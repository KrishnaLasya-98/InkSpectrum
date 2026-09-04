import asyncio
from pathlib import Path
from typing import List
import typer
from rich.console import Console
from rich.table import Table
from .config import settings
from .clients.groq import GroqClient
from .clients.anyapi import AnyAPIClient
from .evaluators.extraction import ExtractionEvaluator
from .evaluators.script_gen import ScriptGenEvaluator
from .evaluators.code_review import CodeReviewEvaluator
from .results.logger import ResultsLogger
from .results.comparison import ModelComparator
from .schemas import TestCase, ModelResult, EvaluationResult

app = typer.Typer()
console = Console()

MODELS = {
    "groq": ["openai/gpt-oss-120b", "qwen3-32b", "qwen3-8b"],
    "anyapi": [
        "qwen3-coder:free",
        "google/gemma-4-26b-a4b-it:free",
        "nvidia/nemotron-nano-9b-v2:free",
    ],
}

TEST_CASES = [
    TestCase(
        name="extraction",
        prompt="Extract key educational concepts from this textbook chapter about food sources. List main topic, 5 subtopics, 3 learning objectives, and any visual aids mentioned.",
        expected_criteria={},
    ),
    TestCase(
        name="script_generation",
        prompt="Generate a 60-second educational video script for Class 4 EVS on 'Food Sources'. Format with scenes, narration, and visuals. Use simple language for 9-10 year olds. Include 1 question.",
        expected_criteria={},
    ),
    TestCase(
        name="code_review",
        prompt="Review this Python Manim scene renderer code. Identify 3 bugs, 2 improvements, and give an overall quality score 1-5. Code: def render_scene(scene): pass",
        expected_criteria={},
    ),
]


def get_client(provider: str):
    if provider == "groq":
        if not settings.groq_api_key:
            console.print("[red]GROQ_API_KEY not set in .env[/red]")
            raise typer.Exit(1)
        return GroqClient(settings.groq_api_key)
    elif provider == "anyapi":
        if not settings.anyapi_api_key:
            console.print("[red]ANYAPI_API_KEY not set in .env[/red]")
            raise typer.Exit(1)
        return AnyAPIClient(settings.anyapi_api_key)
    else:
        console.print(f"[red]Unknown provider: {provider}[/red]")
        raise typer.Exit(1)


@app.command()
def test(
    provider: str = typer.Option("groq", help="Provider: groq or anyapi"),
    model: str = typer.Option(None, help="Model name (default: first in list)"),
    task: str = typer.Option(None, help="Task: extraction, script_generation, code_review, or all"),
):
    """Run evaluation on a specific model."""
    client = get_client(provider)
    models = [model] if model else MODELS[provider]
    tasks = [task] if task and task != "all" else ["extraction", "script_generation", "code_review"]

    evaluators = {
        "extraction": ExtractionEvaluator(),
        "script_generation": ScriptGenEvaluator(),
        "code_review": CodeReviewEvaluator(),
    }

    logger = ResultsLogger()
    all_results = []

    for m in models:
        console.print(f"\n[bold blue]Testing {provider}/{m}[/bold blue]")
        for t in tasks:
            console.print(f"  Task: {t}...")
            evaluator = evaluators[t]
            test_cases = [tc for tc in TEST_CASES if tc.name == t]
            result = asyncio.run(evaluator.run(client, m, test_cases))
            logger.log(result)
            all_results.append(result)

            status = "[green]PASS[/green]" if result.score >= 0.5 else "[yellow]LOW[/yellow]"
            console.print(f"    Score: {result.score:.2f} {status}")

    console.print(f"\n[green]Results saved to {settings.results_dir}/[/green]")


@app.command()
def compare():
    """Compare all saved results."""
    logger = ResultsLogger()
    results = logger.load_all()
    if not results:
        console.print("[yellow]No results found. Run 'test' first.[/yellow]")
        raise typer.Exit()

    comparator = ModelComparator()
    summary = comparator.compare([EvaluationResult(**r) for r in results])

    table = Table(title="Model Comparison")
    table.add_column("Model", style="cyan")
    table.add_column("Avg Score", justify="right")
    table.add_column("Min Score", justify="right")
    table.add_column("Max Score", justify="right")
    table.add_column("Avg Latency (ms)", justify="right")
    table.add_column("Tasks", justify="right")

    for model, data in summary.items():
        table.add_row(
            model,
            f"{data['avg_score']:.2f}",
            f"{data['min_score']:.2f}",
            f"{data['max_score']:.2f}",
            f"{data['avg_latency_ms']:.0f}",
            str(data["tasks_completed"]),
        )

    console.print(table)


@app.command()
def report():
    """Generate detailed report."""
    logger = ResultsLogger()
    results = logger.load_all()
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        raise typer.Exit()

    for r in results[-5:]:
        console.print(f"\n[bold]{r['task']}[/bold] - {r['model']} ({r['provider']})")
        console.print(f"  Score: {r['score']:.2f}")
        console.print(f"  Details: {r['details']}")
        if r["results"] and r["results"][0].get("response"):
            resp = r["results"][0]["response"][:200]
            console.print(f"  Response preview: {resp}...")


if __name__ == "__main__":
    app()
