"""Script: audit content fidelity."""

from __future__ import annotations

from pathlib import Path

from textbook_pipeline.core.fidelity.auditor import ContentAuditor
from textbook_pipeline.models.fidelity import ContentRegistry

def main():
    registry = ContentRegistry("test_chapter", Path("output"))
    auditor = ContentAuditor(registry)
    report = auditor.run_full_audit()
    print(f"QA passes: {report['passes_qa']}")

if __name__ == "__main__":
    main()
