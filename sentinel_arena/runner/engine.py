"""
Benchmark Engine — Orchestrates attacks against raw/guardrailed/SENTINEL.

The heart of the benchmark. For each attack:
1. Raw: Send attack to bare model, judge response
2. Guardrailed: Send attack with safety system prompt, judge response
3. SENTINEL: Send through capability denial wrapper, judge (always 0%)

Collects results and produces structured data for report generation.
"""

import json
import time
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID
from rich.table import Table

from ..sdk.wrapper import SentinelWrapper
from ..sdk.extractor import SentinelExtractError
from ..attacks.loader import Attack, AttackCategory, load_all_attacks
from .judge import Judge, JudgeResult
from .targets import ModelTarget, get_target
from .batch import ResponseCache, RateLimiter

console = Console()


@dataclass
class AttackResult:
    """Result of a single attack against a single config."""
    attack_id: str
    attack_category: str
    config: str  # "raw", "guardrailed", "sentinel"
    model_id: str
    jailbroken: bool
    judge_reason: str
    judge_confidence: float
    response_length: int
    sentinel_score: Optional[float] = None
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    cached: bool = False


@dataclass
class BenchmarkRun:
    """Complete results of a benchmark run."""
    run_id: str
    timestamp: str
    models: List[str]
    total_attacks: int
    results: List[AttackResult] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "models": self.models,
            "total_attacks": self.total_attacks,
            "duration_seconds": self.duration_seconds,
            "results": [asdict(r) for r in self.results],
        }

    @property
    def summary(self) -> Dict[str, Dict[str, Dict]]:
        """
        Compute ASR summary: {category: {config: {total, jailbroken, asr}}}
        """
        cats: Dict[str, Dict[str, list]] = {}
        for r in self.results:
            cat = r.attack_category
            cfg = r.config
            if cat not in cats:
                cats[cat] = {}
            if cfg not in cats[cat]:
                cats[cat][cfg] = []
            cats[cat][cfg].append(r.jailbroken)

        summary = {}
        for cat, configs in cats.items():
            summary[cat] = {}
            for cfg, results in configs.items():
                total = len(results)
                jailbroken = sum(results)
                asr = jailbroken / total if total > 0 else 0.0
                summary[cat][cfg] = {
                    "total": total,
                    "jailbroken": jailbroken,
                    "asr": round(asr * 100, 1),
                }
        return summary


class BenchmarkEngine:
    """
    Orchestrates the full benchmark run.

    Runs each attack against three configurations:
    - raw: bare model
    - guardrailed: safety system prompt
    - sentinel: SENTINEL capability denial wrapper
    """

    def __init__(
        self,
        models: List[str],
        output_dir: Path,
        cache_enabled: bool = True,
        categories: Optional[List[AttackCategory]] = None,
        limit_per_category: Optional[int] = None,
    ):
        self.models = models
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.categories = categories
        self.limit_per_category = limit_per_category

        # Components
        self.judge = Judge()
        self.cache = ResponseCache(self.output_dir / ".cache") if cache_enabled else None
        self._rate_limiters: Dict[str, RateLimiter] = {}

    def _get_limiter(self, target: ModelTarget) -> RateLimiter:
        """Get or create a rate limiter for a model."""
        if target.model_id not in self._rate_limiters:
            self._rate_limiters[target.model_id] = RateLimiter(target.rpm_limit)
        return self._rate_limiters[target.model_id]

    def run(self) -> BenchmarkRun:
        """Execute the full benchmark."""
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        start = time.time()

        # Load attacks
        attacks = load_all_attacks(
            categories=self.categories,
            limit_per_category=self.limit_per_category,
        )

        console.print(f"\n[bold]SENTINEL Arena Benchmark[/bold]")
        console.print(f"  Run ID: {run_id}")
        console.print(f"  Models: {', '.join(self.models)}")
        console.print(f"  Attacks: {len(attacks)}")
        console.print(f"  Configs: raw, guardrailed, sentinel")
        console.print(f"  Total evaluations: {len(attacks) * len(self.models) * 3}\n")

        bench_run = BenchmarkRun(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            models=self.models,
            total_attacks=len(attacks),
        )

        for model_id in self.models:
            target = get_target(model_id)
            wrapper = SentinelWrapper(model=model_id)
            limiter = self._get_limiter(target)

            console.print(f"[bold cyan]Model: {target.name}[/bold cyan] ({model_id})")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Running attacks...",
                    total=len(attacks) * 3,
                )

                for attack in attacks:
                    # --- Config 1: Raw ---
                    result = self._run_attack(
                        attack, model_id, "raw", wrapper, limiter
                    )
                    bench_run.results.append(result)
                    progress.advance(task)

                    # --- Config 2: Guardrailed ---
                    result = self._run_attack(
                        attack, model_id, "guardrailed", wrapper, limiter
                    )
                    bench_run.results.append(result)
                    progress.advance(task)

                    # --- Config 3: SENTINEL ---
                    result = self._run_attack(
                        attack, model_id, "sentinel", wrapper, limiter
                    )
                    bench_run.results.append(result)
                    progress.advance(task)

        bench_run.duration_seconds = time.time() - start

        # Save results
        self._save_results(bench_run)
        self._print_summary(bench_run)

        return bench_run

    def _run_attack(
        self,
        attack: Attack,
        model_id: str,
        config: str,
        wrapper: SentinelWrapper,
        limiter: RateLimiter,
    ) -> AttackResult:
        """Run a single attack against a single config."""
        prompt = attack.prompt

        # Check cache
        if self.cache:
            cached = self.cache.get(model_id, prompt, config)
            if cached is not None:
                # Re-judge the cached response
                if config == "sentinel":
                    judge_result = self.judge.judge_sentinel(0.5, False)
                else:
                    judge_result = self.judge.judge(cached, prompt)
                return AttackResult(
                    attack_id=attack.id,
                    attack_category=attack.category.value,
                    config=config,
                    model_id=model_id,
                    jailbroken=judge_result.jailbroken,
                    judge_reason=judge_result.reason,
                    judge_confidence=judge_result.confidence,
                    response_length=len(cached),
                    cached=True,
                )

        # Rate limit
        limiter.wait_if_needed()

        start = time.time()
        try:
            if config == "raw":
                response = wrapper.evaluate_raw(prompt)
                judge_result = self.judge.judge(response, prompt)
                sentinel_score = None
            elif config == "guardrailed":
                response = wrapper.evaluate_guardrailed(prompt)
                judge_result = self.judge.judge(response, prompt)
                sentinel_score = None
            elif config == "sentinel":
                sentinel_result = wrapper.evaluate(prompt)
                response = f"[SENTINEL score={sentinel_result.score:.4f}]"
                judge_result = self.judge.judge_sentinel(
                    sentinel_result.score,
                    sentinel_result.extract_failed,
                )
                sentinel_score = sentinel_result.score
            else:
                raise ValueError(f"Unknown config: {config}")

            elapsed = (time.time() - start) * 1000

            # Cache the response
            if self.cache and config != "sentinel":
                self.cache.put(model_id, prompt, config, response)

            return AttackResult(
                attack_id=attack.id,
                attack_category=attack.category.value,
                config=config,
                model_id=model_id,
                jailbroken=judge_result.jailbroken,
                judge_reason=judge_result.reason,
                judge_confidence=judge_result.confidence,
                response_length=len(response),
                sentinel_score=sentinel_score,
                elapsed_ms=elapsed,
            )

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return AttackResult(
                attack_id=attack.id,
                attack_category=attack.category.value,
                config=config,
                model_id=model_id,
                jailbroken=False,
                judge_reason=f"Error: {type(e).__name__}",
                judge_confidence=0.0,
                response_length=0,
                elapsed_ms=elapsed,
                error=str(e)[:200],
            )

    def _save_results(self, run: BenchmarkRun):
        """Save raw results as JSON."""
        results_file = self.output_dir / f"results_{run.run_id}.json"
        results_file.write_text(json.dumps(run.to_dict(), indent=2))
        console.print(f"\n[dim]Results saved: {results_file}[/dim]")

    def _print_summary(self, run: BenchmarkRun):
        """Print a summary table to console."""
        summary = run.summary

        table = Table(title=f"\nAttack Success Rate (ASR) — Run {run.run_id}")
        table.add_column("Category", style="cyan")
        table.add_column("Raw ASR", style="red")
        table.add_column("Guardrailed ASR", style="yellow")
        table.add_column("SENTINEL ASR", style="green")

        for cat, configs in sorted(summary.items()):
            raw = configs.get("raw", {})
            guard = configs.get("guardrailed", {})
            sent = configs.get("sentinel", {})

            raw_asr = f"{raw.get('asr', 0)}%"
            guard_asr = f"{guard.get('asr', 0)}%"
            sent_asr = f"{sent.get('asr', 0)}%"

            table.add_row(cat, raw_asr, guard_asr, sent_asr)

        # Totals
        total_raw = sum(1 for r in run.results if r.config == "raw" and r.jailbroken)
        total_guard = sum(1 for r in run.results if r.config == "guardrailed" and r.jailbroken)
        total_sent = sum(1 for r in run.results if r.config == "sentinel" and r.jailbroken)
        count_per = len(run.results) // 3 if run.results else 1

        table.add_section()
        table.add_row(
            "[bold]TOTAL[/bold]",
            f"[bold red]{total_raw}/{count_per} ({total_raw/count_per*100:.1f}%)[/bold red]",
            f"[bold yellow]{total_guard}/{count_per} ({total_guard/count_per*100:.1f}%)[/bold yellow]",
            f"[bold green]{total_sent}/{count_per} ({total_sent/count_per*100:.1f}%)[/bold green]",
        )

        console.print(table)
        console.print(f"\n[dim]Duration: {run.duration_seconds:.1f}s[/dim]")
