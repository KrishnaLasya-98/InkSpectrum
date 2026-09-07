"""Workspace entrypoints for new_video_pip."""

import argparse
import sys
from pathlib import Path

PACKAGES_ROOT = Path(__file__).parent.parent / "packages"
sys.path.insert(0, str(PACKAGES_ROOT / "edugen"))
sys.path.insert(0, str(PACKAGES_ROOT / "video-explainer"))
sys.path.insert(0, str(PACKAGES_ROOT / "textbook-pipeline" / "src"))
sys.path.insert(0, str(PACKAGES_ROOT / "model_testing"))


def run_edugen():
    from animation_creator import main as edugen_main
    edugen_main()


def run_video_explainer():
    from generate_video import main as ve_main
    ve_main()


def run_textbook_pipeline():
    from textbook_pipeline.cli import main as tp_main
    tp_main()


def run_model_test():
    from model_testing.cli import app
    app()


def main():
    parser = argparse.ArgumentParser(description="new_video_pip workspace runner")
    parser.add_argument("module", choices=["edugen", "video_explainer", "textbook_pipeline", "model_test"])
    args = parser.parse_args()

    if args.module == "edugen":
        run_edugen()
    elif args.module == "video_explainer":
        run_video_explainer()
    elif args.module == "textbook_pipeline":
        run_textbook_pipeline()
    elif args.module == "model_test":
        run_model_test()


if __name__ == "__main__":
    main()
