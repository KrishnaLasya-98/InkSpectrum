import asyncio
import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import typer
from rich.console import Console
from rich.table import Table
from .registry import registry
from .evaluator import ModelEvaluator, TestResult


app = typer.Typer(help="LLM Model Testing Sprint - Phase 0")
console = Console()


@app.command()
def test(
    provider: str = typer.Option(..., "--provider", "-p", help="Provider name (groq, anyapi, together, deepseek)"),
    task: str = typer.Option(..., "--task", "-t", help="Task name (extraction, script_gen, code_review)"),
    models: Optional[str] = typer.Option(None, "--models", "-m", help="Comma-separated model IDs"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file for results"),
):
    """Run a specific task against one or more models."""
    provider_instance = registry.get_provider(provider)
    task_cls = registry.get_task(task)
    
    if models:
        model_ids = [m.strip() for m in models.split(",")]
    else:
        model_configs = registry.list_models(provider=provider, free_only=True)
        model_ids = [m.model_id for m in model_configs]
    
    if not model_ids:
        console.print(f"[red]No models found for provider: {provider}[/red]")
        raise typer.Exit(1)
    
    console.print(f"[cyan]Testing {len(model_ids)} models on task '{task}'...[/cyan]")
    
    # Get test content
    if task == "extraction":
        from docling.document_converter import DocumentConverter
        import tempfile
        test_content = "This is a test document about photosynthesis. Photosynthesis is the process by which plants convert light energy into chemical energy."
        messages = task_cls().get_messages(test_content)
    else:
        messages = task_cls().get_messages()
    
    evaluator = ModelEvaluator()
    results = asyncio.run(evaluator.run_benchmark(
        provider_name=provider,
        model_ids=model_ids,
        task_name=task,
        messages=messages,
        scorer_func=task_cls().score
    ))
    
    # Display results
    table = Table(title=f"Results: {task} on {provider}")
    table.add_column("Model", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Score", style="yellow")
    table.add_column("Latency", style="magenta")
    table.add_column("Tokens", style="blue")
    table.add_column("Cost", style="red")
    
    for r in results:
        status_color = "green" if r.status.value == "pass" else "red"
        table.add_row(
            r.model_id,
            f"[{status_color}]{r.status.value}[/{status_color}]",
            f"{r.score:.2f}/5.0",
            f"{r.latency_ms:.0f}ms",
            str(r.total_tokens),
            f"${r.cost_usd:.4f}"
        )
    
    console.print(table)
    
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            json.dump([{
                "model_id": r.model_id,
                "task_name": r.task_name,
                "status": r.status.value,
                "score": r.score,
                "latency_ms": r.latency_ms,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "cost_usd": r.cost_usd,
                "error": r.error,
                "timestamp": datetime.utcnow().isoformat()
            } for r in results], f, indent=2)
        console.print(f"[green]Results saved to {output}[/green]")


@app.command()
def test_all(
    output_dir: Path = typer.Option(Path("test_results"), "--output-dir", "-o"),
):
    """Run all tasks against all free models."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    providers = ["groq", "anyapi"]
    tasks = ["extraction", "script_gen", "code_review"]
    
    all_results = []
    
    for provider_name in providers:
        try:
            provider_instance = registry.get_provider(provider_name)
            model_configs = registry.list_models(provider=provider_name, free_only=True)
            model_ids = [m.model_id for m in model_configs]
            
            if not model_ids:
                continue
            
            for task_name in tasks:
                task_cls = registry.get_task(task_name)
                if task_name == "extraction":
                    test_content = "Photosynthesis is the process by which plants convert light energy into chemical energy stored in glucose."
                    messages = task_cls().get_messages(test_content)
                else:
                    messages = task_cls().get_messages()
                
                console.print(f"[cyan]Testing {provider_name} / {task_name}...[/cyan]")
                evaluator = ModelEvaluator()
                results = asyncio.run(evaluator.run_benchmark(
                    provider_name=provider_name,
                    model_ids=model_ids,
                    task_name=task_name,
                    messages=messages,
                    scorer_func=task_cls().score
                ))
                all_results.extend(results)
        except Exception as e:
            console.print(f"[yellow]Skipping provider {provider_name}: {e}[/yellow]")
    
    # Save combined results
    combined_file = output_dir / "combined_results.json"
    with open(combined_file, "w") as f:
        json.dump([{
            "model_id": r.model_id,
            "task_name": r.task_name,
            "status": r.status.value,
            "score": r.score,
            "latency_ms": r.latency_ms,
            "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
            "total_tokens": r.total_tokens,
            "cost_usd": r.cost_usd,
            "error": r.error,
            "timestamp": datetime.utcnow().isoformat()
        } for r in all_results], f, indent=2)
    
    # Summary table
    table = Table(title="Combined Results Summary")
    table.add_column("Model", style="cyan")
    table.add_column("Tasks", style="green")
    table.add_column("Avg Score", style="yellow")
    table.add_column("Avg Latency", style="magenta")
    
    model_stats = {}
    for r in all_results:
        if r.model_id not in model_stats:
            model_stats[r.model_id] = {"scores": [], "latencies": [], "count": 0}
        model_stats[r.model_id]["scores"].append(r.score)
        model_stats[r.model_id]["latencies"].append(r.latency_ms)
        model_stats[r.model_id]["count"] += 1
    
    for model_id, stats in model_stats.items():
        avg_score = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0
        avg_latency = sum(stats["latencies"]) / len(stats["latencies"]) if stats["latencies"] else 0
        table.add_row(
            model_id,
            str(stats["count"]),
            f"{avg_score:.2f}/5.0",
            f"{avg_latency:.0f}ms"
        )
    
    console.print(table)
    console.print(f"[green]Combined results saved to {combined_file}[/green]")


@app.command()
def report(
    results_file: Path = typer.Argument(..., help="JSON results file from test command"),
):
    """Generate a comparison report from test results."""
    with open(results_file) as f:
        results = json.load(f)
    
    table = Table(title="Model Comparison Report")
    table.add_column("Model", style="cyan")
    table.add_column("Task", style="green")
    table.add_column("Score", style="yellow")
    table.add_column("Latency", style="magenta")
    table.add_column("Tokens", style="blue")
    table.add_column("Cost", style="red")
    table.add_column("Status", style="white")
    
    for r in results:
        table.add_row(
            r["model_id"],
            r["task_name"],
            f"{r['score']:.2f}/5.0",
            f"{r['latency_ms']:.0f}ms",
            str(r["total_tokens"]),
            f"${r['cost_usd']:.4f}",
            r["status"]
        )
    
    console.print(table)


@app.command()
def models(
    provider: Optional[str] = typer.Option(None, "--provider", "-p"),
    free_only: bool = typer.Option(False, "--free-only", "-f"),
):
    """List available models."""
    model_configs = registry.list_models(provider=provider, free_only=free_only)
    
    table = Table(title="Available Models")
    table.add_column("Model ID", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Context", style="yellow")
    table.add_column("RPM", style="magenta")
    table.add_column("Input $/1M", style="red")
    table.add_column("Output $/1M", style="red")
    
    for m in model_configs:
        table.add_row(
            m.model_id,
            m.provider,
            str(m.context_window),
            str(m.rpm_limit or "N/A"),
            f"${m.input_cost_per_1m:.2f}",
            f"${m.output_cost_per_1m:.2f}"
        )
    
    console.print(table)


if __name__ == "__main__":
    app()
