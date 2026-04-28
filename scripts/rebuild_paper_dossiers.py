#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

import paper_dossiers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild paper-centric dossier folders for the Obsidian vault.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--run-label", default="obsidian-paper-dossiers")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = paper_dossiers.load_json(Path(args.config))
    run_dir = paper_dossiers.generate_bundle(
        vault_root=Path(config["vault_root"]),
        output_root=Path(args.output_root),
        run_label=args.run_label,
        config=config,
    )
    print(str(run_dir / "run.md"))


if __name__ == "__main__":
    main()
