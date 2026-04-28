#!/usr/bin/env python
import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_parent(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


def scalar(conn, query: str):
    return conn.execute(query).fetchone()[0]


def rows(conn, query: str, limit: int):
    return conn.execute(query, {"limit": limit}).fetchall()


def title_query():
    return """
    SELECT
        i.itemID,
        COALESCE(MAX(CASE WHEN f.fieldName = 'title' THEN v.value END), '[untitled]') AS title,
        it.typeName,
        i.dateAdded
    FROM items i
    LEFT JOIN deletedItems di ON i.itemID = di.itemID
    LEFT JOIN itemData d ON i.itemID = d.itemID
    LEFT JOIN fieldsCombined f ON d.fieldID = f.fieldID
    LEFT JOIN itemDataValues v ON d.valueID = v.valueID
    LEFT JOIN itemTypesCombined it ON i.itemTypeID = it.itemTypeID
    WHERE di.itemID IS NULL
      AND it.typeName NOT IN ('attachment', 'note', 'annotation')
    GROUP BY i.itemID, it.typeName, i.dateAdded
    ORDER BY i.dateAdded DESC
    LIMIT :limit
    """


def collection_query():
    return """
    SELECT
        c.collectionName,
        COUNT(ci.itemID) AS itemCount
    FROM collections c
    LEFT JOIN collectionItems ci ON c.collectionID = ci.collectionID
    GROUP BY c.collectionID, c.collectionName
    ORDER BY itemCount DESC, c.collectionName ASC
    LIMIT :limit
    """


def tag_query():
    return """
    SELECT
        t.name,
        COUNT(it.itemID) AS itemCount
    FROM tags t
    JOIN itemTags it ON t.tagID = it.tagID
    GROUP BY t.tagID, t.name
    ORDER BY itemCount DESC, t.name ASC
    LIMIT :limit
    """


def format_list(title: str, items, formatter):
    lines = [f"## {title}", ""]
    if not items:
        lines.append("- None")
    else:
        for item in items:
            lines.append(f"- {formatter(item)}")
    lines.append("")
    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--top-n", type=int, default=15)
    args = parser.parse_args()

    config = load_json(Path(args.config))
    zotero_cfg = config["zotero"]
    sqlite_path = Path(zotero_cfg["sqlite_path"])
    if not sqlite_path.exists():
        raise SystemExit(f"Missing Zotero sqlite file: {sqlite_path}")

    vault_root = Path(config["vault_root"])
    obs = config["obsidian"]
    report_root = Path(config["output_root"])
    note_path = vault_root / obs["zotero_folder"] / "library-health.md"
    index_path = vault_root / obs["zotero_folder"] / "_Index.md"
    json_path = report_root / "zotero-library-summary.json"
    ensure_parent(note_path)
    ensure_parent(json_path)

    conn = sqlite3.connect(f"file:{sqlite_path.as_posix()}?mode=ro", uri=True)
    try:
        totals = {
            "all_items": scalar(conn, "SELECT COUNT(*) FROM items"),
            "deleted_items": scalar(conn, "SELECT COUNT(*) FROM deletedItems"),
            "collections": scalar(conn, "SELECT COUNT(*) FROM collections"),
            "tags": scalar(conn, "SELECT COUNT(*) FROM tags"),
            "attachment_items": scalar(conn, "SELECT COUNT(*) FROM itemAttachments"),
            "note_items": scalar(conn, "SELECT COUNT(*) FROM itemNotes"),
            "creators": scalar(conn, "SELECT COUNT(*) FROM creators"),
        }
        totals["active_items"] = totals["all_items"] - totals["deleted_items"]

        recent_items = rows(conn, title_query(), args.top_n)
        largest_collections = rows(conn, collection_query(), args.top_n)
        top_tags = rows(conn, tag_query(), args.top_n)
    finally:
        conn.close()

    storage_dir = sqlite_path.parent / "storage"
    storage_dirs = 0
    if storage_dir.exists():
        storage_dirs = sum(1 for child in storage_dir.iterdir() if child.is_dir())

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sqlite_path": str(sqlite_path),
        "storage_path": str(storage_dir),
        "storage_directories": storage_dirs,
        "totals": totals,
        "recent_items": [
            {
                "item_id": item_id,
                "title": title,
                "type": item_type,
                "date_added": date_added,
            }
            for item_id, title, item_type, date_added in recent_items
        ],
        "largest_collections": [
            {"collection_name": name, "item_count": count}
            for name, count in largest_collections
        ],
        "top_tags": [{"tag": name, "item_count": count} for name, count in top_tags],
    }

    lines = [
        "# Zotero Library Health",
        "",
        f"- Generated: {summary['generated_at']}",
        f"- SQLite path: `{sqlite_path}`",
        f"- Storage path: `{storage_dir}`",
        f"- Storage directories: {storage_dirs}",
        "",
        "## Totals",
        "",
        f"- Active items: {totals['active_items']}",
        f"- Deleted items: {totals['deleted_items']}",
        f"- Collections: {totals['collections']}",
        f"- Tags: {totals['tags']}",
        f"- Attachment items: {totals['attachment_items']}",
        f"- Note items: {totals['note_items']}",
        f"- Creators: {totals['creators']}",
        "",
    ]
    lines += format_list(
        "Largest Collections",
        largest_collections,
        lambda row: f"{row[0]} | {row[1]} items",
    )
    lines += format_list(
        "Top Tags",
        top_tags,
        lambda row: f"{row[0]} | {row[1]} items",
    )
    lines += format_list(
        "Recently Added Items",
        recent_items,
        lambda row: f"{row[1]} | {row[2]} | added {row[3]}",
    )

    note_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    index_lines = [
        "# Zotero Index",
        "",
        "- [[library-health]]",
        "",
        "- Record Zotero library health, exports, and integration state here.",
        "",
    ]
    index_path.write_text("\n".join(index_lines), encoding="utf-8")
    print(str(note_path))


if __name__ == "__main__":
    main()
