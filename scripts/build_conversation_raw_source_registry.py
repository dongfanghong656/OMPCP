#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import import_chatgpt_backup_to_vault as backupmod


COPY_SUFFIX_RE = re.compile(r" \(\d+\)(?=\.)")
TITLE_NORMALIZE_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


@dataclass(frozen=True)
class RecordProfile:
    title: str
    title_norm: str
    conversation_id: str
    source_entry: str
    provider: str
    source_kind: str
    created_at: float | None
    updated_at: float | None
    messages: tuple[tuple[str, str], ...]
    exact_hash: str


@dataclass
class SourceProfile:
    path: Path
    ai_type: str
    providers: tuple[str, ...]
    source_kinds: tuple[str, ...]
    records: list[RecordProfile]
    conversation_count: int
    created_min: float | None
    created_max: float | None
    total_message_chars: int
    exact_hash: str
    imported_manifest_relpath: str | None
    imported_corpus_name: str | None

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()


def normalize_message_text(text: str) -> str:
    value = text.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_title(text: str) -> str:
    return TITLE_NORMALIZE_RE.sub("", text.lower())


def make_record_profile(record: backupmod.ConversationRecord) -> RecordProfile:
    messages = tuple(
        (message.role, normalize_message_text(message.text))
        for message in record.messages
        if normalize_message_text(message.text)
    )
    payload = json.dumps(
        {
            "provider": record.provider,
            "source_kind": record.source_kind,
            "title_norm": normalize_title(record.title),
            "messages": messages,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return RecordProfile(
        title=record.title,
        title_norm=normalize_title(record.title),
        conversation_id=record.conversation_id,
        source_entry=record.source_entry,
        provider=record.provider,
        source_kind=record.source_kind,
        created_at=record.created_at,
        updated_at=record.updated_at,
        messages=messages,
        exact_hash=hashlib.sha1(payload.encode("utf-8")).hexdigest(),
    )


def classify_ai_type(providers: list[str], source_kinds: list[str]) -> str:
    ordered = sorted(dict.fromkeys(providers))
    if len(ordered) == 1:
        return ordered[0]
    if "memo-text-export" in source_kinds:
        return "Chat Memo 合集包"
    return "多平台来源"


def source_preference_key(path: Path) -> tuple[int, int, int, str]:
    copy_penalty = 1 if COPY_SUFFIX_RE.search(path.name) else 0
    extension_rank = {".zip": 0, ".json": 1, ".txt": 2, ".md": 3}.get(path.suffix.lower(), 9)
    return (copy_penalty, extension_rank, len(path.name), path.name.lower())


def timestamp_bounds(records: list[RecordProfile]) -> tuple[float | None, float | None]:
    starts = [item.created_at for item in records if item.created_at is not None]
    ends = [item.updated_at for item in records if item.updated_at is not None]
    return (min(starts) if starts else None, max(ends) if ends else None)


def build_manifest_lookup(vault_root: Path, attachment_folder: str) -> dict[str, tuple[str, str]]:
    lookup: dict[str, tuple[str, str]] = {}
    attachments_root = vault_root / attachment_folder
    if not attachments_root.exists():
        return lookup
    for manifest_path in attachments_root.rglob("manifest.json"):
        try:
            payload = backupmod.load_json(manifest_path)
        except (json.JSONDecodeError, OSError):
            continue
        backup_path = payload.get("backup_path")
        corpus_name = payload.get("corpus_name")
        if not isinstance(backup_path, str) or not isinstance(corpus_name, str):
            continue
        relpath = backupmod.make_forward_slashes(manifest_path.relative_to(vault_root))
        lookup[backup_path.lower()] = (relpath, corpus_name)
    return lookup


def collect_source_profiles(
    scan_dir: Path,
    manifest_lookup: dict[str, tuple[str, str]],
) -> list[SourceProfile]:
    profiles: list[SourceProfile] = []
    for source_path in backupmod.discover_conversation_sources(scan_dir):
        records = sorted(backupmod.collect_backup_records(source_path), key=backupmod.record_sort_key)
        record_profiles = [make_record_profile(record) for record in records]
        created_min, created_max = timestamp_bounds(record_profiles)
        providers = tuple(sorted({item.provider for item in record_profiles}))
        source_kinds = tuple(sorted({item.source_kind for item in record_profiles}))
        exact_payload = json.dumps(
            [item.exact_hash for item in record_profiles],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        manifest_entry = manifest_lookup.get(backupmod.make_forward_slashes(source_path).lower())
        profiles.append(
            SourceProfile(
                path=source_path,
        ai_type=classify_ai_type(list(providers), list(source_kinds)),
                providers=providers,
                source_kinds=source_kinds,
                records=record_profiles,
                conversation_count=len(record_profiles),
                created_min=created_min,
                created_max=created_max,
                total_message_chars=sum(len(message[1]) for item in record_profiles for message in item.messages),
                exact_hash=hashlib.sha1(exact_payload.encode("utf-8")).hexdigest(),
                imported_manifest_relpath=manifest_entry[0] if manifest_entry else None,
                imported_corpus_name=manifest_entry[1] if manifest_entry else None,
            )
        )
    return profiles


def exact_record_match(small: RecordProfile, large: RecordProfile) -> bool:
    if small.exact_hash == large.exact_hash:
        return True
    if small.provider != large.provider or small.source_kind != large.source_kind:
        return False
    if small.conversation_id and large.conversation_id and small.conversation_id == large.conversation_id:
        pass
    elif small.title_norm != large.title_norm:
        return False
    if len(small.messages) > len(large.messages):
        return False
    return small.messages == large.messages[: len(small.messages)]


def source_is_covered_by(small: SourceProfile, large: SourceProfile) -> bool:
    if small.path == large.path:
        return False
    if small.conversation_count > large.conversation_count:
        return False
    if not set(small.providers).issubset(set(large.providers)):
        return False
    if not set(small.source_kinds).issubset(set(large.source_kinds)):
        return False
    strict = small.conversation_count < large.conversation_count
    for small_record in small.records:
        match_found = False
        for large_record in large.records:
            if exact_record_match(small_record, large_record):
                match_found = True
                if small_record.exact_hash != large_record.exact_hash:
                    strict = True
                break
        if not match_found:
            return False
    return strict


def choose_best_cover(source: SourceProfile, candidates: list[SourceProfile]) -> SourceProfile:
    return sorted(
        candidates,
        key=lambda item: (
            item.conversation_count,
            item.total_message_chars,
            source_preference_key(item.path),
        ),
    )[0]


def build_registry(profiles: list[SourceProfile], scan_dir: Path) -> dict:
    exact_groups: dict[str, list[SourceProfile]] = defaultdict(list)
    for profile in profiles:
        exact_groups[profile.exact_hash].append(profile)

    states: dict[str, dict[str, str | None]] = {}
    canonical_pool: list[SourceProfile] = []
    exact_group_rows: list[dict] = []
    for members in exact_groups.values():
        sorted_members = sorted(members, key=lambda item: source_preference_key(item.path))
        keep = sorted_members[0]
        canonical_pool.append(keep)
        states[str(keep.path)] = {"state": "canonical", "target": None}
        if len(sorted_members) > 1:
            exact_group_rows.append(
                {
                    "canonical": backupmod.make_forward_slashes(keep.path),
                    "members": [backupmod.make_forward_slashes(item.path) for item in sorted_members],
                }
            )
        for duplicate in sorted_members[1:]:
            states[str(duplicate.path)] = {
                "state": "duplicate_of",
                "target": backupmod.make_forward_slashes(keep.path),
            }

    direct_cover: dict[str, str] = {}
    for profile in canonical_pool:
        cover_candidates = [candidate for candidate in canonical_pool if source_is_covered_by(profile, candidate)]
        if cover_candidates:
            best_cover = choose_best_cover(profile, cover_candidates)
            direct_cover[str(profile.path)] = backupmod.make_forward_slashes(best_cover.path)

    for path_str, target in direct_cover.items():
        states[path_str] = {"state": "covered_by", "target": target}

    def resolve_final_target(path_str: str) -> str:
        seen: set[str] = set()
        current = path_str
        while True:
            state = states.get(current, {"state": "canonical", "target": None})
            if state["state"] == "canonical" or not state["target"]:
                return backupmod.make_forward_slashes(Path(current))
            if current in seen:
                return state["target"]
            seen.add(current)
            current = str(Path(state["target"]))

    profile_by_path = {backupmod.make_forward_slashes(item.path): item for item in profiles}
    canonical_profiles: list[SourceProfile] = []
    merged_members: dict[str, list[dict[str, str]]] = defaultdict(list)
    cover_relations: list[dict[str, str]] = []
    for profile in profiles:
        path_key = backupmod.make_forward_slashes(profile.path)
        state = states[str(profile.path)]
        final_target = resolve_final_target(str(profile.path))
        if state["state"] == "canonical":
            canonical_profiles.append(profile)
        else:
            relation = {
                "path": path_key,
                "state": str(state["state"]),
                "direct_target": str(state["target"]),
                "final_target": final_target,
            }
            if state["state"] == "covered_by":
                cover_relations.append(relation)
            merged_members[final_target].append(relation)

    canonical_profiles.sort(key=lambda item: (item.ai_type, item.created_min or 0, item.path.name.lower()))

    raw_counts = Counter(item.ai_type for item in profiles)
    canonical_counts = Counter(item.ai_type for item in canonical_profiles)

    source_rows = []
    for profile in profiles:
        path_key = backupmod.make_forward_slashes(profile.path)
        state = states[str(profile.path)]
        source_rows.append(
            {
                "path": path_key,
                "name": profile.path.name,
                "extension": profile.extension,
                "ai_type": profile.ai_type,
                "providers": list(profile.providers),
                "source_kinds": list(profile.source_kinds),
                "conversation_count": profile.conversation_count,
                "created_min": backupmod.timestamp_to_display(profile.created_min),
                "created_max": backupmod.timestamp_to_display(profile.created_max),
                "imported_manifest_relpath": profile.imported_manifest_relpath,
                "imported_corpus_name": profile.imported_corpus_name,
                "status": state["state"],
                "direct_target": state["target"],
                "final_target": resolve_final_target(str(profile.path)),
            }
        )

    canonical_rows = []
    for profile in canonical_profiles:
        path_key = backupmod.make_forward_slashes(profile.path)
        canonical_rows.append(
            {
                "path": path_key,
                "name": profile.path.name,
                "extension": profile.extension,
                "ai_type": profile.ai_type,
                "providers": list(profile.providers),
                "source_kinds": list(profile.source_kinds),
                "conversation_count": profile.conversation_count,
                "created_min": backupmod.timestamp_to_display(profile.created_min),
                "created_max": backupmod.timestamp_to_display(profile.created_max),
                "imported_manifest_relpath": profile.imported_manifest_relpath,
                "imported_corpus_name": profile.imported_corpus_name,
                "merged_members": merged_members.get(path_key, []),
            }
        )

    return {
        "generated_at": backupmod.current_display_timestamp(),
        "scan_dir": backupmod.make_forward_slashes(scan_dir),
        "raw_source_count": len(profiles),
        "canonical_source_count": len(canonical_profiles),
        "exact_duplicate_group_count": len(exact_group_rows),
        "exact_duplicate_file_count": sum(len(group["members"]) - 1 for group in exact_group_rows),
        "covered_file_count": len(cover_relations),
        "ai_type_summary": [
            {
                "ai_type": ai_type,
                "raw_count": raw_counts[ai_type],
                "canonical_count": canonical_counts.get(ai_type, 0),
            }
            for ai_type in sorted(raw_counts)
        ],
        "exact_duplicate_groups": exact_group_rows,
        "covered_relations": cover_relations,
        "canonical_sources": canonical_rows,
        "all_sources": sorted(source_rows, key=lambda item: item["path"].lower()),
    }


def manifest_link(relpath: str | None) -> str:
    if not relpath:
        return "`not imported`"
    return f"[[{relpath}|manifest.json]]"


def build_registry_note(payload: dict, vault_root: Path, note_path: Path, json_relpath: str) -> str:
    frontmatter = backupmod.yaml_frontmatter(
        {
            "note_type": "conversation-raw-source-registry",
            "generated_by": "build_conversation_raw_source_registry.py",
            "generated_at": payload["generated_at"],
            "scan_dir": payload["scan_dir"],
            "raw_source_count": payload["raw_source_count"],
            "canonical_source_count": payload["canonical_source_count"],
        }
    )
    lines = [
        frontmatter,
        "",
        "# 原始对话文件归并总表",
        "",
        "这份总表只整理原始来源文件，不移动 Downloads 中的原文件。这里的“归并”表示建立 canonical 原档、标注完全重复文件，以及标注被更完整版本覆盖的原档。",
        "对于 `chat-memo` / `下载.zip` 这类聚合包，不把外层压缩包当成单一 AI 平台；它们会标记为 `Chat Memo 合集包`，实际平台写在 `Contained platforms`。",
        "",
        f"- 生成时间: {payload['generated_at']}",
        f"- 扫描目录: `{payload['scan_dir']}`",
        f"- 原始对话源文件: {payload['raw_source_count']}",
        f"- Canonical 原档: {payload['canonical_source_count']}",
        f"- 完全重复组: {payload['exact_duplicate_group_count']} 组 / {payload['exact_duplicate_file_count']} 个冗余文件",
        f"- 被更完整版本覆盖: {payload['covered_file_count']} 个文件",
        f"- JSON Manifest: `08_Attachments/{json_relpath}`",
        "",
        "## 来源分类统计",
        "",
        "| 来源分类 | 原始文件 | Canonical |",
        "| --- | ---: | ---: |",
    ]
    for row in payload["ai_type_summary"]:
        lines.append(f"| {row['ai_type']} | {row['raw_count']} | {row['canonical_count']} |")

    lines.extend(["", "## 完全重复文件", ""])
    if not payload["exact_duplicate_groups"]:
        lines.append("- None.")
    else:
        for group in payload["exact_duplicate_groups"]:
            canonical_path = group["canonical"]
            lines.append(f"### {Path(canonical_path).name}")
            lines.append("")
            lines.append(f"- Canonical: `{canonical_path}`")
            for member in group["members"]:
                if member == canonical_path:
                    continue
                lines.append(f"- Duplicate: `{member}`")
            lines.append("")

    lines.extend(["## 被更完整版本覆盖", ""])
    if not payload["covered_relations"]:
        lines.append("- None.")
    else:
        for relation in sorted(payload["covered_relations"], key=lambda item: item["path"].lower()):
            lines.append(f"- `{relation['path']}` -> `{relation['final_target']}`")
        lines.append("")

    lines.extend(["## Canonical 原档库", ""])
    canonical_by_ai: dict[str, list[dict]] = defaultdict(list)
    for row in payload["canonical_sources"]:
        canonical_by_ai[row["ai_type"]].append(row)

    for ai_type in sorted(canonical_by_ai):
        lines.extend([f"## {ai_type}", ""])
        for row in canonical_by_ai[ai_type]:
            lines.append(f"### {row['name']}")
            lines.append("")
            lines.append(f"- Path: `{row['path']}`")
            if len(row.get("providers") or []) > 1:
                lines.append(f"- Contained platforms: `{', '.join(row['providers'])}`")
            lines.append(f"- Source kinds: `{', '.join(row['source_kinds'])}`")
            lines.append(f"- Conversations: {row['conversation_count']}")
            lines.append(f"- Date range: {row['created_min']} -> {row['created_max']}")
            lines.append(f"- Imported corpus: `{row['imported_corpus_name'] or 'unknown'}`")
            lines.append(f"- Imported manifest: {manifest_link(row['imported_manifest_relpath'])}")
            merged = row.get("merged_members") or []
            if merged:
                lines.append("- Merged originals:")
                for member in sorted(merged, key=lambda item: item["path"].lower()):
                    label = "duplicate" if member["state"] == "duplicate_of" else "covered"
                    lines.append(f"  - `{member['path']}` ({label})")
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def append_registry_link(index_path: Path, relpath: str) -> None:
    line = f"- [[{relpath}|原始对话文件归并总表]]"
    content = index_path.read_text(encoding="utf-8") if index_path.exists() else "# 会话索引\n\n"
    if line in content:
        return
    if "## 主题入口" in content:
        content = content.rstrip() + "\n" + line + "\n"
    else:
        content = content.rstrip() + "\n\n## 主题入口\n\n" + line + "\n"
    backupmod.write_text(index_path, content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a deduplicated registry for raw conversation source files.")
    parser.add_argument("--config", required=True, help="Path to oct-research-assist config.json")
    parser.add_argument("--scan-dir", help="Directory to scan. Defaults to the user's Downloads folder.")
    parser.add_argument("--vault-root", help="Optional override for vault root.")
    parser.add_argument(
        "--prefer-config-vault-root",
        action="store_true",
        help="Use config.json vault_root instead of the repo-local workspace vault.",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config = backupmod.load_json(config_path)
    configured_vault = backupmod.resolve_path(config.get("vault_root"), config_path.parent)
    workspace_vault = backupmod.resolve_workspace_vault(config_path)
    if args.vault_root:
        vault_root = Path(args.vault_root).resolve()
    elif args.prefer_config_vault_root:
        if not configured_vault:
            raise SystemExit("vault_root is missing from config.json and --prefer-config-vault-root was requested.")
        vault_root = configured_vault
    else:
        vault_root = workspace_vault

    scan_dir = Path(args.scan_dir).resolve() if args.scan_dir else Path.home() / "Downloads"
    if not scan_dir.is_dir():
        raise SystemExit(f"Scan directory not found: {scan_dir}")

    obsidian = config.get("obsidian", {})
    conversation_folder = obsidian.get("conversation_folder", "09_Conversations")
    attachment_folder = obsidian.get("attachment_folder", "08_Attachments")

    manifest_lookup = build_manifest_lookup(vault_root, attachment_folder)
    profiles = collect_source_profiles(scan_dir, manifest_lookup)
    if not profiles:
        raise SystemExit(f"No supported conversation source files found in: {scan_dir}")

    payload = build_registry(profiles, scan_dir)
    note_path = vault_root / conversation_folder / "原始对话文件归并总表.md"
    json_path = vault_root / attachment_folder / "conversation-archive" / "raw-source-registry" / "raw-source-registry.json"
    json_relpath = backupmod.make_forward_slashes(json_path.relative_to(vault_root / attachment_folder))
    backupmod.write_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2))
    backupmod.write_text(note_path, build_registry_note(payload, vault_root, note_path, json_relpath))
    append_registry_link(vault_root / conversation_folder / "_Index.md", backupmod.make_forward_slashes(note_path.relative_to(vault_root)))

    print(
        json.dumps(
            {
                "scan_dir": backupmod.make_forward_slashes(scan_dir),
                "vault_root": backupmod.make_forward_slashes(vault_root),
                "raw_source_count": payload["raw_source_count"],
                "canonical_source_count": payload["canonical_source_count"],
                "exact_duplicate_group_count": payload["exact_duplicate_group_count"],
                "covered_file_count": payload["covered_file_count"],
                "note_path": backupmod.make_forward_slashes(note_path),
                "json_path": backupmod.make_forward_slashes(json_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
