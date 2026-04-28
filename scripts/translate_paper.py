#!/usr/bin/env python
import argparse
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from path_naming import paper_slug
from secure_config import load_json


IMAGE_RE = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
SECTION_NAME_SET = {
    "abstract",
    "introduction",
    "background",
    "methods",
    "method",
    "materials and methods",
    "results",
    "discussion",
    "discussions",
    "conclusion",
    "conclusions",
    "references",
    "acknowledgements",
    "acknowledgments",
    "declarations",
    "availability of data and materials",
    "ethical approval and consent to participate",
    "consent for publication",
    "competing interests",
    "funding",
    "authors contributions",
    "authors' contributions",
    "authors information",
    "corresponding author",
    "supplementary files",
    "keywords",
}
REFERENCE_LINE_RE = re.compile(r"^\s*\d+[\.\)]\s")
NUMBERED_SECTION_RE = re.compile(r"^\s*\d+(\.\d+)*[\.\)]?\s+\S")
SKIPPED_PARAGRAPHS = {
    "see image above for figure legend",
}


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def slugify(title: str, year: str = "") -> str:
    return paper_slug(title, year=year, max_length=32, fallback="paper")


def sanitize(value: str) -> str:
    return str(value).replace('"', "'")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def heading_key(text: str) -> str:
    key = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return key[:-1].strip() if key.endswith(":") else key


def is_section_heading(text: str) -> bool:
    key = heading_key(text)
    return key in SECTION_NAME_SET or bool(NUMBERED_SECTION_RE.match(text))


def looks_like_reference_entry(text: str) -> bool:
    if REFERENCE_LINE_RE.match(text):
        return True
    if '"' in text and any(year in text for year in ("19", "20")):
        return True
    return False


def build_output_dir(config: dict, title: str, year: str) -> Path:
    translation_cfg = config.get("translation", {})
    render_cfg = translation_cfg.get("render", {})
    explicit_root = render_cfg.get("translated_root", "").strip()
    if explicit_root:
        root = Path(explicit_root)
    else:
        vault_root = Path(config["vault_root"])
        attachment_folder = config["obsidian"]["attachment_folder"]
        folder_name = render_cfg.get("translated_folder_name", "translated-papers")
        root = vault_root / attachment_folder / folder_name
    return root / slugify(title, year)


def resolve_extract_paths(extract_path: Path):
    if not extract_path.exists():
        raise FileNotFoundError(f"Extract path not found: {extract_path}")

    if extract_path.is_dir():
        extract_dir = extract_path
        md_candidates = sorted(extract_dir.glob("*.md"))
    else:
        extract_dir = extract_path.parent
        md_candidates = [extract_path] if extract_path.suffix.lower() == ".md" else sorted(extract_dir.glob("*.md"))

    if not md_candidates:
        raise FileNotFoundError(f"No MinerU markdown file found under: {extract_dir}")

    source_md = md_candidates[0]
    content_list = next(iter(sorted(extract_dir.glob("*_content_list.json"))), None)
    return source_md, content_list, extract_dir


def new_block_id(index: int) -> str:
    return f"b{index:04d}"


def parse_markdown_blocks(md_path: Path):
    lines = md_path.read_text(encoding="utf-8").splitlines()
    blocks = []
    block_index = 1
    i = 0

    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue

        image_match = IMAGE_RE.match(stripped)
        if image_match:
            blocks.append(
                {
                    "id": new_block_id(block_index),
                    "kind": "image",
                    "image_path": image_match.group(1),
                    "caption_blocks": [],
                }
            )
            block_index += 1
            i += 1
            continue

        if stripped.startswith("$$"):
            equation_lines = [lines[i].rstrip()]
            i += 1
            while i < len(lines):
                equation_lines.append(lines[i].rstrip())
                if lines[i].strip().endswith("$$"):
                    i += 1
                    break
                i += 1
            blocks.append(
                {
                    "id": new_block_id(block_index),
                    "kind": "equation",
                    "text": "\n".join(equation_lines).strip(),
                }
            )
            block_index += 1
            continue

        heading_match = HEADING_RE.match(stripped)
        if heading_match:
            blocks.append(
                {
                    "id": new_block_id(block_index),
                    "kind": "heading",
                    "level": len(heading_match.group(1)),
                    "text": normalize_space(heading_match.group(2)),
                }
            )
            block_index += 1
            i += 1
            continue

        paragraph_lines = [stripped]
        i += 1
        while i < len(lines):
            probe = lines[i].strip()
            if not probe or IMAGE_RE.match(probe) or HEADING_RE.match(probe) or probe.startswith("$$"):
                break
            paragraph_lines.append(probe)
            i += 1

        paragraph_text = normalize_space(" ".join(paragraph_lines))
        if heading_key(paragraph_text) not in SKIPPED_PARAGRAPHS:
            blocks.append(
                {
                    "id": new_block_id(block_index),
                    "kind": "paragraph",
                    "text": paragraph_text,
                }
            )
            block_index += 1

    return regroup_figure_blocks(blocks)


def regroup_figure_blocks(blocks):
    grouped = []
    i = 0
    while i < len(blocks):
        current = blocks[i]
        if current["kind"] != "image":
            grouped.append(current)
            i += 1
            continue

        figure_block = dict(current)
        figure_block["caption_blocks"] = []
        caption_chars = 0
        caption_count = 0
        j = i + 1

        while j < len(blocks):
            probe = blocks[j]
            if probe["kind"] in {"image", "equation"}:
                break
            if probe["kind"] == "heading" and is_section_heading(probe["text"]):
                break

            probe_text = probe.get("text", "")
            if caption_count >= 4 or caption_chars + len(probe_text) > 2200:
                break

            caption_block = dict(probe)
            if caption_block["kind"] == "heading":
                caption_block["kind"] = "paragraph"
            figure_block["caption_blocks"].append(caption_block)
            caption_chars += len(probe_text)
            caption_count += 1
            j += 1

        grouped.append(figure_block)
        i = j

    return grouped


def collect_translatable_items(title: str, blocks):
    items = [{"id": "title", "kind": "title", "source_text": title}]
    in_references = False
    title_consumed = False

    for block in blocks:
        if block["kind"] == "heading":
            if not title_consumed and heading_key(block["text"]) == heading_key(title):
                block["skip_render"] = True
                title_consumed = True
                continue
            block["translatable"] = True
            items.append({"id": block["id"], "kind": "heading", "source_text": block["text"]})
            if heading_key(block["text"]) == "references":
                in_references = True
            elif is_section_heading(block["text"]):
                in_references = False
            continue

        if block["kind"] == "paragraph":
            translatable = not (in_references and looks_like_reference_entry(block["text"]))
            block["translatable"] = translatable
            if translatable:
                items.append({"id": block["id"], "kind": "paragraph", "source_text": block["text"]})
            continue

        if block["kind"] == "image":
            for caption_block in block["caption_blocks"]:
                caption_block["translatable"] = True
                items.append(
                    {
                        "id": caption_block["id"],
                        "kind": "figure_caption",
                        "source_text": caption_block["text"],
                    }
                )

    return items


def build_template_payload(title: str, target_language: str, source_md: Path, items):
    return {
        "schema_version": 1,
        "target_language": target_language,
        "source_markdown": str(source_md),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "blocks": [
            {
                "id": item["id"],
                "kind": item["kind"],
                "source_text": item["source_text"],
                "translation": "",
            }
            for item in items
        ],
    }


def load_manual_translations(path: Path):
    payload = load_json(path)
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("Manual translation file must contain a top-level 'blocks' array.")

    translations = {}
    for block in blocks:
        block_id = str(block.get("id", "")).strip()
        translation = str(block.get("translation", "")).strip()
        if block_id and translation:
            translations[block_id] = translation
    return translations


def extract_response_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str) and payload["output_text"].strip():
        return payload["output_text"].strip()

    pieces = []
    for output_item in payload.get("output", []):
        if not isinstance(output_item, dict):
            continue
        for content_item in output_item.get("content", []):
            if not isinstance(content_item, dict):
                continue
            if content_item.get("type") in {"output_text", "text"}:
                text = content_item.get("text", "")
                if text:
                    pieces.append(text)
    return "\n".join(pieces).strip()


def translate_with_openai(config: dict, items, target_language: str):
    translation_cfg = config.get("translation", {})
    openai_cfg = translation_cfg.get("openai", {})
    api_key = openai_cfg.get("api_key", "").strip() or os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OpenAI API key is not configured. Set translation.openai.api_key or OPENAI_API_KEY.")

    endpoint = openai_cfg.get("base_url", "https://api.openai.com/v1/responses").strip()
    model = openai_cfg.get("model", "gpt-5").strip()
    batch_chars = int(openai_cfg.get("batch_chars", 12000))
    max_output_tokens = int(openai_cfg.get("max_output_tokens", 8000))

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "translations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "translation": {"type": "string"},
                    },
                    "required": ["id", "translation"],
                },
            }
        },
        "required": ["translations"],
    }

    batches = []
    current_batch = []
    current_chars = 0
    for item in items:
        item_chars = len(item["source_text"])
        if current_batch and current_chars + item_chars > batch_chars:
            batches.append(current_batch)
            current_batch = []
            current_chars = 0
        current_batch.append(item)
        current_chars += item_chars
    if current_batch:
        batches.append(current_batch)

    translations = {}
    for batch in batches:
        prompt_payload = {
            "target_language": target_language,
            "requirements": [
                "Translate faithfully into polished Simplified Chinese academic prose.",
                "Keep inline LaTeX, display equations, citation markers, DOI, URLs, variables, and units unchanged.",
                "Do not add explanations, summaries, or reviewer comments.",
                "Return one translation for each block id.",
            ],
            "blocks": batch,
        }
        request_payload = {
            "model": model,
            "store": False,
            "max_output_tokens": max_output_tokens,
            "input": json.dumps(prompt_payload, ensure_ascii=False),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "paper_translation_batch",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(request_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI translation request failed ({exc.code}): {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI translation request failed: {exc.reason}") from exc

        response_text = extract_response_text(response_payload)
        if not response_text:
            raise RuntimeError("OpenAI response did not include any text output.")

        parsed = json.loads(response_text)
        for item in parsed.get("translations", []):
            block_id = str(item.get("id", "")).strip()
            translation = str(item.get("translation", "")).strip()
            if block_id and translation:
                translations[block_id] = translation

    missing_ids = [item["id"] for item in items if item["id"] not in translations]
    if missing_ids:
        raise RuntimeError("OpenAI translation response missed block ids: " + ", ".join(missing_ids[:10]))

    return translations


def copy_image_for_output(extract_dir: Path, image_rel_path: str, image_dir: Path) -> str:
    source_path = extract_dir / image_rel_path
    if not source_path.exists():
        return image_rel_path.replace("\\", "/")

    image_dir.mkdir(parents=True, exist_ok=True)
    target_path = image_dir / source_path.name
    if not target_path.exists():
        shutil.copy2(source_path, target_path)
    return f"images/{target_path.name}"


def build_frontmatter(metadata: dict):
    lines = [
        "---",
        f'title: "{sanitize(metadata["translated_title"])}"',
        f'paper_title_original: "{sanitize(metadata["original_title"])}"',
        f'year: "{sanitize(metadata["year"])}"',
        f'authors: "{sanitize(metadata["authors"])}"',
        f'translation_mode: "{sanitize(metadata["translation_mode"])}"',
        f'target_language: "{sanitize(metadata["target_language"])}"',
        f'source_pdf: "{sanitize(metadata["source_pdf"])}"',
        f'source_extract: "{sanitize(metadata["source_extract"])}"',
        f'generated_at: "{sanitize(metadata["generated_at"])}"',
        "---",
        "",
    ]
    return lines


def append_original_callout(lines, source_text: str):
    lines.extend(
        [
            "> [!quote]- Original",
            f"> {source_text}",
            "",
        ]
    )


def render_markdown(
    *,
    blocks,
    translations,
    extract_dir: Path,
    output_dir: Path,
    title: str,
    year: str,
    authors: str,
    source_pdf: str,
    source_md: Path,
    target_language: str,
    translation_mode: str,
    include_original_blocks: bool,
):
    translated_title = translations.get("title", title)
    metadata = {
        "translated_title": translated_title,
        "original_title": title,
        "year": year,
        "authors": authors,
        "translation_mode": translation_mode,
        "target_language": target_language,
        "source_pdf": source_pdf,
        "source_extract": str(source_md),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    lines = build_frontmatter(metadata)
    lines.extend(
        [
            f"# {translated_title}",
            "",
            f"> Original title: {title}",
            f"> Translation mode: {translation_mode}",
            f"> Source extract: `{source_md}`",
            "",
        ]
    )

    image_dir = output_dir / "images"
    for block in blocks:
        if block.get("skip_render"):
            continue
        if block["kind"] == "heading":
            heading_text = translations.get(block["id"], block["text"])
            level = min(max(int(block.get("level", 1)) + 1, 2), 6)
            lines.append("#" * level + f" {heading_text}")
            lines.append("")
            if include_original_blocks:
                append_original_callout(lines, block["text"])
            continue

        if block["kind"] == "paragraph":
            paragraph_text = translations.get(block["id"], block["text"]) if block.get("translatable", False) else block["text"]
            lines.append(paragraph_text)
            lines.append("")
            if include_original_blocks and block.get("translatable", False):
                append_original_callout(lines, block["text"])
            continue

        if block["kind"] == "equation":
            lines.append(block["text"])
            lines.append("")
            continue

        if block["kind"] == "image":
            rendered_image_path = copy_image_for_output(extract_dir, block["image_path"], image_dir)
            lines.append(f"![]({rendered_image_path})")
            lines.append("")
            caption_parts = []
            source_caption_parts = []
            for caption_block in block["caption_blocks"]:
                caption_parts.append(translations.get(caption_block["id"], caption_block["text"]))
                source_caption_parts.append(caption_block["text"])
            if caption_parts:
                lines.append("_Figure caption: " + " ".join(caption_parts) + "_")
                lines.append("")
                if include_original_blocks:
                    append_original_callout(lines, " ".join(source_caption_parts))
            continue

    rendered = "\n".join(lines).strip() + "\n"
    note_path = output_dir / "translated.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(rendered, encoding="utf-8")
    return note_path, translated_title


def prepare_command(args):
    config = load_json(Path(args.config))
    source_md, _, _ = resolve_extract_paths(Path(args.extract_path))
    blocks = parse_markdown_blocks(source_md)
    items = collect_translatable_items(args.title, blocks)

    output_dir = Path(args.output_dir) if args.output_dir else build_output_dir(config, args.title, args.year)
    template_path = Path(args.template_path) if args.template_path else output_dir / "translation-template.json"
    template_payload = build_template_payload(args.title, args.target_language, source_md, items)
    write_json(template_path, template_payload)

    result = {
        "status": "prepared",
        "template_path": str(template_path),
        "source_markdown": str(source_md),
        "output_dir": str(output_dir),
        "block_count": len(template_payload["blocks"]),
    }
    print(json.dumps(result, ensure_ascii=False))


def build_command(args):
    config = load_json(Path(args.config))
    source_md, _, extract_dir = resolve_extract_paths(Path(args.extract_path))
    blocks = parse_markdown_blocks(source_md)
    items = collect_translatable_items(args.title, blocks)

    output_dir = Path(args.output_dir) if args.output_dir else build_output_dir(config, args.title, args.year)
    output_dir.mkdir(parents=True, exist_ok=True)

    include_original_blocks = args.include_original_blocks
    if not include_original_blocks:
        include_original_blocks = bool(
            config.get("translation", {}).get("render", {}).get("include_original_blocks", False)
        )

    if args.mode == "ai":
        translations = translate_with_openai(config, items, args.target_language)
        template_path = ""
    else:
        if not args.translation_file:
            raise ValueError("Manual build mode requires --translation-file.")
        template_path = str(Path(args.translation_file))
        translations = load_manual_translations(Path(args.translation_file))
        missing_ids = [item["id"] for item in items if item["id"] not in translations]
        if missing_ids:
            raise ValueError("Manual translation file is missing ids: " + ", ".join(missing_ids[:10]))

    note_path, translated_title = render_markdown(
        blocks=blocks,
        translations=translations,
        extract_dir=extract_dir,
        output_dir=output_dir,
        title=args.title,
        year=args.year,
        authors=args.authors,
        source_pdf=args.source_pdf,
        source_md=source_md,
        target_language=args.target_language,
        translation_mode=args.mode,
        include_original_blocks=include_original_blocks,
    )

    result = {
        "status": "built",
        "translated_note_path": str(note_path),
        "translated_title": translated_title,
        "translation_file": template_path,
        "output_dir": str(output_dir),
    }
    print(json.dumps(result, ensure_ascii=False))


def build_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    common_parent = argparse.ArgumentParser(add_help=False)
    common_parent.add_argument("--config", required=True)
    common_parent.add_argument("--extract-path", required=True)
    common_parent.add_argument("--title", required=True)
    common_parent.add_argument("--year", default="")
    common_parent.add_argument("--authors", default="")
    common_parent.add_argument("--source-pdf", default="")
    common_parent.add_argument("--target-language", default="zh-CN")
    common_parent.add_argument("--output-dir", default="")

    prepare_parser = subparsers.add_parser("prepare", parents=[common_parent])
    prepare_parser.add_argument("--template-path", default="")
    prepare_parser.set_defaults(handler=prepare_command)

    build_parser = subparsers.add_parser("build", parents=[common_parent])
    build_parser.add_argument("--mode", choices=["ai", "manual"], required=True)
    build_parser.add_argument("--translation-file", default="")
    build_parser.add_argument("--include-original-blocks", action="store_true")
    build_parser.set_defaults(handler=build_command)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
