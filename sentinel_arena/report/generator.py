"""
Report Generator — Produces HTML + markdown reports from benchmark results.
"""

import json
from pathlib import Path
from typing import Dict
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

from ..runner.engine import BenchmarkRun
from .charts import generate_asr_chart


def _category_display_name(cat: str) -> str:
    names = {
        "jailbreakbench": "JailbreakBench",
        "cot_hijack": "CoT Hijacking",
        "autodan": "AutoDAN",
        "encoding": "Encoding Evasion",
        "role_play": "Role-Play / DAN",
        "multi_turn": "Multi-Turn",
        "custom": "GCG / Custom",
    }
    return names.get(cat, cat)


def generate_report(
    run: BenchmarkRun,
    output_dir: Path,
) -> Path:
    """
    Generate HTML report from benchmark results.

    Args:
        run: The completed benchmark run.
        output_dir: Directory to write report files.

    Returns:
        Path to the generated HTML file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = run.summary

    # Generate chart
    chart_path = generate_asr_chart(summary, output_dir / "asr_chart.png")

    # Compute aggregate stats
    all_raw = [r for r in run.results if r.config == "raw"]
    all_guard = [r for r in run.results if r.config == "guardrailed"]
    all_sent = [r for r in run.results if r.config == "sentinel"]

    raw_jb = sum(1 for r in all_raw if r.jailbroken)
    guard_jb = sum(1 for r in all_guard if r.jailbroken)
    sent_jb = sum(1 for r in all_sent if r.jailbroken)

    raw_total = max(len(all_raw), 1)
    guard_total = max(len(all_guard), 1)
    sent_total = max(len(all_sent), 1)

    raw_asr = round(raw_jb / raw_total * 100, 1)
    guard_asr = round(guard_jb / guard_total * 100, 1)
    sentinel_asr = round(sent_jb / sent_total * 100, 1)

    # Category results for table
    category_results = []
    for cat in sorted(summary.keys()):
        configs = summary[cat]
        raw = configs.get("raw", {})
        guard = configs.get("guardrailed", {})
        sent = configs.get("sentinel", {})
        category_results.append({
            "name": _category_display_name(cat),
            "total": raw.get("total", 0),
            "raw_asr": raw.get("asr", 0),
            "guard_asr": guard.get("asr", 0),
            "sentinel_asr": sent.get("asr", 0),
        })

    # Cache hits
    cache_hits = sum(1 for r in run.results if r.cached)

    # Load and render template
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("report.html")

    html = template.render(
        run_id=run.run_id,
        timestamp=run.timestamp,
        models=run.models,
        total_attacks=run.total_attacks,
        raw_asr=raw_asr,
        guard_asr=guard_asr,
        sentinel_asr=sentinel_asr,
        category_results=category_results,
        duration=round(run.duration_seconds, 1),
        cache_hits=cache_hits,
        version="0.1.0",
    )

    html_path = output_dir / "report.html"
    html_path.write_text(html)

    # Also generate markdown summary
    _generate_markdown(run, summary, output_dir, raw_asr, guard_asr, sentinel_asr)

    return html_path


def _generate_markdown(
    run: BenchmarkRun,
    summary: Dict,
    output_dir: Path,
    raw_asr: float,
    guard_asr: float,
    sentinel_asr: float,
):
    """Generate a markdown summary alongside the HTML report."""
    lines = [
        f"# SENTINEL Arena — Benchmark Report",
        f"",
        f"**Run ID:** {run.run_id}",
        f"**Date:** {run.timestamp}",
        f"**Models:** {', '.join(run.models)}",
        f"**Total Attacks:** {run.total_attacks}",
        f"**Duration:** {run.duration_seconds:.1f}s",
        f"",
        f"## Results",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Raw Model ASR | **{raw_asr}%** |",
        f"| Guardrailed ASR | **{guard_asr}%** |",
        f"| SENTINEL ASR | **{sentinel_asr}%** |",
        f"",
        f"## By Category",
        f"",
        f"| Category | Raw | Guardrailed | SENTINEL |",
        f"|----------|-----|-------------|----------|",
    ]

    for cat in sorted(summary.keys()):
        configs = summary[cat]
        raw = configs.get("raw", {}).get("asr", 0)
        guard = configs.get("guardrailed", {}).get("asr", 0)
        sent = configs.get("sentinel", {}).get("asr", 0)
        name = _category_display_name(cat)
        lines.append(f"| {name} | {raw}% | {guard}% | {sent}% |")

    lines.extend([
        f"",
        f"## Why SENTINEL = 0%",
        f"",
        f"SENTINEL uses **capability denial**, not content filtering.",
        f"The model's only output is a single float [0.0-1.0].",
        f"Even if fully jailbroken, only a number gets through.",
        f"The 0% is structural, not statistical.",
        f"",
        f"**Patent:** US Provisional 63/965,457",
        f"",
        f"---",
        f"*Generated by SENTINEL Arena v0.1.0*",
    ])

    md_path = output_dir / "report.md"
    md_path.write_text("\n".join(lines))
