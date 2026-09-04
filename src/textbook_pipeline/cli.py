"""Unified CLI for the textbook pipeline."""

from __future__ import annotations

import logging
from pathlib import Path

import typer

app = typer.Typer(help="Textbook-to-Video Pipeline")

logger = logging.getLogger(__name__)


@app.command()
def generate(
    pdf: Path = typer.Argument(..., help="Input PDF path"),
    subject: str = typer.Option("english", help="Subject: english, math, science, social"),
    grade: int = typer.Option(1, help="Grade level"),
    output: Path = typer.Option(Path("output"), help="Output directory"),
):
    """Generate video from PDF (full pipeline)."""
    typer.echo(f"Generating video from {pdf}...")
    typer.echo(f"Subject: {subject}, Grade: {grade}")
    typer.echo(f"Output: {output}")
    # TODO: Implement full pipeline


@app.command()
def ingest(
    pdf: Path = typer.Argument(..., help="Input PDF path"),
    output: Path = typer.Option(Path("output"), help="Output directory"),
):
    """Extract chapter structure from PDF."""
    typer.echo(f"Ingesting {pdf}...")
    # TODO: Implement ingestion


@app.command()
def script(
    chapter_json: Path = typer.Argument(..., help="Chapter JSON path"),
    output: Path = typer.Option(Path("output"), help="Output directory"),
):
    """Generate script from chapter JSON."""
    typer.echo(f"Generating script from {chapter_json}...")
    # TODO: Implement script generation


@app.command()
def render(
    storyboard: Path = typer.Argument(..., help="Storyboard JSON path"),
    output: Path = typer.Option(Path("output"), help="Output directory"),
):
    """Render video from storyboard."""
    typer.echo(f"Rendering from {storyboard}...")
    # TODO: Implement rendering


@app.command()
def subjects():
    """List available subjects and their configurations."""
    typer.echo("Available subjects: english, math, science, social, humanities")


def main():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
