#!/usr/bin/env python
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_file(path: Path):
    if not path.exists():
        return {}
    try:
        return load_json(path)
    except json.JSONDecodeError:
        return {}


def iso_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_parent(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str):
    ensure_parent(path)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def parse_iso(value: str):
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            ).timestamp()
        except ValueError:
            return 0.0


def relative_string(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def resolve_configured_path(value: str | None, base_dir: Path) -> Path | None:
    if not value:
        return None
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_dir / candidate).resolve()


def configured_vault_root(config_path: Path) -> Path | None:
    config = load_json_file(config_path)
    return resolve_configured_path(config.get("vault_root"), config_path.parent)


def scan_tasks(bridge_root: Path):
    tasks = []
    tasks_root = bridge_root / "tasks"
    runs_root = bridge_root / "runs"
    for bucket in ("inbox", "claimed", "done"):
        task_dir = tasks_root / bucket
        if not task_dir.exists():
            continue
        for task_path in sorted(task_dir.glob("*.yaml")):
            task_id = task_path.stem
            status_path = runs_root / task_id / "status.json"
            status_data = {}
            if status_path.exists():
                try:
                    status_data = load_json(status_path)
                except json.JSONDecodeError:
                    status_data = {}
            tasks.append(
                {
                    "task_id": task_id,
                    "bucket": bucket,
                    "title": status_data.get("title", task_id),
                    "status": status_data.get("status", bucket),
                    "assigned_provider": status_data.get("assigned_provider", ""),
                    "planning_owner": status_data.get("planning_owner", ""),
                    "execution_owner": status_data.get("execution_owner", ""),
                    "updated_at": status_data.get("updated_at", ""),
                    "path": task_path,
                    "status_path": status_path if status_path.exists() else None,
                }
            )
    tasks.sort(key=lambda item: parse_iso(item["updated_at"]), reverse=True)
    return tasks


def scan_run_statuses(bridge_root: Path):
    run_entries = []
    runs_root = bridge_root / "runs"
    if not runs_root.exists():
        return run_entries
    for run_dir in runs_root.iterdir():
        if not run_dir.is_dir():
            continue
        status_path = run_dir / "status.json"
        summary_path = run_dir / "summary.md"
        if not status_path.exists():
            continue
        try:
            status_data = load_json(status_path)
        except json.JSONDecodeError:
            continue
        run_entries.append(
            {
                "task_id": status_data.get("task_id", run_dir.name),
                "title": status_data.get("title", run_dir.name),
                "status": status_data.get("status", ""),
                "assigned_provider": status_data.get("assigned_provider", ""),
                "planning_owner": status_data.get("planning_owner", ""),
                "execution_owner": status_data.get("execution_owner", ""),
                "updated_at": status_data.get("updated_at", ""),
                "status_path": status_path,
                "summary_path": summary_path if summary_path.exists() else None,
            }
        )
    run_entries.sort(key=lambda item: parse_iso(item["updated_at"]), reverse=True)
    return run_entries


def scan_markdown_files(root: Path, limit: int = 20):
    if not root.exists():
        return []
    entries = []
    for path in root.rglob("*.md"):
        if not path.is_file():
            continue
        entries.append({"name": path.name, "path": path, "mtime": path.stat().st_mtime})
    entries.sort(key=lambda item: item["mtime"], reverse=True)
    return entries[:limit]


def scan_recursive_markdown_files(root: Path, filename: str = "summary.md", limit: int = 20):
    if not root.exists():
        return []
    entries = []
    for path in root.rglob(filename):
        if not path.is_file():
            continue
        entries.append({"name": path.name, "path": path, "mtime": path.stat().st_mtime})
    entries.sort(key=lambda item: item["mtime"], reverse=True)
    return entries[:limit]


CLAUDE_MEMORY_DIR = Path(
    r"C:\Users\1\.claude\projects"
    r"\c--Users-1-OneDrive---fzu-edu-cn--1--Attachments\memory"
)


def scan_claude_memories(memory_dir: Path = CLAUDE_MEMORY_DIR):
    """Scan Claude Code memory files, parse YAML frontmatter."""
    if not memory_dir.exists():
        return []
    entries = []
    for md_path in sorted(memory_dir.glob("*.md")):
        if md_path.name in ("MEMORY.md", "bridge_knowledge_digest.md"):
            continue
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta = {}
        if text.startswith("---"):
            end = text.find("---", 3)
            if end > 0:
                for line in text[3:end].strip().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip()
        entries.append({
            "name": meta.get("name", md_path.stem),
            "description": meta.get("description", ""),
            "type": meta.get("type", "unknown"),
            "path": md_path,
            "mtime": md_path.stat().st_mtime,
        })
    entries.sort(key=lambda x: x["mtime"], reverse=True)
    return entries


def build_claude_memory_note(memories):
    """Generate vault note indexing Claude Code memories."""
    body = [
        "---",
        "note_type: claude-code-memory-index",
        "generated_by: sync_tri_agent_workspace.py",
        f"generated_at: {iso_now()}",
        "---",
        "",
        "# Claude Code Memory Index",
        "",
        "Claude Code's persistent memory files, synced from "
        "`C:/Users/1/.claude/projects/c--Users-1-OneDrive---fzu-edu-cn--1--Attachments/memory/`.",
        "",
    ]
    if not memories:
        body.append("- No Claude Code memories found.")
    else:
        body.append("| Memory | Type | Description |")
        body.append("| --- | --- | --- |")
        for m in memories:
            body.append(f"| {m['name']} | {m['type']} | {m['description']} |")
    body.extend([
        "",
        "## Sync",
        "",
        "- Push: `C:\\codex-data\\ai_bridge\\Sync-Claude-Memory.cmd push`",
        "- Pull: `C:\\codex-data\\ai_bridge\\Sync-Claude-Memory.cmd pull`",
        "- Full: `C:\\codex-data\\ai_bridge\\Sync-Claude-Memory.cmd sync`",
    ])
    return "\n".join(body)


def scan_packet_dir(root: Path, limit: int = 12):
    if not root.exists():
        return []
    entries = []
    for path in root.glob("*.md"):
        if not path.is_file():
            continue
        entries.append({"name": path.name, "path": path, "mtime": path.stat().st_mtime})
    entries.sort(key=lambda item: item["mtime"], reverse=True)
    return entries[:limit]


def scan_jsonl_entries(path: Path, limit: int = 20):
    if not path.exists():
        return []
    entries = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        entries.append(item)
    entries.sort(key=lambda item: parse_iso(item.get("created_at", "")), reverse=True)
    return entries[:limit]


def render_provider_state(provider_state: dict):
    rows = [
        "| Provider | State | Cooldown Until | Failure Count | Last Failure |",
        "| --- | --- | --- | ---: | --- |",
    ]
    providers = provider_state.get("providers", {})
    for name in ("codex", "claude", "antigravity"):
        info = providers.get(name, {})
        rows.append(
            "| {name} | {state} | {cooldown} | {count} | {failure} |".format(
                name=name,
                state=info.get("state", "unknown"),
                cooldown=info.get("cooldown_until", "-") or "-",
                count=info.get("failure_count", 0),
                failure=info.get("last_failure_type", "-") or "-",
            )
        )
    return "\n".join(rows)


def render_task_rows(tasks):
    rows = [
        "| Task | Status | Assigned | Planning Owner | Execution Owner | Updated |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if not tasks:
        rows.append("| - | - | - | - | - | - |")
        return "\n".join(rows)
    for task in tasks:
        rows.append(
            "| {task_id} | {status} | {assigned} | {planner} | {executor} | {updated} |".format(
                task_id=task["task_id"],
                status=task["status"] or "-",
                assigned=task["assigned_provider"] or "-",
                planner=task["planning_owner"] or "-",
                executor=task["execution_owner"] or "-",
                updated=task["updated_at"] or "-",
            )
        )
    return "\n".join(rows)


def render_run_rows(runs, bridge_root: Path, limit: int = 8):
    rows = [
        "| Task | Status | Assigned | Updated | Summary Path |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not runs:
        rows.append("| - | - | - | - | - |")
        return "\n".join(rows)
    for item in runs[:limit]:
        summary_path = (
            relative_string(item["summary_path"], bridge_root) if item["summary_path"] else "-"
        )
        rows.append(
            "| {task_id} | {status} | {assigned} | {updated} | `{summary}` |".format(
                task_id=item["task_id"],
                status=item["status"] or "-",
                assigned=item["assigned_provider"] or "-",
                updated=item["updated_at"] or "-",
                summary=summary_path,
            )
        )
    return "\n".join(rows)


def render_file_bullets(entries, root: Path):
    if not entries:
        return "- None"
    lines = []
    for entry in entries:
        rel_path = relative_string(entry["path"], root)
        lines.append(f"- `{rel_path}`")
    return "\n".join(lines)


def build_registry_note(vault_root: Path, bridge_root: Path, provider_state: dict):
    return f"""---
note_type: tri-agent-registry
generated_by: sync_tri_agent_workspace.py
generated_at: {iso_now()}
---

# Tri-Agent System Registry

> [!info]
> This note is autogenerated from the live bridge workspace. Edit runtime sources in `C:/codex-data/ai_bridge`, then rerun `python oct-research-assist/scripts/sync_tri_agent_workspace.py`.

## Canonical Principle

- The durable human-readable memory lives in this Obsidian vault.
- The runtime task bus, packet queues, and provider health still live under `C:/codex-data/ai_bridge`.
- Every durable change should be visible in the vault through a stable note, not only in chat or packet files.

## Provider Roles

| Provider | Main Role | What It Owns |
| --- | --- | --- |
| Codex | Control plane and archivist | Task bus orchestration, synthesis, durable write-back, repository-safe execution |
| Claude Code | Complex-task planner and strike worker | Architecture judgment, hard debugging, high-risk implementation, final review |
| Antigravity | Deep execution plane | Browser-heavy work, long-running execution, simulation runs, artifact collection |

## Runtime State

{render_provider_state(provider_state)}

## Runtime Sources

- Bridge root: `C:/codex-data/ai_bridge`
- Task bus: `C:/codex-data/ai_bridge/task_bus.js`
- Provider registry: `C:/codex-data/ai_bridge/config/provider_registry.yaml`
- Failover policy: `C:/codex-data/ai_bridge/config/failover_policy.yaml`
- Provider state: `C:/codex-data/ai_bridge/state/provider_state.json`
- Shared bridge knowledge: `C:/codex-data/ai_bridge/shared_knowledge`
- Claude handoff root: `C:/codex-data/ai_bridge/handoff/claude`
- Antigravity handoff root: `C:/codex-data/ai_bridge/handoff/antigravity`

## Vault Views

- [[Tri-Agent Hub]]
- [[Tri-Agent Vault Write Protocol]]
- [[Tri-Agent Knowledge Index]]
- [[tri-agent-control-plane-progress]]
- [[Tri-Agent Task Bus Board]]
- [[Tri-Agent Conversation Stream]]
- [[Claude Code Memory Index]]
"""


def build_knowledge_index(
    vault_root: Path,
    bridge_root: Path,
    project_root: Path,
    shared_docs,
    run_docs,
    anchor_docs,
    claude_memories=None,
):
    claude_section = ""
    if claude_memories:
        rows = ["## Claude Code Memories", ""]
        rows.append("| Memory | Type | Description |")
        rows.append("| --- | --- | --- |")
        for m in claude_memories:
            rows.append(f"| {m['name']} | {m['type']} | {m['description']} |")
        rows.append("")
        claude_section = "\n".join(rows)

    return f"""---
note_type: tri-agent-knowledge-index
generated_by: sync_tri_agent_workspace.py
generated_at: {iso_now()}
---

# Tri-Agent Knowledge Index

This note centralizes the bridge-side documents that explain roles, rules, capabilities, and current shared context. The vault note is the Obsidian-friendly index; the source documents remain under `C:/codex-data/ai_bridge`.

## Bridge Shared Knowledge

{render_file_bullets(shared_docs, bridge_root)}

{claude_section}## Project Anchor Docs

{render_file_bullets(anchor_docs, project_root)}

## High-Value Runtime Notes

{render_file_bullets(run_docs, bridge_root)}

## Vault Counterparts

- [[Tri-Agent System Registry]]
- [[Tri-Agent Vault Write Protocol]]
- [[tri-agent-control-plane-progress]]
- [[Tri-Agent Task Bus Board]]
- [[Tri-Agent Conversation Stream]]
- [[Tri-Agent Shared Intelligence Feed]]

## Editing Rule

- Add new durable bridge knowledge under `ai_bridge/shared_knowledge/`.
- If the document changes roles, routing, or operating conventions, rerun the sync script so this vault index stays current.
"""


def build_progress_note(vault_root: Path, bridge_root: Path, tasks, runs, recent_bridge_docs):
    queued = [task for task in tasks if task["status"] == "queued"]
    claimed = [task for task in tasks if task["status"] == "claimed"]
    completed = [run for run in runs if run["status"] == "completed"]
    return f"""---
note_type: tri-agent-progress
generated_by: sync_tri_agent_workspace.py
generated_at: {iso_now()}
---

# tri-agent-control-plane-progress

## Current Queue

{render_task_rows(queued)}

## Currently Claimed

{render_task_rows(claimed)}

## Recent Completed Runs

{render_run_rows(completed, bridge_root)}

## Recent Bridge Document Changes

{render_file_bullets(recent_bridge_docs, bridge_root)}

## Interpretation

- If a task remains queued for too long, hand it to the intended worker through the packet queue and then rerun this sync.
- If a durable decision happens in `ai_bridge`, mirror it into the vault through the generated notes and any relevant project notes.
"""


def build_conversation_note(vault_root: Path, bridge_root: Path, request_docs, reply_docs, claude_docs, antigravity_docs):
    return f"""---
note_type: tri-agent-conversation-stream
generated_by: sync_tri_agent_workspace.py
generated_at: {iso_now()}
---

# Tri-Agent Conversation Stream

This note is the durable index for bridge-mediated dialogue. The raw packets still live in `ai_bridge`; this note makes the recent cross-agent traffic visible from inside the vault.

## Mailbox Requests

{render_file_bullets(request_docs, bridge_root)}

## Mailbox Replies

{render_file_bullets(reply_docs, bridge_root)}

## Claude Relay Packets

{render_file_bullets(claude_docs, bridge_root)}

## Antigravity Relay Packets

{render_file_bullets(antigravity_docs, bridge_root)}

## Operating Rule

- Important reasoning should not remain only in these raw packet files.
- When a packet materially changes project direction, add or update a normal vault note in `04_Progress`, `03_Concepts`, or `10_Tasks`.
"""


def build_shared_intelligence_note(vault_root: Path, bridge_root: Path, entries):
    body = [
        "---",
        "note_type: tri-agent-shared-intelligence-feed",
        "generated_by: sync_tri_agent_workspace.py",
        f"generated_at: {iso_now()}",
        "---",
        "",
        "# Tri-Agent Shared Intelligence Feed",
        "",
        "This note surfaces the append-only shared intelligence stream that Codex, Claude Code, and Antigravity use to publish durable methods, routing changes, review patterns, and execution heuristics.",
        "",
        "## Canonical Sources",
        "",
        "- `C:/codex-data/ai_bridge/state/shared_intelligence_stream.jsonl`",
        "- `C:/codex-data/ai_bridge/shared_knowledge/Shared_Intelligence_Live_Feed.md`",
        "- `C:/codex-data/ai_bridge/shared_knowledge/Tri_Agent_Shared_Intelligence_Protocol.md`",
        "",
        "## Recent Entries",
        "",
    ]

    if not entries:
        body.append("- No shared intelligence entries yet.")
    else:
        for entry in entries:
            body.append(f"### {entry.get('title', 'Untitled entry')}")
            body.append("")
            body.append(f"- Author: {entry.get('author', '-')}")
            body.append(f"- Kind: {entry.get('kind', '-')}")
            body.append(f"- Created: {entry.get('created_at', '-')}")
            if entry.get("task_id"):
                body.append(f"- Task: {entry.get('task_id')}")
            if entry.get("tags"):
                body.append(f"- Tags: {', '.join(entry.get('tags', []))}")
            if entry.get("source_paths"):
                body.append(
                    f"- Source Paths: {' ; '.join(entry.get('source_paths', []))}"
                )
            body.append("")
            body.append("#### Summary")
            body.append("")
            body.append(entry.get("summary", "No summary provided."))
            if entry.get("details"):
                body.append("")
                body.append("#### Details")
                body.append("")
                body.append(entry.get("details"))
            body.append("")

    body.extend(
        [
            "## Operating Rule",
            "",
            "- Publish durable methods and reusable logic here instead of leaving them only in chat.",
            "- If a stream entry materially changes project direction, also update the relevant normal vault note.",
            "- Rerun the sync script after meaningful stream updates so this view stays current.",
        ]
    )
    return "\n".join(body)


def build_task_board(vault_root: Path, bridge_root: Path, tasks):
    queued = [task for task in tasks if task["status"] == "queued"]
    claimed = [task for task in tasks if task["status"] == "claimed"]
    done = [task for task in tasks if task["status"] in {"completed", "failed", "blocked", "partial"}]
    return f"""---
note_type: tri-agent-task-board
generated_by: sync_tri_agent_workspace.py
generated_at: {iso_now()}
---

# Tri-Agent Task Bus Board

## Queued

{render_task_rows(queued)}

## Claimed

{render_task_rows(claimed)}

## Recently Closed or Transitioned

{render_task_rows(done[:10])}

## Rule of Use

- Submit all new work through the shared task bus under `ai_bridge/tasks/inbox/`.
- Keep `planning_owner` and `execution_owner` explicit so Claude planning and Antigravity execution do not collapse into one ambiguous state.
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge-root")
    parser.add_argument("--vault-root")
    parser.add_argument("--config")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    assist_root = script_dir.parent
    project_root = assist_root.parent
    default_bridge_root = project_root.parent / "ai_bridge"
    default_config_path = assist_root / "config.json"
    fallback_config_path = assist_root / "config.example.json"
    config_path = (
        Path(args.config).resolve()
        if args.config
        else default_config_path if default_config_path.exists() else fallback_config_path
    )
    default_vault_root = configured_vault_root(config_path) or (assist_root / "vault")

    bridge_root = Path(args.bridge_root).resolve() if args.bridge_root else default_bridge_root
    vault_root = Path(args.vault_root).resolve() if args.vault_root else default_vault_root

    provider_state_path = bridge_root / "state" / "provider_state.json"
    provider_state = (
        load_json(provider_state_path) if provider_state_path.exists() else {"providers": {}}
    )

    tasks = scan_tasks(bridge_root)
    runs = scan_run_statuses(bridge_root)
    shared_docs = scan_markdown_files(bridge_root / "shared_knowledge")
    recent_bridge_docs = scan_markdown_files(bridge_root / "shared_knowledge", limit=10)
    recent_run_notes = scan_recursive_markdown_files(bridge_root / "runs", filename="summary.md", limit=10)
    request_docs = scan_packet_dir(bridge_root / "mailbox" / "requests")
    reply_docs = scan_packet_dir(bridge_root / "mailbox" / "replies")
    claude_docs = scan_packet_dir(bridge_root / "claude_packets")
    antigravity_docs = scan_packet_dir(bridge_root / "antigravity_packets")
    shared_intelligence_entries = scan_jsonl_entries(
        bridge_root / "state" / "shared_intelligence_stream.jsonl"
    )
    anchor_docs = [
        {"path": project_root / "AGENTS.md"},
        {"path": project_root / "SYSTEM_OVERVIEW.md"},
        {"path": project_root / "PROJECT_PROFILE.md"},
        {"path": project_root / "WORKING_CONSTITUTION.md"},
        {"path": assist_root / "README.md"},
    ]
    claude_memories = scan_claude_memories()

    write_text(
        vault_root / "00_System" / "05_Docs" / "Tri-Agent System Registry.md",
        build_registry_note(vault_root, bridge_root, provider_state),
    )
    write_text(
        vault_root / "03_Concepts" / "Tri-Agent Knowledge Index.md",
        build_knowledge_index(
            vault_root,
            bridge_root,
            project_root,
            shared_docs,
            recent_run_notes,
            anchor_docs,
            claude_memories,
        ),
    )
    write_text(
        vault_root / "04_Progress" / "tri-agent-control-plane-progress.md",
        build_progress_note(vault_root, bridge_root, tasks, runs, recent_bridge_docs),
    )
    write_text(
        vault_root / "09_Conversations" / "Tri-Agent" / "Tri-Agent Conversation Stream.md",
        build_conversation_note(
            vault_root,
            bridge_root,
            request_docs,
            reply_docs,
            claude_docs,
            antigravity_docs,
        ),
    )
    write_text(
        vault_root / "09_Conversations" / "Tri-Agent" / "_Index.md",
        "# Tri-Agent Conversation Index\n\n- [[Tri-Agent Conversation Stream]]\n",
    )
    write_text(
        vault_root / "03_Concepts" / "Tri-Agent Shared Intelligence Feed.md",
        build_shared_intelligence_note(vault_root, bridge_root, shared_intelligence_entries),
    )
    write_text(
        vault_root / "10_Tasks" / "Tri-Agent" / "Tri-Agent Task Bus Board.md",
        build_task_board(vault_root, bridge_root, tasks),
    )
    write_text(
        vault_root / "10_Tasks" / "Tri-Agent" / "_Index.md",
        "# Tri-Agent Task Index\n\n- [[Tri-Agent Task Bus Board]]\n- [[Tri-Agent Backlog]]\n",
    )
    write_text(
        vault_root / "03_Concepts" / "Claude Code Memory Index.md",
        build_claude_memory_note(claude_memories),
    )

    print(f"Synced tri-agent workspace into vault at {vault_root}")


if __name__ == "__main__":
    main()
