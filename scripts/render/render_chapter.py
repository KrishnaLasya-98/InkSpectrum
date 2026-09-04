"""Script: render a chapter to video."""

from __future__ import annotations

from pathlib import Path

from textbook_pipeline.core.compose.assembler import Compositor

def main():
    compositor = Compositor()
    print("Compositor ready")

if __name__ == "__main__":
    main()
