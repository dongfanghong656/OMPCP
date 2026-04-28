#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import discovery_to_zotero as discovery
import local_pdf_to_zotero as local_pdf
import zotero_to_vault
from path_naming import safe_slug


@dataclass
class CurationTarget:
    item_key: str
    title: str = ""
    add_tags: list[str] = field(default_factory=list)
    remove_tags: list[str] = field(default_factory=list)
    remove_tag_prefixes: list[str] = field(default_factory=list)
    add_collection_paths: list[str] = field(default_factory=list)
    remove_collection_paths: list[str] = field(default_factory=list)
    set_fields: dict[str, Any] = field(default_factory=dict)
    preserve_existing_tags: bool = True
    preserve_existing_collections: bool = True


@dataclass
class CollectionContext:
    cache: local_pdf.ZoteroLocalIndex
    path_by_key: dict[str, str] = field(default_factory=dict)
    key_by_path: dict[str, str] = field(default_factory=dict)


@dataclass
class CurationResult:
    item_key: str
    title: str = ""
    status: str = "pending"
    message: str = ""
    changed: bool = False
    patch_fields: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    collection_paths: list[str] = field(default_factory=list)


def normalize_text(value: Any) -> str:
    return discovery.normalize_whitespace(str(value))


def normalize_tag_list(value: Any) -> list[str]:
    return [normalize_text(tag) for tag in local_pdf.parse_string_list(value) if normalize_text(tag)]


def normalize_collection_path_list(value: Any) -> list[str]:
    paths: list[str] = []
    for path in local_pdf.parse_string_list(value):
        normalized = local_pdf.normalize_collection_path(path)
        if normalized:
            discovery.unique_append(paths, normalized)
    return paths


def first_nonempty_record(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, "", []):
            return value
    return None


def merge_field_updates(defaults: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    merged = dict(defaults)
    for key, value in (record or {}).items():
        merged[key] = value
    return merged


def build_target(record: dict[str, Any], defaults: dict[str, Any]) -> CurationTarget:
    merged_fields = merge_field_updates(defaults.get("set_fields", {}), record.get("set_fields", {}))
    item_key = normalize_text(first_nonempty_record(record, "item_key", "zotero_key", "key"))
    if not item_key:
        raise ValueError("Each curation target requires item_key, zotero_key, or key.")

    title = normalize_text(first_nonempty_record(record, "title", "paper_title")) or normalize_text(defaults.get("title", ""))
    add_tags = normalize_tag_list(first_nonempty_record(record, "add_tags", "tags", "tag_order") or defaults.get("add_tags") or defaults.get("tags", []))
    remove_tags = normalize_tag_list(first_nonempty_record(record, "remove_tags") or defaults.get("remove_tags", []))
    remove_tag_prefixes = normalize_tag_list(first_nonempty_record(record, "remove_tag_prefixes") or defaults.get("remove_tag_prefixes", []))
    add_collection_paths = normalize_collection_path_list(
        first_nonempty_record(record, "add_collection_paths", "collection_paths", "collections", "add_collections")
        or defaults.get("add_collection_paths")
        or defaults.get("collection_paths")
        or defaults.get("collections", [])
    )
    remove_collection_paths = normalize_collection_path_list(
        first_nonempty_record(record, "remove_collection_paths", "remove_collections")
        or defaults.get("remove_collection_paths")
        or defaults.get("remove_collections", [])
    )

    preserve_existing_tags = bool(record.get("preserve_existing_tags", defaults.get("preserve_existing_tags", True)))
    preserve_existing_collections = bool(
        record.get("preserve_existing_collections", defaults.get("preserve_existing_collections", True))
    )

    return CurationTarget(
        item_key=item_key,
        title=title,
        add_tags=add_tags,
        remove_tags=remove_tags,
        remove_tag_prefixes=remove_tag_prefixes,
        add_collection_paths=add_collection_paths,
        remove_collection_paths=remove_collection_paths,
        set_fields=merged_fields,
        preserve_existing_tags=preserve_existing_tags,
        preserve_existing_collections=preserve_existing_collections,
    )


def load_targets(path: Path) -> list[CurationTarget]:
    payload = discovery.load_json(path)
    defaults: dict[str, Any] = {}
    records: list[dict[str, Any]]
    if isinstance(payload, list):
        records = payload
    else:
        defaults = payload.get("defaults") or {}
        records = first_nonempty_record(payload, "items", "targets", "records", "entries") or []
    return [build_target(record, defaults) for record in records if isinstance(record, dict)]


def call_json(config: dict[str, Any], url: str, method: str = "GET", data: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[Any, dict[str, str]]:
    last_error: Exception | None = None
    effective_headers = headers or local_pdf.zotero_api_headers(config, include_json=False)
    for attempt in range(4):
        try:
            return local_pdf.http_json(url, method=method, headers=effective_headers, data=data, timeout=90)
        except Exception as exc:  # pragma: no cover - exercised in live runs
            last_error = exc
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise last_error or RuntimeError(f"Failed request for {url}")


def call_request(
    config: dict[str, Any],
    url: str,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    last_error: Exception | None = None
    effective_headers = headers or local_pdf.zotero_api_headers(config, include_json=False)
    for attempt in range(4):
        try:
            return local_pdf.http_request(url, method=method, headers=effective_headers, data=data, timeout=90)
        except Exception as exc:  # pragma: no cover - exercised in live runs
            last_error = exc
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise last_error or RuntimeError(f"Failed request for {url}")


def load_collection_context(config: dict[str, Any], max_items: int = 1000) -> CollectionContext:
    sqlite_raw = normalize_text((config.get("zotero") or {}).get("sqlite_path", ""))
    sqlite_path = Path(sqlite_raw) if sqlite_raw else None
    cache = local_pdf.load_zotero_local_index(sqlite_path) if sqlite_path else local_pdf.ZoteroLocalIndex()
    path_by_key = zotero_to_vault.load_collection_path_map(sqlite_path) if sqlite_path else {}
    try:
        remote_map = zotero_to_vault.fetch_remote_collection_path_map(config, max_items=max_items)
        for key, path in remote_map.items():
            if path:
                path_by_key[key] = path
    except Exception:
        pass

    key_by_path: dict[str, str] = {}
    for key, path in path_by_key.items():
        normalized_path = local_pdf.normalize_collection_path(path)
        if normalized_path and normalized_path not in key_by_path:
            key_by_path[normalized_path] = key

    for key, path in sorted(path_by_key.items(), key=lambda item: (item[1].count("/"), item[1], item[0])):
        normalized_path = local_pdf.normalize_collection_path(path)
        if not normalized_path:
            continue
        parent_path, _, name = normalized_path.rpartition("/")
        parent_key = key_by_path.get(parent_path, "")
        cache.collections_by_parent_and_name[(parent_key, name)] = key

    return CollectionContext(cache=cache, path_by_key=path_by_key, key_by_path=key_by_path)


def ensure_collection_keys(
    paths: list[str],
    context: CollectionContext,
    config: dict[str, Any],
    write_zotero: bool,
) -> list[str]:
    keys: list[str] = []
    for path in paths:
        normalized_path = local_pdf.normalize_collection_path(path)
        if not normalized_path:
            continue
        key = context.key_by_path.get(normalized_path, "")
        if not key:
            key = local_pdf.ensure_collection_path(normalized_path, context.cache, config, write_zotero)
        if not key:
            raise RuntimeError(f"Collection path could not be resolved: {normalized_path}")
        context.key_by_path[normalized_path] = key
        context.path_by_key[key] = normalized_path
        discovery.unique_append(keys, key)
    return keys


def merge_tags(current_tags: list[str], target: CurationTarget) -> list[str]:
    remove_set = {normalize_text(tag) for tag in target.remove_tags if normalize_text(tag)}
    remove_prefixes = [normalize_text(prefix) for prefix in target.remove_tag_prefixes if normalize_text(prefix)]
    merged: list[str] = []
    seen: set[str] = set()

    def should_drop(tag: str) -> bool:
        normalized = normalize_text(tag)
        if not normalized:
            return True
        if normalized in remove_set:
            return True
        return any(normalized.startswith(prefix) for prefix in remove_prefixes)

    for tag in target.add_tags:
        normalized = normalize_text(tag)
        if should_drop(normalized) or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(normalized)
    if target.preserve_existing_tags:
        for tag in current_tags:
            normalized = normalize_text(tag)
            if should_drop(normalized) or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
    return merged


def merge_collection_keys(
    current_keys: list[str],
    add_keys: list[str],
    target: CurationTarget,
    context: CollectionContext,
) -> list[str]:
    remove_paths = {local_pdf.normalize_collection_path(path) for path in target.remove_collection_paths if local_pdf.normalize_collection_path(path)}
    merged: list[str] = []
    seen_paths: set[str] = set()
    seen_keys: set[str] = set()
    for key in add_keys:
        normalized_key = normalize_text(key)
        if normalized_key:
            path = local_pdf.normalize_collection_path(context.path_by_key.get(normalized_key, ""))
            if path:
                if path in seen_paths:
                    continue
                seen_paths.add(path)
            elif normalized_key in seen_keys:
                continue
            seen_keys.add(normalized_key)
            merged.append(normalized_key)
    if target.preserve_existing_collections:
        for key in current_keys:
            normalized_key = normalize_text(key)
            if not normalized_key:
                continue
            path = local_pdf.normalize_collection_path(context.path_by_key.get(normalized_key, ""))
            if path and path in remove_paths:
                continue
            if path:
                if path in seen_paths:
                    continue
                seen_paths.add(path)
            elif normalized_key in seen_keys:
                continue
            seen_keys.add(normalized_key)
            merged.append(normalized_key)
    return merged


def build_patch(
    current_item: dict[str, Any],
    target: CurationTarget,
    desired_collection_keys: list[str],
    context: CollectionContext,
) -> tuple[dict[str, Any], list[str], list[str]]:
    current_tags = [normalize_text(tag.get("tag", "")) for tag in current_item.get("tags", []) if isinstance(tag, dict) and normalize_text(tag.get("tag", ""))]
    current_collections = [normalize_text(key) for key in current_item.get("collections", []) if normalize_text(key)]

    merged_tags = merge_tags(current_tags, target)
    merged_collections = merge_collection_keys(current_collections, desired_collection_keys, target, context)

    patch: dict[str, Any] = {}
    if merged_tags != current_tags:
        patch["tags"] = [{"tag": tag} for tag in merged_tags]
    if merged_collections != current_collections:
        patch["collections"] = merged_collections

    for field_name, value in target.set_fields.items():
        if current_item.get(field_name) != value:
            patch[field_name] = value

    return patch, merged_tags, merged_collections


def fetch_remote_item(config: dict[str, Any], item_key: str) -> dict[str, Any]:
    prefix = discovery.zotero_library_prefix(config)
    url = f"{local_pdf.ZOTERO_API_BASE}/{prefix}/items/{item_key}"
    payload, _ = call_json(config, url)
    return payload.get("data", {})


def apply_target(
    target: CurationTarget,
    context: CollectionContext,
    config: dict[str, Any],
    write_zotero: bool,
) -> CurationResult:
    current_item = fetch_remote_item(config, target.item_key)
    title = normalize_text(current_item.get("title", "")) or target.title or target.item_key
    desired_collection_keys = ensure_collection_keys(target.add_collection_paths, context, config, write_zotero)
    patch, merged_tags, merged_collections = build_patch(current_item, target, desired_collection_keys, context)

    result = CurationResult(item_key=target.item_key, title=title, patch_fields=sorted(patch))
    if not patch:
        result.status = "unchanged"
        result.message = "Item already matched the requested curation state."
        result.tags = [normalize_text(tag.get("tag", "")) for tag in current_item.get("tags", []) if isinstance(tag, dict) and normalize_text(tag.get("tag", ""))]
        result.collection_paths = [context.path_by_key.get(key, key) for key in current_item.get("collections", []) if normalize_text(key)]
        return result

    result.changed = True
    if write_zotero:
        prefix = discovery.zotero_library_prefix(config)
        url = f"{local_pdf.ZOTERO_API_BASE}/{prefix}/items/{target.item_key}"
        headers = local_pdf.zotero_api_headers(
            config,
            include_json=True,
            extra={"If-Unmodified-Since-Version": str(current_item.get("version", 0))},
        )
        call_request(config, url, method="PATCH", data=json.dumps(patch).encode("utf-8"), headers=headers)
        current_item = fetch_remote_item(config, target.item_key)
        result.status = "updated"
        result.message = f"Updated remote item {target.item_key}."
    else:
        result.status = "dry-run"
        result.message = "Patch prepared but not written to Zotero."
        current_item = dict(current_item)
        current_item["tags"] = [{"tag": tag} for tag in merged_tags]
        current_item["collections"] = merged_collections
        for field_name, value in target.set_fields.items():
            current_item[field_name] = value

    result.tags = [normalize_text(tag.get("tag", "")) for tag in current_item.get("tags", []) if isinstance(tag, dict) and normalize_text(tag.get("tag", ""))]
    result.collection_paths = [context.path_by_key.get(normalize_text(key), normalize_text(key)) for key in current_item.get("collections", []) if normalize_text(key)]
    return result


def resolve_output_root(config: dict[str, Any], output_root: str) -> Path:
    return Path(output_root) if output_root else Path(config["output_root"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply repeatable Zotero item curation rules to specific items.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--curation-file", required=True)
    parser.add_argument("--run-label", default="zotero-curation")
    parser.add_argument("--output-root", default="")
    parser.add_argument("--max-collections", type=int, default=1000)
    parser.add_argument("--write-zotero", action="store_true")
    return parser


def write_run_report(path: Path, run_id: str, results: list[CurationResult], write_zotero: bool) -> None:
    lines = [
        "# Zotero Curation Run",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Mode: `{'write-zotero' if write_zotero else 'dry-run'}`",
        f"- Targets: {len(results)}",
        f"- Updated: {sum(1 for result in results if result.status == 'updated')}",
        f"- Unchanged: {sum(1 for result in results if result.status == 'unchanged')}",
        f"- Dry run only: {sum(1 for result in results if result.status == 'dry-run')}",
        f"- Failed: {sum(1 for result in results if result.status == 'failed')}",
        "",
        "## Items",
        "",
    ]
    if not results:
        lines.append("- None")
    else:
        for result in results:
            collections = ", ".join(result.collection_paths) if result.collection_paths else "none"
            tags = ", ".join(result.tags) if result.tags else "none"
            fields = ", ".join(result.patch_fields) if result.patch_fields else "none"
            lines.extend(
                [
                    f"- {result.title or '[untitled]'} | `{result.item_key}` | {result.status} | changed: `{str(result.changed).lower()}`",
                    f"  - Patch fields: {fields}",
                    f"  - Collections: {collections}",
                    f"  - Tags: {tags}",
                    f"  - Message: {result.message or 'n/a'}",
                ]
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config = discovery.load_json(Path(args.config))
    targets = load_targets(Path(args.curation_file))
    output_root = resolve_output_root(config, args.output_root)
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(args.run_label)}"
    run_dir = output_root / "zotero-curation" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    context = load_collection_context(config, max_items=args.max_collections)
    results: list[CurationResult] = []
    for target in targets:
        try:
            results.append(apply_target(target, context, config, args.write_zotero))
        except Exception as exc:
            results.append(
                CurationResult(
                    item_key=target.item_key,
                    title=target.title or target.item_key,
                    status="failed",
                    message=str(exc),
                )
            )

    payload = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "write-zotero" if args.write_zotero else "dry-run",
        "curation_file": str(Path(args.curation_file)),
        "results": [asdict(result) for result in results],
    }
    (run_dir / "run.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_run_report(run_dir / "run.md", run_id, results, args.write_zotero)
    print(str(run_dir / "run.md"))


if __name__ == "__main__":
    main()
