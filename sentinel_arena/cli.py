"""
SENTINEL Arena CLI - Entry point for running benchmarks and generating reports.

Usage:
    sentinel-arena run [--models MODEL] [--categories CAT] [--limit N] [--output DIR]
    sentinel-arena report RESULTS_DIR
    sentinel-arena attacks [--category CAT]
    sentinel-arena models
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .attacks.loader import AttackCategory, load_all_attacks
from .runner.engine import BenchmarkEngine, BenchmarkRun
from .runner.targets import list_targets, get_target
from .report.generator import generate_report

console = Console()


@click.group(invoke_without_command=True)
@click.option('--version', is_flag=True, help='Show version')
@click.pass_context
def main(ctx, version):
    """SENTINEL Arena - Capability denial benchmark suite."""
    if version:
        click.echo(f"sentinel-arena v{__version__}")
        return
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.option('--models', '-m', multiple=True, default=['ollama/llama3.2:3b'],
              help='Model IDs to test (repeatable)')
@click.option('--categories', '-c', multiple=True, default=None,
              help='Attack categories to include (repeatable)')
@click.option('--limit', '-l', type=int, default=None,
              help='Limit attacks per category')
@click.option('--output', '-o', type=click.Path(), default=None,
              help='Output directory for results')
@click.option('--no-cache', is_flag=True, help='Disable response caching')
def run(models, categories, limit, output, no_cache):
    """Run the benchmark against specified models."""
    # Parse categories
    cat_filter = None
    if categories:
        cat_filter = []
        for c in categories:
            try:
                cat_filter.append(AttackCategory(c))
            except ValueError:
                console.print(f"[red]Unknown category: {c}[/red]")
                valid = [ac.value for ac in AttackCategory]
                console.print(f"Valid: {', '.join(valid)}")
                sys.exit(1)

    # Set output directory
    if output is None:
        output = Path("results") / "latest"
    output = Path(output)

    # Run benchmark
    engine = BenchmarkEngine(
        models=list(models),
        output_dir=output,
        cache_enabled=not no_cache,
        categories=cat_filter,
        limit_per_category=limit,
    )

    console.print(f"\n[bold green]SENTINEL Arena v{__version__}[/bold green]")
    console.print(f"Starting benchmark...\n")

    bench_run = engine.run()

    # Auto-generate report
    console.print(f"\n[bold]Generating report...[/bold]")
    report_path = generate_report(bench_run, output)
    console.print(f"[green]Report: {report_path}[/green]")


@main.command()
@click.argument('results_dir', type=click.Path(exists=True))
def report(results_dir):
    """Generate report from existing results."""
    results_dir = Path(results_dir)

    # Find the latest results JSON
    json_files = sorted(results_dir.glob("results_*.json"))
    if not json_files:
        console.print(f"[red]No results files found in {results_dir}[/red]")
        sys.exit(1)

    results_file = json_files[-1]
    console.print(f"Loading: {results_file}")

    data = json.loads(results_file.read_text())

    # Reconstruct BenchmarkRun
    from .runner.engine import BenchmarkRun, AttackResult
    bench_run = BenchmarkRun(
        run_id=data["run_id"],
        timestamp=data["timestamp"],
        models=data["models"],
        total_attacks=data["total_attacks"],
        duration_seconds=data["duration_seconds"],
        results=[AttackResult(**r) for r in data["results"]],
    )

    report_path = generate_report(bench_run, results_dir)
    console.print(f"[green]Report generated: {report_path}[/green]")


@main.command()
@click.option('--category', '-c', default=None, help='Filter by category')
def attacks(category):
    """List available attack vectors."""
    cat_filter = None
    if category:
        try:
            cat_filter = [AttackCategory(category)]
        except ValueError:
            console.print(f"[red]Unknown category: {category}[/red]")
            sys.exit(1)

    all_attacks = load_all_attacks(categories=cat_filter)

    table = Table(title=f"Attack Vectors ({len(all_attacks)} total)")
    table.add_column("ID", style="dim")
    table.add_column("Category", style="cyan")
    table.add_column("Description", max_width=60)
    table.add_column("Source", style="dim", max_width=30)

    for a in all_attacks:
        table.add_row(
            a.id,
            a.category.value,
            a.description[:60],
            a.source[:30],
        )

    console.print(table)


@main.command()
@click.option('--local-only', is_flag=True, help='Show only free local models')
def models(local_only):
    """List available model targets."""
    targets = list_targets(local_only=local_only)

    table = Table(title="Available Models")
    table.add_column("Model ID", style="cyan")
    table.add_column("Name")
    table.add_column("Provider")
    table.add_column("Local", style="green")
    table.add_column("RPM Limit", style="dim")

    for t in targets:
        table.add_row(
            t.model_id,
            t.name,
            t.provider,
            "Yes" if t.is_local else "No",
            str(t.rpm_limit) if t.rpm_limit else "unlimited",
        )

    console.print(table)


if __name__ == "__main__":
    main()
