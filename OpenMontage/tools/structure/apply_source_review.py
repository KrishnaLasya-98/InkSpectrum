"""Apply explicit, reviewed additions/corrections without losing source history.

Outputs a new document; never overwrites the source document. This does not
certify PDF fidelity: the review patch must come from an actual page review.
"""
import argparse
import copy
import json
from pathlib import Path

from schemas.artifacts import validate_artifact
from tools.structure.source_contract import build_coverage_contract


def apply_review(document, review):
    result = copy.deepcopy(document)
    by_id = {b["block_id"]: b for b in result["blocks"]}
    for change in review.get("replacements", []):
        block = by_id[change["block_id"]]
        if block["source_text"] != change["expected_text"]:
            raise ValueError(f"Stale source review: {block['block_id']}")
        block["source_text"] = change["replacement_text"]
    for addition in review.get("additions", []):
        if addition["block_id"] in by_id:
            raise ValueError(f"Duplicate source ID: {addition['block_id']}")
        block = copy.deepcopy(addition)
        after_id = block.pop("after_block_id")
        index = next(i for i, b in enumerate(result["blocks"]) if b["block_id"] == after_id)
        block["reading_order"] = index + 2
        result["blocks"].insert(index + 1, block)
        by_id[block["block_id"]] = block
    for index, block in enumerate(result["blocks"], 1):
        block["reading_order"] = index
    for page in result["pages"]:
        page["block_ids"] = [b["block_id"] for b in result["blocks"] if b["page_number"] == page["page_number"]]
    result["validation"].update(
        block_count=len(result["blocks"]),
        required_block_count=sum(bool(b["required_for_coverage"]) for b in result["blocks"]),
        semantic_roles=sorted({b["semantic_role"] for b in result["blocks"]}),
        recovered_layout_blocks=result["validation"].get("recovered_layout_blocks", 0) + len(review.get("additions", [])),
    )
    # Layout geometry still requires downstream evidence. Do not falsely upgrade
    # an incomplete geometry contract just because someone read its pages.
    validate_artifact("chapter_document", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("document", type=Path)
    parser.add_argument("review", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    if args.document.resolve().parent == args.output_dir.resolve():
        raise SystemExit("Choose a new revision directory; preserve source history")
    document = apply_review(json.loads(args.document.read_text(encoding="utf-8")),
                            json.loads(args.review.read_text(encoding="utf-8")))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in (("chapter_document", document), ("coverage_contract", build_coverage_contract(document))):
        (args.output_dir / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir), "source_blocks": len(document["blocks"])}))


if __name__ == "__main__":
    main()
