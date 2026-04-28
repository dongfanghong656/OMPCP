#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

DEFAULT_PEOPLE_FOLDER = "13_People"
DEFAULT_RELATIONSHIP_FOLDER = "14_Relationships"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(value: str) -> str:
    collapsed = re.sub(r"\s+", "", value or "")
    return collapsed.casefold()


def dedupe_strings(existing: list[str] | None, incoming: list[str] | None) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for raw in (existing or []) + (incoming or []):
        value = str(raw).strip()
        if not value:
            continue
        key = normalize_text(value)
        if key in seen:
            continue
        merged.append(value)
        seen.add(key)
    return merged


def slugify(value: str, prefix: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", "-", (value or "").casefold()).strip("-")
    if lowered:
        return f"{prefix}-{lowered}"
    digest = hashlib.sha1((value or prefix).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


def obsidian_with_defaults(obsidian: dict[str, Any]) -> dict[str, Any]:
    merged = dict(obsidian)
    merged.setdefault("people_folder", DEFAULT_PEOPLE_FOLDER)
    merged.setdefault("relationship_folder", DEFAULT_RELATIONSHIP_FOLDER)
    return merged


def relationship_paths(vault_root: Path, obsidian: dict[str, Any]) -> dict[str, Path]:
    obs = obsidian_with_defaults(obsidian)
    people_dir = vault_root / obs["people_folder"]
    relationship_dir = vault_root / obs["relationship_folder"]
    return {
        "people_dir": people_dir,
        "people_registry": people_dir / "_registry.json",
        "people_index": people_dir / "_Index.md",
        "relationship_dir": relationship_dir,
        "relationship_registry": relationship_dir / "_registry.json",
        "relationship_index": relationship_dir / "_Index.md",
    }


def empty_registry(key: str) -> dict[str, Any]:
    return {"version": 1, "updated_at": "", key: []}


def load_registry(path: Path, key: str) -> dict[str, Any]:
    if not path.exists():
        return empty_registry(key)
    payload = load_json(path)
    payload.setdefault("version", 1)
    payload.setdefault("updated_at", "")
    payload.setdefault(key, [])
    return payload


def note_ref(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.startswith("[[") and text.endswith("]]"):
        return text[2:-2]
    if "\\" in text or "/" in text or "." in Path(text).name:
        return Path(text).stem
    return text


def listify(payload: Any) -> list[str]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [str(item).strip() for item in payload if str(item).strip()]
    value = str(payload).strip()
    return [value] if value else []


def person_lookup_keys(person: dict[str, Any]) -> set[str]:
    keys = {normalize_text(person.get("canonical_name", ""))}
    for alias in person.get("aliases", []):
        keys.add(normalize_text(alias))
    return {key for key in keys if key}


def find_person_index(people: list[dict[str, Any]], labels: list[str]) -> int | None:
    targets = {normalize_text(label) for label in labels if normalize_text(label)}
    if not targets:
        return None
    for index, person in enumerate(people):
        if person_lookup_keys(person) & targets:
            return index
    return None


def ensure_person_shape(person: dict[str, Any]) -> dict[str, Any]:
    person.setdefault("id", slugify(person.get("canonical_name", "person"), "person"))
    person.setdefault("slug", person["id"])
    person.setdefault("canonical_name", "")
    person.setdefault("aliases", [])
    person.setdefault("relationship_to_user", "")
    person.setdefault("relationship_stage", "")
    person.setdefault("summary", "")
    person.setdefault("organization", "")
    person.setdefault("location", "")
    person.setdefault("contact_points", [])
    person.setdefault("traits", [])
    person.setdefault("preferences", [])
    person.setdefault("topics", [])
    person.setdefault("important_dates", [])
    person.setdefault("notes", [])
    person.setdefault("uncertainties", [])
    person.setdefault("tags", [])
    person.setdefault("confidence", "")
    person.setdefault("source_notes", [])
    person.setdefault("created_at", "")
    person.setdefault("last_updated", "")
    return person


def upsert_person(
    people: list[dict[str, Any]],
    payload: dict[str, Any],
    source_note: str | None,
) -> dict[str, Any]:
    canonical_name = str(payload.get("canonical_name") or payload.get("name") or "").strip()
    aliases = listify(payload.get("aliases"))
    lookup_labels = [canonical_name, *aliases]
    lookup_index = find_person_index(people, lookup_labels)
    now = datetime.now().isoformat(timespec="seconds")

    if lookup_index is None:
        if not canonical_name and aliases:
            canonical_name = aliases[0]
            aliases = aliases[1:]
        if not canonical_name:
            raise ValueError("Person entries require `name` or `canonical_name`.")
        person = ensure_person_shape(
            {
                "id": slugify(canonical_name, "person"),
                "slug": slugify(canonical_name, "person"),
                "canonical_name": canonical_name,
                "created_at": now,
            }
        )
        people.append(person)
    else:
        person = ensure_person_shape(people[lookup_index])

    explicit_canonical = str(payload.get("canonical_name") or "").strip()
    if explicit_canonical and normalize_text(explicit_canonical) != normalize_text(person["canonical_name"]):
        person["aliases"] = dedupe_strings(person["aliases"], [person["canonical_name"]])
        person["canonical_name"] = explicit_canonical
    elif not person["canonical_name"] and canonical_name:
        person["canonical_name"] = canonical_name

    if not person["created_at"]:
        person["created_at"] = now

    person["aliases"] = dedupe_strings(person["aliases"], aliases)
    for scalar in [
        "relationship_to_user",
        "relationship_stage",
        "summary",
        "organization",
        "location",
        "confidence",
    ]:
        incoming = str(payload.get(scalar) or "").strip()
        if incoming:
            person[scalar] = incoming

    for list_field in [
        "contact_points",
        "traits",
        "preferences",
        "topics",
        "important_dates",
        "notes",
        "uncertainties",
        "tags",
    ]:
        person[list_field] = dedupe_strings(person.get(list_field, []), listify(payload.get(list_field)))

    source_reference = note_ref(source_note)
    if source_reference:
        person["source_notes"] = dedupe_strings(person.get("source_notes", []), [source_reference])

    person["last_updated"] = now
    return person


def event_people_labels(payload: dict[str, Any]) -> list[str]:
    raw_people = payload.get("people") or payload.get("participants") or []
    names: list[str] = []
    for item in raw_people:
        if isinstance(item, dict):
            value = str(item.get("name") or item.get("canonical_name") or "").strip()
        else:
            value = str(item).strip()
        if value:
            names.append(value)
    return dedupe_strings([], names)


def ensure_event_shape(event: dict[str, Any]) -> dict[str, Any]:
    event.setdefault("id", slugify(event.get("title", "relationship-event"), "relationship-event"))
    event.setdefault("date", date.today().isoformat())
    event.setdefault("title", "")
    event.setdefault("type", "")
    event.setdefault("summary", "")
    event.setdefault("impact_on_user", "")
    event.setdefault("follow_up", "")
    event.setdefault("status", "")
    event.setdefault("confidence", "")
    event.setdefault("people", [])
    event.setdefault("tags", [])
    event.setdefault("uncertainties", [])
    event.setdefault("source_notes", [])
    event.setdefault("created_at", "")
    event.setdefault("last_updated", "")
    return event


def upsert_event(
    events: list[dict[str, Any]],
    payload: dict[str, Any],
    participant_ids: list[str],
    source_note: str | None,
) -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    event_date = str(payload.get("date") or date.today().isoformat()).strip()
    title = str(payload.get("title") or "").strip()
    summary = str(payload.get("summary") or "").strip()
    if not title:
        title = summary[:50] if summary else "Relationship event"
    event_key = "|".join([event_date, title, ",".join(sorted(participant_ids))])
    event_id = str(payload.get("id") or slugify(event_key, "relationship-event"))

    existing = next((item for item in events if item.get("id") == event_id), None)
    if existing is None:
        event = ensure_event_shape({"id": event_id, "created_at": now})
        events.append(event)
    else:
        event = ensure_event_shape(existing)

    for scalar in [
        "date",
        "title",
        "type",
        "summary",
        "impact_on_user",
        "follow_up",
        "status",
        "confidence",
    ]:
        incoming = str(payload.get(scalar) or "").strip()
        if incoming:
            event[scalar] = incoming

    if not event["created_at"]:
        event["created_at"] = now

    event["people"] = dedupe_strings(event.get("people", []), participant_ids)
    event["tags"] = dedupe_strings(event.get("tags", []), listify(payload.get("tags")))
    event["uncertainties"] = dedupe_strings(event.get("uncertainties", []), listify(payload.get("uncertainties")))

    source_reference = note_ref(source_note)
    if source_reference:
        event["source_notes"] = dedupe_strings(event.get("source_notes", []), [source_reference])

    event["last_updated"] = now
    return event


def as_link_list(items: list[str], wrapped: bool = False) -> list[str]:
    values: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        values.append(f"[[{text}]]" if wrapped else text)
    return values


def bullet_section(title: str, items: list[str], wrap_links: bool = False) -> list[str]:
    lines = [f"## {title}", ""]
    values = as_link_list(items, wrapped=wrap_links)
    if not values:
        lines.append("- None recorded.")
    else:
        for item in values:
            lines.append(f"- {item}")
    lines.append("")
    return lines


def person_note_path(people_dir: Path, person: dict[str, Any]) -> Path:
    return people_dir / f"{person['id']}.md"


def event_note_path(relationship_dir: Path, event: dict[str, Any]) -> Path:
    return relationship_dir / f"{event['date']}-{event['id']}.md"


def render_person_note(
    people_dir: Path,
    relationship_dir: Path,
    person: dict[str, Any],
    related_events: list[dict[str, Any]],
) -> None:
    header_lines = [
        f"# {person['canonical_name']}",
        "",
        f"- ID: {person['id']}",
        f"- Relationship to user: {person.get('relationship_to_user') or 'Unknown'}",
        f"- Relationship stage: {person.get('relationship_stage') or 'Unspecified'}",
        f"- Confidence: {person.get('confidence') or 'Unspecified'}",
        f"- Last updated: {person.get('last_updated') or 'Unknown'}",
        f"- Aliases: {', '.join(person.get('aliases', [])) or 'None'}",
        f"- Organization: {person.get('organization') or 'Unknown'}",
        f"- Location: {person.get('location') or 'Unknown'}",
        "",
        "## Snapshot",
        "",
        person.get("summary") or "No summary recorded yet.",
        "",
    ]
    body = []
    body += bullet_section("Contact Points", person.get("contact_points", []))
    body += bullet_section("Traits", person.get("traits", []))
    body += bullet_section("Preferences", person.get("preferences", []))
    body += bullet_section("Topics", person.get("topics", []))
    body += bullet_section("Important Dates", person.get("important_dates", []))
    body += bullet_section("Notes", person.get("notes", []))
    body += bullet_section("Open Questions", person.get("uncertainties", []))
    body += bullet_section("Tags", person.get("tags", []))
    body += bullet_section("Source Notes", person.get("source_notes", []), wrap_links=True)

    related_event_refs = [
        f"{event['date']}-{event['id']}" for event in sorted(related_events, key=lambda item: item.get("date", ""), reverse=True)
    ]
    body += bullet_section("Recent Relationship Events", related_event_refs, wrap_links=True)
    person_note_path(people_dir, person).write_text("\n".join(header_lines + body).rstrip() + "\n", encoding="utf-8")


def render_event_note(
    relationship_dir: Path,
    event: dict[str, Any],
    people_by_id: dict[str, dict[str, Any]],
) -> None:
    people_lines = []
    for person_id in event.get("people", []):
        person = people_by_id.get(person_id)
        label = person["canonical_name"] if person else person_id
        people_lines.append(f"[[{person_id}]] ({label})")

    lines = [
        f"# {event['title']}",
        "",
        f"- ID: {event['id']}",
        f"- Date: {event.get('date') or 'Unknown'}",
        f"- Type: {event.get('type') or 'Unspecified'}",
        f"- Status: {event.get('status') or 'Unspecified'}",
        f"- Confidence: {event.get('confidence') or 'Unspecified'}",
        "",
        "## People",
        "",
    ]
    if people_lines:
        lines.extend(f"- {item}" for item in people_lines)
    else:
        lines.append("- None linked.")
    lines += [
        "",
        "## Summary",
        "",
        event.get("summary") or "No summary recorded yet.",
        "",
        "## Impact On User",
        "",
        event.get("impact_on_user") or "No direct impact recorded.",
        "",
        "## Suggested Follow-up",
        "",
        event.get("follow_up") or "No follow-up recorded.",
        "",
    ]
    lines += bullet_section("Uncertainties", event.get("uncertainties", []))
    lines += bullet_section("Tags", event.get("tags", []))
    lines += bullet_section("Source Notes", event.get("source_notes", []), wrap_links=True)
    event_note_path(relationship_dir, event).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def refresh_indexes(
    paths: dict[str, Path],
    people_registry: dict[str, Any],
    relationship_registry: dict[str, Any],
) -> None:
    people = sorted(people_registry["people"], key=lambda item: normalize_text(item.get("canonical_name", "")))
    events = sorted(
        relationship_registry["events"],
        key=lambda item: (item.get("date", ""), item.get("last_updated", "")),
        reverse=True,
    )
    people_registry["people"] = people
    relationship_registry["events"] = events
    people_registry["updated_at"] = datetime.now().isoformat(timespec="seconds")
    relationship_registry["updated_at"] = people_registry["updated_at"]
    save_json(paths["people_registry"], people_registry)
    save_json(paths["relationship_registry"], relationship_registry)

    people_by_id = {person["id"]: person for person in people}
    for person in people:
        related_events = [event for event in events if person["id"] in event.get("people", [])]
        render_person_note(paths["people_dir"], paths["relationship_dir"], person, related_events[:10])
    for event in events:
        render_event_note(paths["relationship_dir"], event, people_by_id)

    people_index_lines = [
        "# People Index",
        "",
        "Use this layer for durable person profiles, contact context, and relationship-sensitive follow-up notes.",
        "",
    ]
    if not people:
        people_index_lines.append("- No people recorded yet.")
    else:
        for person in people:
            people_index_lines.append(
                f"- [[{person['id']}]] | {person['canonical_name']} | "
                f"{person.get('relationship_to_user') or 'Unknown'} | updated {person.get('last_updated') or 'Unknown'}"
            )
    paths["people_index"].write_text("\n".join(people_index_lines).rstrip() + "\n", encoding="utf-8")

    relationship_index_lines = [
        "# Relationship Event Index",
        "",
        "Record major interactions, shifts in context, commitments, tensions, and follow-up obligations here.",
        "",
    ]
    if not events:
        relationship_index_lines.append("- No relationship events recorded yet.")
    else:
        for event in events:
            labels = []
            for person_id in event.get("people", []):
                labels.append(people_by_id.get(person_id, {}).get("canonical_name", person_id))
            relationship_index_lines.append(
                f"- [[{event['date']}-{event['id']}]] | {event.get('date') or 'Unknown'} | "
                f"{event.get('type') or 'Unspecified'} | {', '.join(labels) or 'No linked person'}"
            )
    paths["relationship_index"].write_text(
        "\n".join(relationship_index_lines).rstrip() + "\n",
        encoding="utf-8",
    )


def bootstrap_relationship_memory(vault_root: Path, obsidian: dict[str, Any]) -> dict[str, Path]:
    paths = relationship_paths(vault_root, obsidian)
    paths["people_dir"].mkdir(parents=True, exist_ok=True)
    paths["relationship_dir"].mkdir(parents=True, exist_ok=True)
    if not paths["people_registry"].exists():
        save_json(paths["people_registry"], empty_registry("people"))
    if not paths["relationship_registry"].exists():
        save_json(paths["relationship_registry"], empty_registry("events"))
    if not paths["people_index"].exists():
        paths["people_index"].write_text(
            "# People Index\n\nUse this layer for durable person profiles, contact context, and relationship-sensitive follow-up notes.\n",
            encoding="utf-8",
        )
    if not paths["relationship_index"].exists():
        paths["relationship_index"].write_text(
            "# Relationship Event Index\n\nRecord major interactions, shifts in context, commitments, tensions, and follow-up obligations here.\n",
            encoding="utf-8",
        )
    return paths


def update_memory_from_payload(
    config_path: Path,
    payload_path: Path,
    source_note: str | None = None,
) -> dict[str, Any]:
    config = load_json(config_path)
    vault_root = Path(config["vault_root"])
    paths = bootstrap_relationship_memory(vault_root, config["obsidian"])
    people_registry = load_registry(paths["people_registry"], "people")
    relationship_registry = load_registry(paths["relationship_registry"], "events")
    payload = load_json(payload_path)
    people = people_registry["people"]
    events = relationship_registry["events"]

    person_entries = payload.get("people", []) or []
    event_entries = payload.get("events", []) or []
    touched_people: list[str] = []
    touched_events: list[str] = []

    for entry in person_entries:
        person = upsert_person(people, entry, source_note=source_note)
        touched_people.append(person["id"])

    people_by_label = {}
    for person in people:
        for key in person_lookup_keys(person):
            people_by_label[key] = person

    for entry in event_entries:
        participant_ids: list[str] = []
        for label in event_people_labels(entry):
            normalized = normalize_text(label)
            person = people_by_label.get(normalized)
            if person is None:
                person = upsert_person(people, {"name": label, "confidence": "low"}, source_note=source_note)
                for key in person_lookup_keys(person):
                    people_by_label[key] = person
            participant_ids.append(person["id"])
        if participant_ids or entry.get("summary") or entry.get("title"):
            event = upsert_event(events, entry, participant_ids=participant_ids, source_note=source_note)
            touched_events.append(event["id"])

    refresh_indexes(paths, people_registry, relationship_registry)
    return {
        "people_updated": sorted(set(touched_people)),
        "events_updated": sorted(set(touched_events)),
        "people_registry": str(paths["people_registry"]),
        "relationship_registry": str(paths["relationship_registry"]),
    }


def search_people(people: list[dict[str, Any]], keyword: str) -> list[dict[str, Any]]:
    target = normalize_text(keyword)
    if not target:
        return []
    matches: list[dict[str, Any]] = []
    for person in people:
        haystack = "\n".join(
            [
                person.get("canonical_name", ""),
                " ".join(person.get("aliases", [])),
                person.get("relationship_to_user", ""),
                person.get("relationship_stage", ""),
                person.get("summary", ""),
                person.get("organization", ""),
                person.get("location", ""),
                " ".join(person.get("contact_points", [])),
                " ".join(person.get("traits", [])),
                " ".join(person.get("preferences", [])),
                " ".join(person.get("topics", [])),
                " ".join(person.get("important_dates", [])),
                " ".join(person.get("notes", [])),
                " ".join(person.get("uncertainties", [])),
                " ".join(person.get("tags", [])),
            ]
        )
        if target in normalize_text(haystack):
            matches.append(person)
    return matches


def search_events(events: list[dict[str, Any]], keyword: str) -> list[dict[str, Any]]:
    target = normalize_text(keyword)
    if not target:
        return []
    matches: list[dict[str, Any]] = []
    for event in events:
        haystack = "\n".join(
            [
                event.get("date", ""),
                event.get("title", ""),
                event.get("type", ""),
                event.get("summary", ""),
                event.get("impact_on_user", ""),
                event.get("follow_up", ""),
                " ".join(event.get("tags", [])),
                " ".join(event.get("uncertainties", [])),
                " ".join(event.get("people", [])),
            ]
        )
        if target in normalize_text(haystack):
            matches.append(event)
    return matches


def person_summary_text(person: dict[str, Any], related_events: list[dict[str, Any]]) -> str:
    lines = [
        f"Person: {person['canonical_name']}",
        f"Relationship to user: {person.get('relationship_to_user') or 'Unknown'}",
        f"Relationship stage: {person.get('relationship_stage') or 'Unspecified'}",
        f"Confidence: {person.get('confidence') or 'Unspecified'}",
        f"Aliases: {', '.join(person.get('aliases', [])) or 'None'}",
        f"Organization: {person.get('organization') or 'Unknown'}",
        f"Location: {person.get('location') or 'Unknown'}",
        "",
        "Summary:",
        person.get("summary") or "No summary recorded yet.",
        "",
    ]
    for section, key in [
        ("Traits", "traits"),
        ("Preferences", "preferences"),
        ("Topics", "topics"),
        ("Notes", "notes"),
        ("Open Questions", "uncertainties"),
        ("Source Notes", "source_notes"),
    ]:
        lines.append(f"{section}:")
        values = person.get(key, [])
        if not values:
            lines.append("- None recorded.")
        else:
            for item in values:
                prefix = f"[[{item}]]" if key == "source_notes" else item
                lines.append(f"- {prefix}")
        lines.append("")

    lines.append("Recent Events:")
    if not related_events:
        lines.append("- None recorded.")
    else:
        for event in related_events:
            lines.append(
                f"- {event.get('date') or 'Unknown'} | {event.get('title') or 'Untitled'} | "
                f"{event.get('summary') or 'No summary'}"
            )
    return "\n".join(lines).rstrip()


def query_memory(
    config_path: Path,
    person_name: str | None = None,
    keyword: str | None = None,
    limit_events: int = 5,
) -> dict[str, Any]:
    config = load_json(config_path)
    paths = bootstrap_relationship_memory(Path(config["vault_root"]), config["obsidian"])
    people_registry = load_registry(paths["people_registry"], "people")
    relationship_registry = load_registry(paths["relationship_registry"], "events")
    people = people_registry["people"]
    events = relationship_registry["events"]

    matched_people: list[dict[str, Any]]
    matched_events: list[dict[str, Any]]
    if person_name:
        exact_index = find_person_index(people, [person_name])
        if exact_index is not None:
            matched_people = [people[exact_index]]
        else:
            matched_people = search_people(people, person_name)
        matched_ids = {person["id"] for person in matched_people}
        matched_events = [event for event in events if matched_ids & set(event.get("people", []))]
    elif keyword:
        matched_people = search_people(people, keyword)
        matched_ids = {person["id"] for person in matched_people}
        keyword_events = search_events(events, keyword)
        related_events = [event for event in events if matched_ids & set(event.get("people", []))]
        seen_event_ids = set()
        matched_events = []
        for event in keyword_events + related_events:
            event_id = event.get("id")
            if event_id in seen_event_ids:
                continue
            matched_events.append(event)
            seen_event_ids.add(event_id)
    else:
        matched_people = people
        matched_events = events

    matched_events = sorted(
        matched_events,
        key=lambda item: (item.get("date", ""), item.get("last_updated", "")),
        reverse=True,
    )
    return {
        "people": matched_people,
        "events": matched_events[:limit_events],
        "people_registry": str(paths["people_registry"]),
        "relationship_registry": str(paths["relationship_registry"]),
    }


def format_query_result(result: dict[str, Any]) -> str:
    people = result["people"]
    events = result["events"]
    if not people and not events:
        return "No relationship memory matches found."

    event_map: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        for person_id in event.get("people", []):
            event_map.setdefault(person_id, []).append(event)

    blocks: list[str] = []
    for person in people:
        blocks.append(person_summary_text(person, event_map.get(person["id"], [])))
    if events and not people:
        lines = ["Matching Relationship Events:", ""]
        for event in events:
            lines.append(
                f"- {event.get('date') or 'Unknown'} | {event.get('title') or 'Untitled'} | "
                f"{event.get('summary') or 'No summary'}"
            )
        blocks.append("\n".join(lines).rstrip())
    return "\n\n".join(blocks).rstrip()


def list_people(config_path: Path) -> str:
    result = query_memory(config_path)
    people = result["people"]
    if not people:
        return "No people recorded yet."
    lines = []
    for person in people:
        lines.append(
            f"{person['canonical_name']} | {person.get('relationship_to_user') or 'Unknown'} | "
            f"{person.get('relationship_stage') or 'Unspecified'}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser("bootstrap")
    bootstrap_parser.add_argument("--config", required=True)

    upsert_parser = subparsers.add_parser("upsert")
    upsert_parser.add_argument("--config", required=True)
    upsert_parser.add_argument("--payload", required=True)
    upsert_parser.add_argument("--source-note")

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("--config", required=True)
    query_parser.add_argument("--person")
    query_parser.add_argument("--keyword")
    query_parser.add_argument("--limit-events", type=int, default=5)
    query_parser.add_argument("--json", action="store_true")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--config", required=True)

    args = parser.parse_args()
    config_path = Path(args.config)

    if args.command == "bootstrap":
        config = load_json(config_path)
        paths = bootstrap_relationship_memory(Path(config["vault_root"]), config["obsidian"])
        print(json.dumps({key: str(value) for key, value in paths.items()}, ensure_ascii=False, indent=2))
        return

    if args.command == "upsert":
        result = update_memory_from_payload(
            config_path=config_path,
            payload_path=Path(args.payload),
            source_note=args.source_note,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "query":
        result = query_memory(
            config_path=config_path,
            person_name=args.person,
            keyword=args.keyword,
            limit_events=args.limit_events,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(format_query_result(result))
        return

    if args.command == "list":
        print(list_people(config_path))
        return


if __name__ == "__main__":
    main()
