#!/usr/bin/env python
import argparse
import json
from datetime import date, datetime
from pathlib import Path

from relationship_memory import update_memory_from_payload


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def append_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--memory-payload")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_json(config_path)
    vault_root = Path(config["vault_root"])
    obs = config["obsidian"]
    today = date.today().isoformat()
    stamp = datetime.now().strftime("%H%M%S")
    slug = args.title.lower().replace(" ", "-")
    conversation_path = vault_root / obs["conversation_folder"] / f"{today}-{slug}-{stamp}.md"
    daily_path = vault_root / obs["daily_folder"] / f"{today}.md"
    conversation_path.parent.mkdir(parents=True, exist_ok=True)
    daily_path.parent.mkdir(parents=True, exist_ok=True)

    content = f"# {args.title}\n\n- Date: {today}\n- Time: {datetime.now().strftime('%H:%M:%S')}\n\n## Summary\n\n{args.summary.strip()}\n"
    conversation_path.write_text(content, encoding="utf-8")

    if not daily_path.exists():
        daily_path.write_text(f"# {today}\n\n## Reading\n\n## Decisions\n\n## Questions\n\n## Next actions\n", encoding="utf-8")
    append_text(daily_path, f"\n## Conversation update\n\n- [[{conversation_path.stem}]]\n")

    if args.memory_payload:
        update_memory_from_payload(
            config_path=config_path,
            payload_path=Path(args.memory_payload),
            source_note=conversation_path.stem,
        )

    print(str(conversation_path))


if __name__ == "__main__":
    main()
