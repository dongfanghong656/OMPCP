#!/usr/bin/env python
import argparse
import json
from datetime import date
from pathlib import Path

DEFAULT_PEOPLE_FOLDER = "13_People"
DEFAULT_RELATIONSHIP_FOLDER = "14_Relationships"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content.rstrip() + "\n", encoding="utf-8")


def obsidian_with_defaults(obsidian):
    merged = dict(obsidian)
    merged.setdefault("people_folder", DEFAULT_PEOPLE_FOLDER)
    merged.setdefault("relationship_folder", DEFAULT_RELATIONSHIP_FOLDER)
    return merged


def build_seed_files(config):
    obs = obsidian_with_defaults(config["obsidian"])
    today = date.today().isoformat()
    return {
        Path(obs["daily_folder"]) / "_Index.md": "# Daily Notes\n\n- Use one note per day to record what was read, decided, and blocked.\n",
        Path(obs["daily_folder"]) / f"{today}.md": f"# {today}\n\n## Reading\n\n## Decisions\n\n## Questions\n\n## Next actions\n",
        Path("00_Home") / "Home.md": "# OCT Research Vault\n\nThis vault is the durable memory for OCT deconvolution work. It keeps source papers, critical notes, experimental planning, writing fragments, conversation history, and relationship context in one place.\n\n## Navigation\n\n- [[System-Map]]\n- [[Learning-Path]]\n- [[Automation-Playbooks]]\n- [[Search-Guide]]\n\n## Sections\n\n- `01_Daily`: day-by-day trace\n- `02_Papers`: paper notes and reading judgments\n- `03_Concepts`: technical concept notes\n- `04_Progress`: project milestones and risk updates\n- `05_Experiments`: experiment design and evaluation setups\n- `06_Writing`: manuscript fragments\n- `07_Profiles`: current project profile\n- `08_Attachments`: extracted text and copied PDFs\n- `09_Conversations`: durable memory from Codex sessions\n- `10_Tasks`: concrete next actions\n- `11_Retrieval`: newly found papers\n- `12_Zotero`: Zotero integration state\n- `13_People`: durable person profiles and preferences\n- `14_Relationships`: interaction history, commitments, and follow-up cues\n",
        Path("00_Home") / "System-Map.md": "# System Map\n\nDescribe the platform as layered research infrastructure instead of a pile of disconnected notes. The same vault can also carry durable relationship memory for supervisors, collaborators, classmates, and other recurring people in the research loop.\n",
        Path("00_Home") / "Learning-Path.md": "# Learning Path\n\nMap the three-month OCT program from physical understanding to manuscript delivery.\n",
        Path("00_Home") / "Automation-Playbooks.md": "# Automation Playbooks\n\nDocument daily, weekly, and event-driven jobs that keep the vault fresh.\n",
        Path("00_Home") / "Search-Guide.md": "# Search Guide\n\nRecord naming rules, index locations, and recommended search patterns.\n",
        Path(obs["paper_folder"]) / "_Index.md": "# Paper Index\n\n",
        Path(obs["concept_folder"]) / "_Index.md": "# Concept Index\n\n- Add one note per concept when a term needs a stable definition or a literature-backed comparison.\n",
        Path(obs["progress_folder"]) / "_Index.md": "# Progress Index\n\n- Track project-level progress, risks, and decisions here.\n",
        Path(obs["experiment_folder"]) / "_Index.md": "# Experiment Index\n\n- Use this area for phantom protocols, PSF measurement plans, and evaluation setups.\n",
        Path(obs["writing_folder"]) / "_Index.md": "# Writing Index\n\n- Store section drafts, outline fragments, and response-to-reviewer material here.\n",
        Path(obs["profile_folder"]) / "research-profile.md": "# Research Profile\n\nThe current target is a three-month English SCI Q1 submission on OCT deconvolution with emphasis on lateral resolution, artifact control, and reproducibility.\n",
        Path(obs["conversation_folder"]) / "_Index.md": "# Conversation Index\n\n- Each important Codex session should leave a durable summary note.\n",
        Path(obs["task_folder"]) / "_Index.md": "# Task Index\n\n- Store concrete tasks, blockers, owners, and deadlines here.\n",
        Path(obs["retrieval_folder"]) / "_Index.md": "# Retrieval Index\n\n- Save machine retrieval snapshots and short judgments here.\n",
        Path(obs["zotero_folder"]) / "_Index.md": "# Zotero Index\n\n- [[library-health]]\n- Record Zotero library health, exports, and integration state here.\n",
        Path(obs["zotero_folder"]) / "library-health.md": "# Zotero Library Health\n\nRun `refresh_zotero_index.py` to replace this placeholder with a live sqlite-backed report.\n",
        Path(obs["people_folder"]) / "_Index.md": "# People Index\n\n- Keep one durable profile per recurring person and record explicit uncertainty instead of guessing.\n",
        Path(obs["people_folder"]) / "_registry.json": "{\n  \"version\": 1,\n  \"updated_at\": \"\",\n  \"people\": []\n}\n",
        Path(obs["relationship_folder"]) / "_Index.md": "# Relationship Event Index\n\n- Record interaction-level events, commitments, tensions, and follow-up obligations here.\n",
        Path(obs["relationship_folder"]) / "_registry.json": "{\n  \"version\": 1,\n  \"updated_at\": \"\",\n  \"events\": []\n}\n",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_json(config_path)
    vault_root = Path(config["vault_root"])
    output_root = Path(config["output_root"])
    vault_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    obs = obsidian_with_defaults(config["obsidian"])
    for folder in obs.values():
        (vault_root / folder).mkdir(parents=True, exist_ok=True)

    for relative_path, content in build_seed_files(config).items():
        ensure_file(vault_root / relative_path, content)

    print(f"Bootstrapped vault at {vault_root}")


if __name__ == "__main__":
    main()
