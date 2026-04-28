#!/usr/bin/env python
import argparse
import hashlib
import json
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable


VISIBLE_CONTENT_TYPES = {"text", "multimodal_text"}

DEFAULT_DAILY_TEMPLATE = """# {date}

## Reading

## Decisions

## Questions

## Next actions
"""

TOPIC_BUCKETS = [
    {
        "slug": "oct-psf-deconvolution",
        "label": "OCT / PSF / Deconvolution",
        "keywords": [
            "oct",
            "sdoct",
            "sd-oct",
            "ofdi",
            "psf",
            "deconvolution",
            "pca",
            "point spread function",
            "depth-variant",
            "mirror",
            "particle",
            "aberration",
            "phase",
            "zernike",
        ],
        "targets": [
            "03_Concepts/03_PSF-and-Imaging-Model",
            "03_Concepts/04_Deconvolution-and-Inverse-Problems",
            "04_Progress",
        ],
        "knowledge_surface": [
            "Imported threads repeatedly discuss PSF truthing, depth-variant blur, deconvolution gains, and method boundaries.",
            "The corpus now supports reusable judgments rather than one-off answers about whether a restoration method should be trusted.",
        ],
        "capability": "Can reason about PSF modeling, validation strategy, deconvolution applicability, and method boundaries from conversation evidence.",
    },
    {
        "slug": "spectrometer-and-acquisition",
        "label": "Spectrometer / Acquisition / Debugging",
        "keywords": [
            "spectrometer",
            "camera",
            "line scan",
            "line-scan",
            "snap",
            "stage",
            "opd",
            "optical path difference",
            "interference",
            "fringe",
            "a-scan",
            "b-scan",
            "acquisition",
            "scan length",
            "pixel",
        ],
        "targets": [
            "03_Concepts/01_OCT-Physics",
            "03_Concepts/02_System-Build-and-Calibration",
            "05_Experiments",
        ],
        "knowledge_surface": [
            "Imported threads cover acquisition geometry, line-camera interpretation, OPD tuning, parasitic interference, and practical debugging.",
            "The corpus helps map software parameters back to physical system behavior.",
        ],
        "capability": "Can map camera and scan parameters back to physical motion, optical path, and likely hardware failure modes.",
    },
    {
        "slug": "matlab-and-algorithm-prototyping",
        "label": "MATLAB / Algorithm Prototyping",
        "keywords": [
            "matlab",
            "prototype",
            "script",
            "algorithm",
            "reconstruction",
            "optimize",
            "simulation",
            "code",
        ],
        "targets": [
            "03_Concepts/06_MATLAB-and-Implementation",
            "05_Experiments",
            "04_Progress",
        ],
        "knowledge_surface": [
            "The imported conversations repeatedly turn research questions into executable MATLAB-side prototypes and validation routines.",
            "This supports fast movement from concept to testable implementation.",
        ],
        "capability": "Can convert method discussions into concrete MATLAB-oriented implementation ideas and validation steps.",
    },
    {
        "slug": "obsidian-and-knowledge-system",
        "label": "Obsidian / Knowledge System / Conversation Curation",
        "keywords": [
            "obsidian",
            "vault",
            "knowledge base",
            "conversation",
            "transcript",
            "archive",
            "protocol",
            "html export",
            "finder",
            "index",
        ],
        "targets": [
            "09_Conversations",
            "00_Home/Protocols",
            "00_System/04_Scripts",
        ],
        "knowledge_surface": [
            "The corpus includes repeated work on transcript recovery, index design, vault routing, and long-term conversation curation.",
            "These discussions are now part of the vault's operating memory instead of remaining trapped in chat history.",
        ],
        "capability": "Can convert conversations into durable Obsidian assets with transcripts, summaries, indexes, and protocol notes.",
    },
    {
        "slug": "research-assistant-and-codex-operations",
        "label": "Research Assistant / Codex / Workflow",
        "keywords": [
            "codex",
            "agent",
            "workflow",
            "automation",
            "sandbox",
            "collaboration",
            "recovery",
            "tooling",
        ],
        "targets": [
            "07_Profiles",
            "04_Progress",
            "00_Home/Protocols",
        ],
        "knowledge_surface": [
            "The imported threads also contain operating knowledge about assistant behavior, sandbox limits, and vault-oriented collaboration.",
            "This strengthens the system's reusable workflow layer, not just its OCT content.",
        ],
        "capability": "Can design and refine research-assistant workflows, archive mechanisms, and tool-driven collaboration loops.",
    },
]

FALLBACK_BUCKET = {
    "slug": "miscellaneous",
    "label": "Miscellaneous / Cross-cutting",
    "targets": ["09_Conversations", "04_Progress"],
    "knowledge_surface": ["This thread spans multiple buckets or needs later manual routing."],
    "capability": "Needs later manual interpretation against the raw transcript.",
}

MEMO_HEADER_RE = re.compile(r"^(Title|URL|Platform|Created|Messages):\s*(.*)$")
MEMO_MESSAGE_RE = re.compile(
    r"^(User|AI|Assistant|System):\s*\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*$",
    re.MULTILINE,
)
MARKDOWN_CHAT_DATE_RE = re.compile(r"^\*\*Date\*\*:\s*(.+)$", re.MULTILINE)
MARKDOWN_CHAT_SOURCE_RE = re.compile(
    r"^\*\*Source\*\*:\s*\[(?P<label>[^\]]+)\]\((?P<url>[^)]+)\)",
    re.MULTILINE,
)
MARKDOWN_TURN_SPLIT_RE = re.compile(r"^## Turn \d+\s*$", re.MULTILINE)
MARKDOWN_ROLE_RE = re.compile(r"^### .*?\b(User|AI|Assistant|System)\b\s*$", re.MULTILINE)
RESPONSE_EXPORT_STEM_RE = re.compile(r"^(?P<title>.+?)_(?P<ts>\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})$")
TIMESTAMP_IN_NAME_RE = re.compile(r"_(\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})$")
PRIVATE_USE_RE = re.compile(r"[\ue000-\uf8ff]")
ARTIFACT_TOKEN_RE = re.compile(r"(?:filecite|turn\d+(?:file|search|view)\d+|turn\d+fetch\d+)")
BRACKET_CITATION_RE = re.compile(r"【[^】]*†[^】]*】")
INLINE_CITE_RE = re.compile(r"(?<![A-Za-z])cite(?![A-Za-z])", re.IGNORECASE)
MARKDOWN_IMAGE_LINE_RE = re.compile(r"(?m)^\s*!\[[^\]]*\]\([^)]+\)\s*$")
UPLOAD_PLACEHOLDER_RE = re.compile(r"(?m)^\s*\*\[This turn includes uploaded images\]\*\s*$")
ZIP_CONVERSATION_NAME_HINTS = (
    "chatgpt",
    "chat-memo",
    "gemini-chat",
    "conversation",
    "claude",
)


@dataclass
class Message:
    role: str
    text: str
    created_at: float | None = None


@dataclass
class CorpusLayout:
    corpus_name: str
    corpus_slug: str
    transcript_group: str
    topic_note_path: Path
    capability_note_path: Path
    progress_note_path: Path


@dataclass
class ConversationRecord:
    title: str
    conversation_id: str
    source_entry: str
    source_zip: str
    created_at: float | None
    updated_at: float | None
    model: str
    messages: list[Message]
    provider: str = "Unknown"
    source_kind: str = "unknown"
    source_url: str | None = None
    corpus_key: str = "generic-conversation-backup"
    primary_buckets: list[str] = field(default_factory=list)
    matched_terms: list[str] = field(default_factory=list)
    note_path: Path | None = None
    transcript_path: Path | None = None
    manifest_entry: dict | None = None
    visible_turn_count: int | None = None
    user_turn_count: int | None = None
    assistant_turn_count: int | None = None
    archive_class: str | None = None
    archive_class_reason: str | None = None

    @property
    def user_turns(self) -> int:
        if self.user_turn_count is not None:
            return self.user_turn_count
        return sum(1 for message in self.messages if message.role == "user")

    @property
    def assistant_turns(self) -> int:
        if self.assistant_turn_count is not None:
            return self.assistant_turn_count
        return sum(1 for message in self.messages if message.role == "assistant")

    @property
    def visible_turns(self) -> int:
        if self.visible_turn_count is not None:
            return self.visible_turn_count
        return len(self.messages)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_bytes(raw: bytes):
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            return json.loads(raw.decode(encoding))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return json.loads(raw.decode("utf-8", errors="replace"))


def decode_text_bytes(raw: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def resolve_path(value: str | None, base_dir: Path) -> Path | None:
    if not value:
        return None
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_dir / candidate).resolve()


def resolve_workspace_vault(config_path: Path) -> Path:
    return (config_path.parent / "vault").resolve()


def normalize_space(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n").replace("\r", "\n")).strip()


def collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.strip())


def make_forward_slashes(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def timestamp_to_datetime(value: float | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value))
    except (TypeError, ValueError, OSError):
        return None


def parse_datetime_string(value: str | None) -> float | None:
    if not value:
        return None
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), pattern).timestamp()
        except ValueError:
            continue
    return None


def parse_flexible_datetime(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    direct = parse_datetime_string(value)
    if direct is not None:
        return direct
    for pattern in ("%B %d, %Y at %I:%M %p", "%b %d, %Y at %I:%M %p"):
        try:
            return datetime.strptime(value, pattern).timestamp()
        except ValueError:
            continue
    return None


def timestamp_from_filename_stem(stem: str) -> float | None:
    match = TIMESTAMP_IN_NAME_RE.search(stem)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d-%H-%M-%S").timestamp()
    except ValueError:
        return None


def stable_short_hash(text: str, length: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def timestamp_to_date(value: float | None) -> str:
    dt = timestamp_to_datetime(value)
    return dt.strftime("%Y-%m-%d") if dt else "unknown"


def timestamp_to_display(value: float | None) -> str:
    dt = timestamp_to_datetime(value)
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "unknown"


def current_display_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def append_unique_lines(path: Path, lines: Iterable[str]):
    existing = ""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    additions = [line for line in lines if line and line not in existing]
    if not additions:
        return
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(prefix + "\n".join(additions) + "\n")


def safe_append_unique_lines(path: Path, lines: Iterable[str]):
    try:
        append_unique_lines(path, lines)
    except OSError:
        return


def yaml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_frontmatter(data: dict) -> str:
    lines: list[str] = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {yaml_quote(str(item))}")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            lines.append(f"{key}: {value}")
        elif value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {yaml_quote(str(value))}")
    lines.append("---")
    return "\n".join(lines)


def parse_scalar(value: str):
    stripped = value.strip()
    if stripped in {"true", "false"}:
        return stripped == "true"
    if stripped == "null":
        return None
    if stripped.startswith('"') or stripped.startswith("[") or stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return stripped
    if re.fullmatch(r"-?\d+", stripped):
        return int(stripped)
    if re.fullmatch(r"-?\d+\.\d+", stripped):
        return float(stripped)
    return stripped


def parse_frontmatter_block(content: str) -> tuple[dict, str]:
    if not content.startswith("---\n"):
        return {}, content
    parts = content.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, content
    frontmatter_text = parts[0][4:]
    body = parts[1]
    data: dict[str, object] = {}
    current_key: str | None = None
    current_list: list[object] | None = None
    for line in frontmatter_text.splitlines():
        if line.startswith("  - ") and current_key and current_list is not None:
            current_list.append(parse_scalar(line[4:]))
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if raw_value == "":
            current_key = key
            current_list = []
            data[key] = current_list
        else:
            current_key = None
            current_list = None
            data[key] = parse_scalar(raw_value)
    return data, body


def sanitize_filename(text: str, max_length: int = 72) -> str:
    value = re.sub(r'[<>:"/\\\\|?*]+', " ", text).strip()
    value = re.sub(r"\s+", " ", value)
    value = value.replace(".", " ").replace(":", " ")
    value = value.strip(" -_")
    if not value:
        value = "untitled"
    if len(value) > max_length:
        value = value[:max_length].rstrip()
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value or "untitled"


def trim_preview(text: str, limit: int = 180) -> str:
    value = normalize_space(text).replace("\n", " ")
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def wiki_target(path: Path, vault_root: Path) -> str:
    relative = path.relative_to(vault_root)
    if relative.suffix.lower() == ".md":
        relative = relative.with_suffix("")
    return make_forward_slashes(relative)


def extract_note_title(content: str) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            title = re.sub(r"^(摘要｜|正文｜)", "", title)
            return title.strip()
    return "Untitled"


def extract_text_from_part(part) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, dict):
        for key in ("text", "content", "result", "summary"):
            value = part.get(key)
            if isinstance(value, str):
                return value
        if "parts" in part and isinstance(part["parts"], list):
            return "\n".join(filter(None, (extract_text_from_part(item) for item in part["parts"])))
    return ""


def extract_visible_text(message: dict) -> str:
    content = message.get("content") or {}
    if not isinstance(content, dict):
        return normalize_space(str(content))
    content_type = content.get("content_type")
    if content_type not in VISIBLE_CONTENT_TYPES:
        return ""
    parts = content.get("parts")
    if isinstance(parts, list):
        chunks = [extract_text_from_part(part) for part in parts]
        return collapse_blank_lines("\n".join(chunk for chunk in chunks if chunk))
    for key in ("text", "result", "summary"):
        value = content.get(key)
        if isinstance(value, str):
            return collapse_blank_lines(value)
    return ""


def ordered_nodes(mapping: dict, current_node: str | None) -> list[dict]:
    if current_node and current_node in mapping:
        chain = []
        node_id = current_node
        seen = set()
        while node_id and node_id in mapping and node_id not in seen:
            seen.add(node_id)
            node = mapping[node_id]
            chain.append(node)
            node_id = node.get("parent")
        chain.reverse()
        return chain
    nodes = list(mapping.values())
    nodes.sort(
        key=lambda node: (
            ((node.get("message") or {}).get("create_time") or 0),
            node.get("id") or "",
        )
    )
    return nodes


def infer_provider_from_url(url: str | None) -> str:
    if not url:
        return "Unknown"
    lowered = url.lower()
    if "gemini.google.com" in lowered:
        return "Gemini"
    if "claude.ai" in lowered:
        return "Claude"
    if "kimi.moonshot.cn" in lowered or "moonshot.cn" in lowered:
        return "Kimi"
    if "deepseek.com" in lowered:
        return "DeepSeek"
    if "chatgpt.com" in lowered or "chat.openai.com" in lowered:
        return "ChatGPT"
    return "Unknown"


def infer_provider_from_entry(source_entry: str) -> str:
    lowered = Path(source_entry).stem.lower()
    if lowered.startswith("gemini_"):
        return "Gemini"
    if lowered.startswith("claude_"):
        return "Claude"
    if lowered.startswith("kimi_"):
        return "Kimi"
    if lowered.startswith("deepseek_"):
        return "DeepSeek"
    if lowered.startswith("chatgpt_"):
        return "ChatGPT"
    return "Unknown"


def role_from_memo_label(label: str) -> str:
    lowered = label.lower()
    if lowered == "user":
        return "user"
    if lowered in {"ai", "assistant"}:
        return "assistant"
    return "assistant"


def record_sort_key(record: ConversationRecord):
    return (record.created_at or 0, record.title.lower(), record.conversation_id.lower())


def summarize_provider_counts(items: list[ConversationRecord]) -> Counter:
    return Counter(item.provider for item in items)


def parse_chatgpt_json_conversation(source_zip: Path, source_entry: str, payload: dict) -> ConversationRecord:
    ordered = ordered_nodes(payload.get("mapping") or {}, payload.get("current_node"))
    messages: list[Message] = []
    for node in ordered:
        message = node.get("message")
        if not message:
            continue
        role = ((message.get("author") or {}).get("role")) or ""
        if role not in {"user", "assistant"}:
            continue
        text = extract_visible_text(message)
        if not text:
            continue
        messages.append(Message(role=role, text=text, created_at=message.get("create_time")))

    title = payload.get("title") or Path(source_entry).stem
    model = payload.get("default_model_slug") or payload.get("model_slug") or "unknown"
    return ConversationRecord(
        title=title,
        conversation_id=payload.get("conversation_id") or Path(source_entry).stem,
        source_entry=source_entry,
        source_zip=make_forward_slashes(source_zip),
        created_at=payload.get("create_time"),
        updated_at=payload.get("update_time"),
        model=model,
        messages=messages,
        provider="ChatGPT",
        source_kind="chatgpt-json-backup",
        source_url=payload.get("safe_urls") if isinstance(payload.get("safe_urls"), str) else None,
        corpus_key="chatgpt-business-backup",
    )


def parse_memo_text_conversation(source_zip: Path, source_entry: str, raw_text: str) -> ConversationRecord:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    header: dict[str, str] = {}
    body_start = 0
    lines = text.split("\n")
    for idx, line in enumerate(lines):
        if not line.strip():
            body_start = idx + 1
            break
        match = MEMO_HEADER_RE.match(line.strip())
        if match:
            header[match.group(1).lower()] = match.group(2).strip()
        else:
            body_start = idx
            break

    body = "\n".join(lines[body_start:]).strip()
    messages: list[Message] = []
    matches = list(MEMO_MESSAGE_RE.finditer(body))
    for index, match in enumerate(matches):
        role = role_from_memo_label(match.group(1))
        created_at = parse_datetime_string(match.group(2))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        content = collapse_blank_lines(body[start:end].strip())
        if not content:
            continue
        messages.append(Message(role=role, text=content, created_at=created_at))

    provider = header.get("platform") or infer_provider_from_url(header.get("url"))
    if not provider or provider == "Unknown":
        provider = infer_provider_from_entry(source_entry)
    created_at = parse_datetime_string(header.get("created"))
    if messages:
        created_at = created_at or messages[0].created_at
    updated_at = messages[-1].created_at if messages else created_at
    source_stem = Path(source_entry).stem
    title = header.get("title") or source_stem
    return ConversationRecord(
        title=title,
        conversation_id=source_stem,
        source_entry=source_entry,
        source_zip=make_forward_slashes(source_zip),
        created_at=created_at,
        updated_at=updated_at,
        model=provider or "unknown",
        messages=messages,
        provider=provider or "Unknown",
        source_kind="memo-text-export",
        source_url=header.get("url"),
        corpus_key="conversation-memo-backup",
    )


def normalize_export_title(title: str) -> str:
    value = title.strip().replace("_", " ")
    value = re.sub(r"^(?:Branch|branch)\s*[·:：-]\s*", "", value)
    value = re.sub(r"^分支\s*[·:：-]\s*", "", value)
    return normalize_space(value) or "Untitled"


def classify_markdown_response_export(title: str, text: str) -> tuple[str, str]:
    fragment_openers = (
        "我先",
        "先说",
        "先给",
        "下面我",
        "你这",
        "对这个",
        "我继续",
        "我检查",
        "我直接",
        "我已经",
        "我把",
        "可以",
        "作为AI",
        "针对您",
        "我会",
    )
    draft_terms = (
        "综述",
        "研究",
        "理论",
        "报告",
        "排版",
        "方案",
        "迁移",
        "检索式",
        "写法",
        "解法",
    )
    title = title.strip()
    preview = clean_markdown_export_text(text)[:120].strip()
    if title.startswith(fragment_openers) or preview.startswith(fragment_openers):
        return "dialogue-fragment", "Starts with a conversational assistant opener."
    if any(term in title for term in draft_terms):
        return "research-draft", "Title reads like a standalone write-up or drafted output."
    return "dialogue-fragment", "Defaulted to assistant response fragment because the export contains one visible answer."


def clean_markdown_export_text(text: str) -> str:
    value = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    value = UPLOAD_PLACEHOLDER_RE.sub("[Uploaded images omitted]", value)
    value = MARKDOWN_IMAGE_LINE_RE.sub("", value)
    return collapse_blank_lines(value)


def parse_markdown_chat_conversation(source_zip: Path, source_entry: str, raw_text: str) -> ConversationRecord:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    title = normalize_export_title(lines[0][2:].strip()) if lines and lines[0].startswith("# ") else normalize_export_title(Path(source_entry).stem)

    source_match = MARKDOWN_CHAT_SOURCE_RE.search(text)
    source_url = source_match.group("url") if source_match else None
    provider = infer_provider_from_url(source_url) or "Unknown"
    source_label = source_match.group("label") if source_match else ""
    if provider == "Unknown" and "gemini" in source_label.lower():
        provider = "Gemini"

    created_at = None
    date_match = MARKDOWN_CHAT_DATE_RE.search(text)
    if date_match:
        created_at = parse_flexible_datetime(date_match.group(1))

    turn_matches = list(MARKDOWN_TURN_SPLIT_RE.finditer(text))
    messages: list[Message] = []
    for turn_index, turn_match in enumerate(turn_matches):
        start = turn_match.end()
        end = turn_matches[turn_index + 1].start() if turn_index + 1 < len(turn_matches) else len(text)
        turn_body = text[start:end].strip()
        role_matches = list(MARKDOWN_ROLE_RE.finditer(turn_body))
        for role_index, role_match in enumerate(role_matches):
            role_start = role_match.end()
            role_end = role_matches[role_index + 1].start() if role_index + 1 < len(role_matches) else len(turn_body)
            role_label = role_match.group(1)
            role = role_from_memo_label(role_label)
            content = clean_markdown_export_text(turn_body[role_start:role_end].strip())
            if not content:
                continue
            messages.append(Message(role=role, text=content, created_at=created_at))

    content_hash = stable_short_hash(f"{title}\n{source_url or ''}\n{text}")
    conversation_id = content_hash
    if source_url and "/app/" in source_url:
        conversation_id = source_url.rstrip("/").split("/")[-1]

    return ConversationRecord(
        title=title,
        conversation_id=conversation_id,
        source_entry=source_entry,
        source_zip=make_forward_slashes(source_zip),
        created_at=created_at,
        updated_at=created_at,
        model=provider or "unknown",
        messages=messages,
        provider=provider or "Unknown",
        source_kind="markdown-chat-export",
        source_url=source_url,
        corpus_key="conversation-memo-backup",
    )


def parse_markdown_response_export(source_zip: Path, source_entry: str, raw_text: str) -> ConversationRecord:
    source_stem = Path(source_entry).stem
    stem_match = RESPONSE_EXPORT_STEM_RE.match(source_stem)
    if stem_match:
        title = normalize_export_title(stem_match.group("title"))
        created_at = timestamp_from_filename_stem(source_stem)
    else:
        title = normalize_export_title(source_stem)
        created_at = timestamp_from_filename_stem(source_stem)

    text = clean_markdown_export_text(raw_text)
    archive_class, archive_reason = classify_markdown_response_export(title, text)
    conversation_id = f"md-{stable_short_hash(f'{source_entry}\\n{text}')}"
    provider = "Standalone Export"
    return ConversationRecord(
        title=title,
        conversation_id=conversation_id,
        source_entry=source_entry,
        source_zip=make_forward_slashes(source_zip),
        created_at=created_at,
        updated_at=created_at,
        model=provider,
        messages=[Message(role="assistant", text=text, created_at=created_at)],
        provider=provider,
        source_kind="markdown-response-export",
        source_url=None,
        corpus_key="conversation-memo-backup",
        archive_class=archive_class,
        archive_class_reason=archive_reason,
    )


def looks_like_markdown_response_export(path: Path, raw_text: str) -> bool:
    if RESPONSE_EXPORT_STEM_RE.match(path.stem):
        return True
    if path.name.lower() == "chat.md" and "**Source**:" in raw_text and "## Turn " in raw_text:
        return True
    return False


def looks_like_memo_text_export(raw_text: str) -> bool:
    return "Messages:" in raw_text and ("User:" in raw_text or "AI:" in raw_text or "Assistant:" in raw_text)


def parse_markdown_file_conversation(source_zip: Path, source_entry: str, raw_text: str) -> list[ConversationRecord]:
    path = Path(source_entry)
    if path.name.lower() == "chat.md" and "**Source**:" in raw_text and "## Turn " in raw_text:
        return [parse_markdown_chat_conversation(source_zip, source_entry, raw_text)]
    if looks_like_markdown_response_export(path, raw_text):
        return [parse_markdown_response_export(source_zip, source_entry, raw_text)]
    return []


def collect_records_from_file(path: Path, source_root: Path | None = None) -> list[ConversationRecord]:
    source_entry = make_forward_slashes(path.relative_to(source_root)) if source_root else path.name
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            payload = load_json(path)
        except (UnicodeDecodeError, json.JSONDecodeError, OSError):
            return []
        if isinstance(payload, dict) and ("mapping" in payload or "current_node" in payload):
            return [parse_chatgpt_json_conversation(path, source_entry, payload)]
        return []
    if suffix == ".txt":
        try:
            raw_text = decode_text_bytes(path.read_bytes())
        except OSError:
            return []
        if looks_like_memo_text_export(raw_text):
            return [parse_memo_text_conversation(path, source_entry, raw_text)]
        return []
    if suffix == ".md":
        try:
            raw_text = decode_text_bytes(path.read_bytes())
        except OSError:
            return []
        return parse_markdown_file_conversation(path, source_entry, raw_text)
    return []


def zip_contains_supported_payload(path: Path) -> bool:
    if any(hint in path.name.lower() for hint in ZIP_CONVERSATION_NAME_HINTS):
        return True
    try:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                lowered = name.lower()
                if lowered.endswith(".json"):
                    try:
                        payload = load_json_bytes(archive.read(name))
                    except Exception:
                        continue
                    if isinstance(payload, dict) and ("mapping" in payload or "current_node" in payload):
                        return True
                elif lowered.endswith(".txt"):
                    raw_text = decode_text_bytes(archive.read(name))
                    if looks_like_memo_text_export(raw_text):
                        return True
                elif lowered.endswith(".md"):
                    raw_text = decode_text_bytes(archive.read(name))
                    if parse_markdown_file_conversation(path, name, raw_text):
                        return True
    except zipfile.BadZipFile:
        return False
    return False


def discover_conversation_sources(scan_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for path in sorted(scan_dir.iterdir()):
        if not path.is_file():
            continue
        include = False
        suffix = path.suffix.lower()
        if suffix == ".zip":
            include = zip_contains_supported_payload(path)
        elif suffix in {".json", ".txt", ".md"}:
            include = bool(collect_records_from_file(path))
        if include:
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                candidates.append(resolved)
    return candidates


def score_buckets(record: ConversationRecord):
    searchable_text = "\n".join(
        [
            record.title,
            record.provider,
            "\n".join(message.text for message in record.messages[:10]),
        ]
    ).lower()
    hits: dict[str, int] = {}
    matched_terms: dict[str, list[str]] = defaultdict(list)
    for bucket in TOPIC_BUCKETS:
        score = 0
        for term in bucket["keywords"]:
            lowered = term.lower()
            if lowered in searchable_text:
                score += searchable_text.count(lowered)
                matched_terms[bucket["slug"]].append(term)
        if score:
            hits[bucket["slug"]] = score

    if not hits:
        record.primary_buckets = [FALLBACK_BUCKET["slug"]]
        record.matched_terms = []
        return

    ranked = sorted(hits.items(), key=lambda item: item[1], reverse=True)
    top_score = ranked[0][1]
    selected = [slug for slug, score in ranked if score >= max(1, top_score // 2)]
    record.primary_buckets = selected[:3]
    merged_terms = []
    for slug in record.primary_buckets:
        merged_terms.extend(matched_terms.get(slug, []))
    record.matched_terms = sorted(dict.fromkeys(merged_terms))


def bucket_by_slug(slug: str) -> dict:
    for bucket in TOPIC_BUCKETS:
        if bucket["slug"] == slug:
            return bucket
    return FALLBACK_BUCKET


def slug_from_label(label: str) -> str:
    for bucket in TOPIC_BUCKETS:
        if bucket["label"] == label:
            return bucket["slug"]
    if label == FALLBACK_BUCKET["label"]:
        return FALLBACK_BUCKET["slug"]
    return FALLBACK_BUCKET["slug"]


def load_records_from_summary_tree(
    summaries_root: Path,
    readable_transcripts_root: Path,
    corpus_key: str,
) -> list[ConversationRecord]:
    records: list[ConversationRecord] = []
    if not summaries_root.exists():
        return records
    for note_path in sorted(summaries_root.rglob("*.md")):
        if note_path.name == "_Index.md":
            continue
        content = note_path.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter_block(content)
        title = extract_note_title(body)
        topic_labels = frontmatter.get("topic_buckets") or []
        if not isinstance(topic_labels, list):
            topic_labels = []
        transcript_path = readable_transcripts_root / note_path.relative_to(summaries_root)
        record = ConversationRecord(
            title=title,
            conversation_id=str(frontmatter.get("conversation_id") or note_path.stem),
            source_entry=str(frontmatter.get("source_entry") or ""),
            source_zip=str(frontmatter.get("source_zip") or ""),
            created_at=parse_datetime_string(str(frontmatter.get("created_at") or "")),
            updated_at=parse_datetime_string(str(frontmatter.get("updated_at") or "")),
            model=str(frontmatter.get("model") or "unknown"),
            messages=[],
            provider=str(frontmatter.get("provider") or "Unknown"),
            source_kind=str(frontmatter.get("source_kind") or "unknown"),
            source_url=frontmatter.get("source_url") if isinstance(frontmatter.get("source_url"), str) else None,
            corpus_key=corpus_key,
            primary_buckets=[slug_from_label(str(label)) for label in topic_labels],
            matched_terms=[str(item) for item in (frontmatter.get("keywords") or []) if str(item)],
            note_path=note_path,
            transcript_path=transcript_path if transcript_path.exists() else None,
            visible_turn_count=int(frontmatter.get("visible_turns") or 0),
            user_turn_count=int(frontmatter.get("user_turns") or 0),
            assistant_turn_count=int(frontmatter.get("assistant_turns") or 0),
            archive_class=frontmatter.get("archive_class") if isinstance(frontmatter.get("archive_class"), str) else None,
            archive_class_reason=frontmatter.get("archive_class_reason") if isinstance(frontmatter.get("archive_class_reason"), str) else None,
        )
        records.append(record)
    records.sort(key=record_sort_key)
    return records


def monthly_folder_name(record: ConversationRecord) -> str:
    dt = timestamp_to_datetime(record.created_at)
    if not dt:
        return "unknown-date"
    return dt.strftime("%Y-%m")


def is_writing_output(record: ConversationRecord) -> bool:
    return record.source_kind == "markdown-response-export" and record.archive_class == "research-draft"


def conversation_filename(record: ConversationRecord) -> str:
    dt = timestamp_to_datetime(record.created_at)
    date_prefix = dt.strftime("%Y-%m-%d-%H%M%S") if dt else "unknown-date"
    title_slug = sanitize_filename(record.title)
    short_id = sanitize_filename(record.conversation_id.split("-")[-1], max_length=24)
    return f"{date_prefix}-{title_slug}-{short_id}.md"


def transcript_filename(record: ConversationRecord) -> str:
    return conversation_filename(record)


def clean_citation_artifacts(text: str) -> str:
    value = PRIVATE_USE_RE.sub("", text)
    value = BRACKET_CITATION_RE.sub("", value)
    value = ARTIFACT_TOKEN_RE.sub("", value)
    value = INLINE_CITE_RE.sub("", value)
    value = re.sub(r"(?m)^\s*\+1\s*$", "", value)
    value = re.sub(r"(?m)^\s*(User|Assistant|AI)\s*$", "", value)
    return collapse_blank_lines(value)


def normalize_bullet_lines(text: str) -> str:
    lines = text.split("\n")
    normalized: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("●", "•", "▪", "◦")):
            normalized.append(f"- {stripped[1:].strip()}")
        else:
            normalized.append(line.rstrip())
    return "\n".join(normalized).strip()


def normalize_display_math(text: str) -> str:
    lines = text.split("\n")
    output: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].strip() == r"\[":
            end = index + 1
            block: list[str] = []
            while end < len(lines) and lines[end].strip() != r"\]":
                block.append(lines[end].rstrip())
                end += 1
            if end < len(lines):
                non_empty = [line for line in block if line.strip()]
                if len(non_empty) == 1:
                    output.extend(["$$", non_empty[0].strip(), "$$"])
                elif non_empty:
                    output.append(r"\[")
                    output.extend(non_empty)
                    output.append(r"\]")
                index = end + 1
                continue
        output.append(lines[index].rstrip())
        index += 1
    return "\n".join(output).strip()


def clean_message_text(text: str) -> str:
    value = normalize_space(text)
    value = value.replace("。  ", "。\n\n")
    value = clean_citation_artifacts(value)
    value = normalize_bullet_lines(value)
    value = normalize_display_math(value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def is_meta_status_message(message: Message) -> bool:
    if message.role != "assistant":
        return False
    text = normalize_space(message.text)
    if len(text) > 260:
        return False
    if any(marker in text for marker in ("##", "###", "|", "$$", r"\[")):
        return False
    markers = [
        "我先",
        "我会",
        "接下来",
        "我刚",
        "我已经把",
        "现在我会",
        "下面我会",
        "我准备",
        "Let me",
        "I will",
    ]
    return any(marker in text for marker in markers)


def build_readable_blocks(record: ConversationRecord) -> list[Message]:
    cleaned: list[Message] = []
    for message in record.messages:
        text = clean_message_text(message.text)
        if not text:
            continue
        cleaned.append(Message(role=message.role, text=text, created_at=message.created_at))

    runs: list[list[Message]] = []
    for message in cleaned:
        if runs and runs[-1][-1].role == message.role:
            runs[-1].append(message)
        else:
            runs.append([message])

    blocks: list[Message] = []
    for run in runs:
        selected = run
        if run[0].role == "assistant":
            substantive = [item for item in run if not is_meta_status_message(item)]
            if substantive:
                selected = substantive
        merged_text = "\n\n".join(item.text for item in selected).strip()
        if not merged_text:
            continue
        blocks.append(
            Message(
                role=run[0].role,
                text=merged_text,
                created_at=selected[0].created_at,
            )
        )
    return blocks


def first_user_requests(record: ConversationRecord, limit: int = 5) -> list[str]:
    requests = [trim_preview(message.text) for message in record.messages if message.role == "user"]
    return requests[:limit]


def last_assistant_preview(record: ConversationRecord) -> str:
    assistant_messages = [message for message in record.messages if message.role == "assistant"]
    if not assistant_messages:
        return "No assistant response captured."
    return trim_preview(assistant_messages[-1].text, limit=320)


def rendered_bucket_labels(record: ConversationRecord) -> str:
    labels = [bucket_by_slug(slug)["label"] for slug in record.primary_buckets]
    return " / ".join(labels) if labels else FALLBACK_BUCKET["label"]


def rendered_targets(record: ConversationRecord) -> list[str]:
    targets: list[str] = []
    for slug in record.primary_buckets:
        targets.extend(bucket_by_slug(slug).get("targets", []))
    return list(dict.fromkeys(targets))


def layout_for_corpus(vault_root: Path, corpus_key: str) -> CorpusLayout:
    if corpus_key == "chatgpt-business-backup":
        return CorpusLayout(
            corpus_name="ChatGPT Business Archive",
            corpus_slug="chatgpt-business-backup",
            transcript_group="chatgpt-archive",
            topic_note_path=vault_root / "03_Concepts" / "10_Conversation-Archives" / "ChatGPT-Conversation-Topic-Atlas-Archive.md",
            capability_note_path=vault_root / "07_Profiles" / "05_Conversation-Archives" / "ChatGPT-Conversation-Capability-Library-Archive.md",
            progress_note_path=vault_root / "04_Progress" / f"{datetime.now().strftime('%Y-%m-%d')}-chatgpt-archive-import-and-learning.md",
        )
    return CorpusLayout(
        corpus_name="Conversation Memo Archive",
        corpus_slug="conversation-memo-backup",
        transcript_group="conversation-archive",
        topic_note_path=vault_root / "03_Concepts" / "10_Conversation-Archives" / "Conversation-Memo-Topic-Atlas-Archive.md",
        capability_note_path=vault_root / "07_Profiles" / "05_Conversation-Archives" / "Conversation-Memo-Capability-Library-Archive.md",
        progress_note_path=vault_root / "04_Progress" / f"{datetime.now().strftime('%Y-%m-%d')}-conversation-archive-import-and-learning.md",
    )


def build_transcript_note(record: ConversationRecord, vault_root: Path, corpus_name: str) -> str:
    readable_blocks = build_readable_blocks(record)
    frontmatter = yaml_frontmatter(
        {
            "note_type": "conversation-backup-transcript",
            "source_kind": record.source_kind,
            "provider": record.provider,
            "conversation_id": record.conversation_id,
            "source_entry": record.source_entry,
            "source_zip": record.source_zip,
            "source_url": record.source_url,
            "created_at": timestamp_to_display(record.created_at),
            "updated_at": timestamp_to_display(record.updated_at),
            "model": record.model,
            "visible_turns": record.visible_turns,
            "user_turns": record.user_turns,
            "assistant_turns": record.assistant_turns,
            "topic_buckets": [bucket_by_slug(slug)["label"] for slug in record.primary_buckets],
            "archive_class": record.archive_class,
            "archive_class_reason": record.archive_class_reason,
        }
    )
    sections = [
        frontmatter,
        "",
        f"# 正文｜{record.title}",
        "",
        f"Keywords: {', '.join(record.matched_terms) if record.matched_terms else rendered_bucket_labels(record)}",
        "",
        "## Snapshot",
        "",
        f"- Corpus: {corpus_name}",
        f"- Provider: `{record.provider}`",
        f"- Source kind: `{record.source_kind}`",
        f"- Conversation ID: `{record.conversation_id}`",
        f"- Source entry: `{record.source_entry}`",
        f"- Source zip: `{record.source_zip}`",
        f"- Source URL: `{record.source_url or 'unknown'}`",
        f"- Created: {timestamp_to_display(record.created_at)}",
        f"- Updated: {timestamp_to_display(record.updated_at)}",
        f"- Model: `{record.model}`",
        f"- Source summary: [[{wiki_target(record.note_path, vault_root)}|摘要页]]" if record.note_path else "- Source summary: unavailable",
        f"- Visible turns: {record.visible_turns} (user {record.user_turns} / assistant {record.assistant_turns})",
        f"- Readable blocks: {len(readable_blocks)}",
        f"- Archive class: `{record.archive_class}`" if record.archive_class else None,
        f"- Archive class note: {record.archive_class_reason}" if record.archive_class_reason else None,
        "",
        "## 阅读正文",
        "",
    ]
    user_index = 0
    assistant_index = 0
    for message in readable_blocks:
        if message.role == "user":
            user_index += 1
            role_label = "问题" if user_index == 1 else f"追问 {user_index}"
        else:
            assistant_index += 1
            role_label = "回答" if assistant_index == 1 else f"补充 {assistant_index}"
        sections.append(f"## {role_label}")
        sections.append("")
        sections.append(message.text.strip())
        sections.append("")
    return "\n".join(line for line in sections if line is not None)


def build_conversation_note(record: ConversationRecord, vault_root: Path, corpus_name: str) -> str:
    transcript_link = (
        f"[[{wiki_target(record.transcript_path, vault_root)}|阅读版正文]]"
        if record.transcript_path
        else "Transcript not generated."
    )
    targets = rendered_targets(record)
    target_lines = [f"- `{target}`" for target in targets] or ["- `09_Conversations`"]
    request_lines = [f"- {item}" for item in first_user_requests(record)] or ["- No user request preview captured."]
    keywords = ", ".join(record.matched_terms) if record.matched_terms else rendered_bucket_labels(record)
    frontmatter = yaml_frontmatter(
        {
            "note_type": "conversation-backup-note",
            "source_kind": record.source_kind,
            "provider": record.provider,
            "conversation_id": record.conversation_id,
            "source_entry": record.source_entry,
            "source_zip": record.source_zip,
            "source_url": record.source_url,
            "created_at": timestamp_to_display(record.created_at),
            "updated_at": timestamp_to_display(record.updated_at),
            "model": record.model,
            "visible_turns": record.visible_turns,
            "user_turns": record.user_turns,
            "assistant_turns": record.assistant_turns,
            "topic_buckets": [bucket_by_slug(slug)["label"] for slug in record.primary_buckets],
            "keywords": record.matched_terms,
            "archive_class": record.archive_class,
            "archive_class_reason": record.archive_class_reason,
        }
    )
    summary = (
        f"This thread was restored from {corpus_name}. "
        f"It belongs to provider `{record.provider}` and routes mainly to {rendered_bucket_labels(record)}. "
        f"The restored branch contains {record.visible_turns} visible turns."
    )
    sections = [
        frontmatter,
        "",
        f"# 摘要｜{record.title}",
        "",
        f"Keywords: {keywords}",
        "",
        "## Summary",
        "",
        summary,
        "",
        "## Snapshot",
        "",
        f"- Provider: `{record.provider}`",
        f"- Source kind: `{record.source_kind}`",
        f"- Conversation ID: `{record.conversation_id}`",
        f"- Created: {timestamp_to_display(record.created_at)}",
        f"- Updated: {timestamp_to_display(record.updated_at)}",
        f"- Model: `{record.model}`",
        f"- Source URL: `{record.source_url or 'unknown'}`",
        f"- Visible turns: {record.visible_turns} (user {record.user_turns} / assistant {record.assistant_turns})",
        f"- Archive class: `{record.archive_class}`" if record.archive_class else None,
        f"- Archive class note: {record.archive_class_reason}" if record.archive_class_reason else None,
        f"- Transcript: {transcript_link}",
        "",
        "## First User Requests",
        "",
        *request_lines,
        "",
        "## Final Assistant Preview",
        "",
        last_assistant_preview(record),
        "",
        "## Suggested Landing Zones",
        "",
        *target_lines,
        "",
        "## Source Trace",
        "",
        f"- Backup entry: `{record.source_entry}`",
        f"- Backup zip: `{record.source_zip}`",
        "",
    ]
    return "\n".join(line for line in sections if line is not None)


def ensure_daily_note(vault_root: Path, daily_folder: str, record: ConversationRecord):
    date_value = timestamp_to_date(record.created_at)
    if date_value == "unknown":
        return
    daily_path = vault_root / daily_folder / f"{date_value}.md"
    if not daily_path.exists():
        write_text(daily_path, DEFAULT_DAILY_TEMPLATE.format(date=date_value))
    link_line = f"- [[{wiki_target(record.note_path, vault_root)}]]"
    content = daily_path.read_text(encoding="utf-8")
    if link_line in content:
        return
    if "## Conversation update" not in content:
        content = content.rstrip() + "\n\n## Conversation update\n\n"
    elif not content.endswith("\n"):
        content += "\n"
    content += link_line + "\n"
    write_text(daily_path, content)


def build_month_index(
    month: str,
    items: list[ConversationRecord],
    vault_root: Path,
    corpus_name: str,
    folder_split: str = "`Summaries/` and `Readable Transcripts/`",
) -> str:
    rows = [
        f"# {corpus_name} Conversation Index - {month}",
        "",
        f"- Conversations: {len(items)}",
        f"- Folder split: {folder_split}",
        "",
        "| Date | Provider | Title | Topics | Turns | Model | Summary | Readable Transcript |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for item in items:
        note_link = f"[[{wiki_target(item.note_path, vault_root)}|Summary]]"
        transcript_link = f"[[{wiki_target(item.transcript_path, vault_root)}|Readable]]"
        rows.append(
            "| {date} | `{provider}` | {title} | {topics} | {turns} | `{model}` | {note} | {transcript} |".format(
                date=timestamp_to_date(item.created_at),
                provider=item.provider,
                title=item.title.replace("|", "/"),
                topics=rendered_bucket_labels(item).replace("|", "/"),
                turns=item.visible_turns,
                model=item.model,
                note=note_link,
                transcript=transcript_link,
            )
        )
    return "\n".join(rows)


def build_root_conversation_index(
    layout: CorpusLayout,
    items: list[ConversationRecord],
    month_index_paths: dict[str, Path],
    manifest_relpath: str,
    vault_root: Path,
    extra_view_paths: list[tuple[str, Path]] | None = None,
) -> str:
    model_counts = Counter(item.model for item in items)
    provider_counts = summarize_provider_counts(items)
    bucket_counts = Counter()
    for item in items:
        bucket_counts.update(item.primary_buckets)
    rows = [
        f"# {layout.corpus_name} Conversation Library",
        "",
        f"- Generated: {current_display_timestamp()}",
        f"- Conversations: {len(items)}",
        f"- Date range: {timestamp_to_date(items[0].created_at)} -> {timestamp_to_date(items[-1].created_at)}" if items else "- Date range: unknown",
        f"- Latest import manifest: `08_Attachments/{manifest_relpath}`",
        "- Summary folder: `Summaries/`",
        "- Readable transcript folder: `Readable Transcripts/`",
        "",
        "## Provider Mix",
        "",
    ]
    for provider, count in provider_counts.most_common():
        rows.append(f"- `{provider}`: {count}")
    rows.extend(["", "## Model Mix", ""])
    for model, count in model_counts.most_common():
        rows.append(f"- `{model}`: {count}")
    rows.extend(["", "## Topic Buckets", ""])
    for slug, count in bucket_counts.most_common():
        rows.append(f"- {bucket_by_slug(slug)['label']}: {count}")
    rows.extend(["", "## Month Indexes", ""])
    for month, path in sorted(month_index_paths.items()):
        rows.append(f"- [[{wiki_target(path, vault_root)}|{month}]]")
    if extra_view_paths:
        rows.extend(["", "## Extra Views", ""])
        for label, path in extra_view_paths:
            rows.append(f"- [[{wiki_target(path, vault_root)}|{label}]]")
    rows.extend(["", "## Top Threads By Size", ""])
    for item in sorted(items, key=lambda entry: entry.visible_turns, reverse=True)[:10]:
        rows.append(
            f"- [[{wiki_target(item.note_path, vault_root)}|{item.title}]]"
            f" ({item.visible_turns} turns, {item.provider}, {rendered_bucket_labels(item)})"
        )
    return "\n".join(rows)


def build_writing_outputs_index(
    items: list[ConversationRecord],
    month_index_paths: dict[str, Path],
    manifest_relpath: str,
    vault_root: Path,
) -> str:
    rows = [
        "# Conversation Memo Writing Outputs",
        "",
        f"- Generated: {current_display_timestamp()}",
        f"- Outputs: {len(items)}",
        f"- Date range: {timestamp_to_date(items[0].created_at)} -> {timestamp_to_date(items[-1].created_at)}" if items else "- Date range: unknown",
        f"- Latest import manifest: `08_Attachments/{manifest_relpath}`",
        "- Summary folder: `Writing Outputs/Summaries/`",
        "- Readable draft folder: `Writing Outputs/Readable Drafts/`",
        "",
        "## Why This Exists",
        "",
        "These notes were exported as one-sided markdown drafts rather than true back-and-forth conversations, so they are kept separate from dialogue archives.",
        "",
        "## Month Indexes",
        "",
    ]
    for month, path in sorted(month_index_paths.items()):
        rows.append(f"- [[{wiki_target(path, vault_root)}|{month}]]")
    rows.extend(["", "## Outputs", ""])
    for item in items:
        rows.append(
            f"- [[{wiki_target(item.note_path, vault_root)}|{item.title}]]"
            f" ({timestamp_to_date(item.created_at)}, {item.provider})"
        )
    return "\n".join(rows)


def build_topic_atlas(items: list[ConversationRecord], corpus_name: str) -> str:
    grouped: dict[str, list[ConversationRecord]] = defaultdict(list)
    for item in items:
        for slug in item.primary_buckets:
            grouped[slug].append(item)

    provider_counts = summarize_provider_counts(items)
    frontmatter = yaml_frontmatter(
        {
            "note_type": "conversation-backup-topic-atlas",
            "generated_by": "import_chatgpt_backup_to_vault.py",
            "generated_at": current_display_timestamp(),
            "corpus_name": corpus_name,
            "conversation_count": len(items),
        }
    )
    lines = [
        frontmatter,
        "",
        f"# {corpus_name} Topic Atlas",
        "",
        "This atlas groups restored conversations into stable themes so the corpus can keep feeding long-term notes instead of remaining a pile of transcripts.",
        "",
        "## Provider Mix",
        "",
    ]
    for provider, count in provider_counts.most_common():
        lines.append(f"- `{provider}`: {count}")
    lines.extend(["", "## Topic Buckets", ""])
    for bucket in TOPIC_BUCKETS:
        conversations = sorted(grouped.get(bucket["slug"], []), key=lambda item: item.visible_turns, reverse=True)
        if not conversations:
            continue
        lines.extend([f"## {bucket['label']}", "", "### Knowledge Surface", ""])
        for claim in bucket["knowledge_surface"]:
            lines.append(f"- {claim}")
        lines.extend(["", "### Sample Threads", ""])
        for conversation in conversations[:8]:
            lines.append(
                f"- [[{conversation.note_path.stem}|{conversation.title}]]"
                f" ({conversation.provider}, {conversation.visible_turns} turns)"
            )
        lines.extend(["", "### Suggested Landing Zones", ""])
        for target in bucket["targets"]:
            lines.append(f"- `{target}`")
        lines.append("")
    return "\n".join(lines)


def build_capability_library(items: list[ConversationRecord], corpus_name: str) -> str:
    grouped: dict[str, list[ConversationRecord]] = defaultdict(list)
    for item in items:
        for slug in item.primary_buckets:
            grouped[slug].append(item)
    provider_counts = summarize_provider_counts(items)
    frontmatter = yaml_frontmatter(
        {
            "note_type": "conversation-backup-capability-library",
            "generated_by": "import_chatgpt_backup_to_vault.py",
            "generated_at": current_display_timestamp(),
            "corpus_name": corpus_name,
            "conversation_count": len(items),
        }
    )
    lines = [
        frontmatter,
        "",
        f"# {corpus_name} Capability Library",
        "",
        "This page maps the restored corpus into reusable capability bands rather than treating every thread as an isolated record.",
        "",
        "## Provider Mix",
        "",
    ]
    for provider, count in provider_counts.most_common():
        lines.append(f"- `{provider}`: {count}")
    lines.extend(["", "## Capability Bands", ""])
    for bucket in TOPIC_BUCKETS:
        conversations = sorted(grouped.get(bucket["slug"], []), key=lambda item: item.visible_turns, reverse=True)
        if not conversations:
            continue
        lines.extend([f"## {bucket['label']}", "", bucket["capability"], "", "### Evidence Threads", ""])
        for conversation in conversations[:8]:
            lines.append(
                f"- [[{conversation.note_path.stem}|{conversation.title}]]"
                f" ({conversation.provider}, {conversation.visible_turns} turns)"
            )
        lines.extend(
            [
                "",
                "### Current Boundary",
                "",
                "- This capability band is corpus-derived and still needs higher-value conclusions to be distilled into concept, protocol, or experiment notes.",
                "",
            ]
        )
    return "\n".join(lines)


def build_standalone_response_review(
    dialogue_items: list[ConversationRecord],
    writing_output_items: list[ConversationRecord],
    vault_root: Path,
) -> str:
    grouped: dict[str, list[ConversationRecord]] = defaultdict(list)
    for item in dialogue_items:
        if item.source_kind == "markdown-response-export":
            grouped[item.archive_class or "unclassified"].append(item)

    lines = [
        "# Standalone Response Review",
        "",
        "This note separates one-sided markdown response exports into dialogue fragments versus research-draft style outputs.",
        "",
    ]
    labels = {
        "dialogue-fragment": "Dialogue Fragments",
        "unclassified": "Unclassified",
    }
    for key in ("dialogue-fragment", "unclassified"):
        bucket = sorted(grouped.get(key, []), key=record_sort_key)
        if not bucket:
            continue
        lines.extend([f"## {labels[key]}", "", f"- Count: {len(bucket)}", ""])
        for item in bucket:
            lines.append(
                f"- [[{wiki_target(item.note_path, vault_root)}|{item.title}]]"
                f" ({timestamp_to_date(item.created_at)}, {item.archive_class_reason or 'No reason captured.'})"
            )
        lines.append("")
    research_drafts = sorted(writing_output_items, key=record_sort_key)
    if research_drafts:
        lines.extend(
            [
                "## Research Drafts",
                "",
                f"- Count: {len(research_drafts)}",
                "- Routed to [[09_Conversations/Conversation Memo Archive/Writing Outputs/_Index|Writing Outputs]].",
                "",
            ]
        )
        for item in research_drafts:
            lines.append(
                f"- [[{wiki_target(item.note_path, vault_root)}|{item.title}]]"
                f" ({timestamp_to_date(item.created_at)}, {item.archive_class_reason or 'No reason captured.'})"
            )
        lines.append("")
    return "\n".join(lines)


def build_progress_note(
    items: list[ConversationRecord],
    layout: CorpusLayout,
    manifest_relpath: str,
    topic_note_rel: str,
    capability_note_rel: str,
) -> str:
    model_counts = Counter(item.model for item in items)
    provider_counts = summarize_provider_counts(items)
    bucket_counts = Counter()
    for item in items:
        bucket_counts.update(item.primary_buckets)
    top_threads = sorted(items, key=lambda item: item.visible_turns, reverse=True)[:8]
    lines = [
        f"# {datetime.now().strftime('%Y-%m-%d')} {layout.corpus_name} import and learning",
        "",
        f"- Corpus: {layout.corpus_name}",
        f"- Imported at: {current_display_timestamp()}",
        f"- Conversations restored: {len(items)}",
        f"- Manifest: `08_Attachments/{manifest_relpath}`",
        "",
        "## Provider Mix",
        "",
    ]
    for provider, count in provider_counts.most_common():
        lines.append(f"- `{provider}`: {count}")
    lines.extend(["", "## Model Mix", ""])
    for model, count in model_counts.most_common():
        lines.append(f"- `{model}`: {count}")
    lines.extend(["", "## Topic Mix", ""])
    for slug, count in bucket_counts.most_common():
        lines.append(f"- {bucket_by_slug(slug)['label']}: {count}")
    lines.extend(["", "## Largest Threads", ""])
    for item in top_threads:
        lines.append(f"- [[{item.note_path.stem}|{item.title}]] ({item.provider}, {item.visible_turns} turns)")
    lines.extend(
        [
            "",
            "## Derived Outputs",
            "",
            f"- [[{topic_note_rel}|Topic Atlas]]",
            f"- [[{capability_note_rel}|Capability Library]]",
            "",
            "## Interpretation",
            "",
            "- The imported history is now part of the long-term research memory, not just a portable backup file.",
            "- The next step is to keep sinking high-value threads into stable concept, protocol, and experiment notes.",
        ]
    )
    return "\n".join(lines)


def update_root_indexes(vault_root: Path, layout: CorpusLayout, progress_note_path: Path, topic_note_path: Path, capability_note_path: Path):
    safe_append_unique_lines(
        vault_root / "09_Conversations" / "_Index.md",
        [f"- [[09_Conversations/{layout.corpus_name}/_Index|{layout.corpus_name} Index]]"],
    )
    safe_append_unique_lines(
        vault_root / "03_Concepts" / "_Index.md",
        [f"- [[{wiki_target(topic_note_path, vault_root)}|{topic_note_path.stem.replace('-', ' ')}]]"],
    )
    safe_append_unique_lines(
        vault_root / "04_Progress" / "_Index.md",
        [f"- [[{wiki_target(progress_note_path, vault_root)}|{progress_note_path.stem.replace('-', ' ')}]]"],
    )
    safe_append_unique_lines(
        vault_root / "07_Profiles" / "_Index.md",
        [f"- [[{wiki_target(capability_note_path, vault_root)}|{capability_note_path.stem.replace('-', ' ')}]]"],
    )


def manifest_payload(items: list[ConversationRecord], backup_path: Path, manifest_relpath: str, layout: CorpusLayout) -> dict:
    model_counts = Counter(item.model for item in items)
    provider_counts = summarize_provider_counts(items)
    bucket_counts = Counter()
    for item in items:
        bucket_counts.update(item.primary_buckets)
    return {
        "generated_at": current_display_timestamp(),
        "backup_path": make_forward_slashes(backup_path),
        "manifest_path": f"08_Attachments/{manifest_relpath}",
        "corpus_name": layout.corpus_name,
        "conversation_count": len(items),
        "providers": dict(provider_counts),
        "models": dict(model_counts),
        "topic_buckets": {bucket_by_slug(slug)["label"]: count for slug, count in bucket_counts.most_common()},
        "conversations": [item.manifest_entry for item in items],
    }


def collect_backup_records(backup_path: Path) -> list[ConversationRecord]:
    records: list[ConversationRecord] = []
    if backup_path.is_file() and backup_path.suffix.lower() in {".json", ".txt", ".md"}:
        records.extend(collect_records_from_file(backup_path))
    elif backup_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(backup_path) as archive:
            for name in archive.namelist():
                lowered = name.lower()
                if lowered.endswith(".json"):
                    payload = load_json_bytes(archive.read(name))
                    if isinstance(payload, dict) and ("mapping" in payload or "current_node" in payload):
                        records.append(parse_chatgpt_json_conversation(backup_path, name, payload))
                elif lowered.endswith(".txt"):
                    raw_text = decode_text_bytes(archive.read(name))
                    if looks_like_memo_text_export(raw_text):
                        records.append(parse_memo_text_conversation(backup_path, name, raw_text))
                elif lowered.endswith(".md"):
                    raw_text = decode_text_bytes(archive.read(name))
                    records.extend(parse_markdown_file_conversation(backup_path, name, raw_text))
    elif backup_path.is_dir():
        for path in sorted(backup_path.rglob("*")):
            if not path.is_file():
                continue
            records.extend(collect_records_from_file(path, source_root=backup_path))
    else:
        raise FileNotFoundError(f"Backup path not found: {backup_path}")
    return records


def import_backup(backup_path: Path, vault_root: Path, config_path: Path, link_daily: bool, emit_summary: bool = True) -> dict:
    config = load_json(config_path)
    obsidian = config.get("obsidian", {})
    conversation_folder = obsidian.get("conversation_folder", "09_Conversations")
    daily_folder = obsidian.get("daily_folder", "01_Daily")
    attachment_folder = obsidian.get("attachment_folder", "08_Attachments")

    records = collect_backup_records(backup_path)
    if not records:
        raise SystemExit(f"No supported conversation payloads found in: {backup_path}")

    corpus_keys = {record.corpus_key for record in records}
    if len(corpus_keys) != 1:
        raise SystemExit(f"Mixed unsupported corpus types in one import: {sorted(corpus_keys)}")
    layout = layout_for_corpus(vault_root, next(iter(corpus_keys)))
    corpus_folder = vault_root / conversation_folder / layout.corpus_name
    backup_slug = sanitize_filename(backup_path.stem, max_length=48)
    summaries_root = corpus_folder / "Summaries"
    readable_transcripts_root = corpus_folder / "Readable Transcripts"
    writing_outputs_folder = corpus_folder / "Writing Outputs"
    writing_summaries_root = writing_outputs_folder / "Summaries"
    writing_transcripts_root = writing_outputs_folder / "Readable Drafts"
    manifest_dir = vault_root / attachment_folder / layout.transcript_group / backup_slug
    legacy_transcripts_root = manifest_dir / "transcripts"
    if legacy_transcripts_root.exists():
        shutil.rmtree(legacy_transcripts_root, ignore_errors=True)

    for record in records:
        score_buckets(record)
        month = monthly_folder_name(record)
        note_root = summaries_root
        transcript_root = readable_transcripts_root
        if layout.corpus_slug == "conversation-memo-backup" and is_writing_output(record):
            note_root = writing_summaries_root
            transcript_root = writing_transcripts_root
        note_path = note_root / month / conversation_filename(record)
        transcript_path = transcript_root / month / transcript_filename(record)
        record.note_path = note_path
        record.transcript_path = transcript_path
        write_text(transcript_path, build_transcript_note(record, vault_root, layout.corpus_name))
        write_text(note_path, build_conversation_note(record, vault_root, layout.corpus_name))
        if link_daily:
            ensure_daily_note(vault_root, daily_folder, record)
        record.manifest_entry = {
            "title": record.title,
            "conversation_id": record.conversation_id,
            "provider": record.provider,
            "source_kind": record.source_kind,
            "archive_class": record.archive_class,
            "archive_class_reason": record.archive_class_reason,
            "source_url": record.source_url,
            "created_at": timestamp_to_display(record.created_at),
            "updated_at": timestamp_to_display(record.updated_at),
            "model": record.model,
            "visible_turns": record.visible_turns,
            "topic_buckets": [bucket_by_slug(slug)["label"] for slug in record.primary_buckets],
            "note_path": make_forward_slashes(record.note_path.relative_to(vault_root)),
            "transcript_path": make_forward_slashes(record.transcript_path.relative_to(vault_root)),
            "source_entry": record.source_entry,
            "source_zip": record.source_zip,
        }

    manifest_path = manifest_dir / "manifest.json"
    manifest_relpath = make_forward_slashes(manifest_path.relative_to(vault_root / attachment_folder))
    write_text(
        manifest_path,
        json.dumps(
            manifest_payload(records, backup_path, manifest_relpath, layout),
            ensure_ascii=False,
            indent=2,
        ),
    )

    all_records = load_records_from_summary_tree(
        summaries_root=summaries_root,
        readable_transcripts_root=readable_transcripts_root,
        corpus_key=next(iter(corpus_keys)),
    )
    writing_output_records: list[ConversationRecord] = []
    if layout.corpus_slug == "conversation-memo-backup":
        writing_output_records = load_records_from_summary_tree(
            summaries_root=writing_summaries_root,
            readable_transcripts_root=writing_transcripts_root,
            corpus_key=next(iter(corpus_keys)),
        )
    months: dict[str, list[ConversationRecord]] = defaultdict(list)
    for record in all_records:
        months[monthly_folder_name(record)].append(record)

    month_index_paths: dict[str, Path] = {}
    for month, items in months.items():
        index_path = summaries_root / month / "_Index.md"
        month_index_paths[month] = index_path
        write_text(index_path, build_month_index(month, items, vault_root, layout.corpus_name))

    root_index_path = corpus_folder / "_Index.md"
    extra_view_paths: list[tuple[str, Path]] = []
    if layout.corpus_slug == "conversation-memo-backup":
        standalone_review_path = corpus_folder / "_Standalone-Response-Review.md"
        extra_view_paths.append(("Standalone Response Review", standalone_review_path))
        if writing_output_records:
            extra_view_paths.append(("Writing Outputs", writing_outputs_folder / "_Index.md"))
    write_text(
        root_index_path,
        build_root_conversation_index(
            layout,
            all_records,
            month_index_paths,
            manifest_relpath,
            vault_root,
            extra_view_paths=extra_view_paths,
        ),
    )

    if layout.corpus_slug == "conversation-memo-backup":
        writing_months: dict[str, list[ConversationRecord]] = defaultdict(list)
        for record in writing_output_records:
            writing_months[monthly_folder_name(record)].append(record)
        writing_month_index_paths: dict[str, Path] = {}
        for month, items in writing_months.items():
            index_path = writing_summaries_root / month / "_Index.md"
            writing_month_index_paths[month] = index_path
            write_text(
                index_path,
                build_month_index(
                    month,
                    items,
                    vault_root,
                    "Conversation Memo Writing Outputs",
                    folder_split="`Writing Outputs/Summaries/` and `Writing Outputs/Readable Drafts/`",
                ),
            )
        write_text(
            writing_outputs_folder / "_Index.md",
            build_writing_outputs_index(writing_output_records, writing_month_index_paths, manifest_relpath, vault_root),
        )

    capability_index_path = layout.capability_note_path.parent / "_Index.md"
    write_text(layout.topic_note_path, build_topic_atlas(all_records, layout.corpus_name))
    write_text(layout.capability_note_path, build_capability_library(all_records, layout.corpus_name))
    safe_append_unique_lines(capability_index_path, [f"- [[{layout.capability_note_path.stem}]]"])
    if layout.corpus_slug == "conversation-memo-backup":
        standalone_review_path = corpus_folder / "_Standalone-Response-Review.md"
        write_text(standalone_review_path, build_standalone_response_review(all_records, writing_output_records, vault_root))
    write_text(
        layout.progress_note_path,
        build_progress_note(
            records,
            layout,
            manifest_relpath,
            wiki_target(layout.topic_note_path, vault_root),
            wiki_target(layout.capability_note_path, vault_root),
        ),
    )
    update_root_indexes(vault_root, layout, layout.progress_note_path, layout.topic_note_path, layout.capability_note_path)

    result = {
        "backup": make_forward_slashes(backup_path),
        "vault_root": make_forward_slashes(vault_root),
        "corpus_name": layout.corpus_name,
        "conversation_count": len(records),
        "providers": dict(summarize_provider_counts(records)),
        "conversation_index": make_forward_slashes(root_index_path),
        "topic_atlas": make_forward_slashes(layout.topic_note_path),
        "capability_library": make_forward_slashes(layout.capability_note_path),
        "progress_note": make_forward_slashes(layout.progress_note_path),
    }
    if emit_summary:
        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
        )
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Import supported conversation backups into the OCT Obsidian vault without external API calls."
    )
    parser.add_argument("--config", required=True, help="Path to oct-research-assist config.json")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--backup", help="Path to one conversation backup zip, file, or extracted folder")
    source_group.add_argument("--scan-dir", help="Directory to scan for supported conversation backup files")
    parser.add_argument(
        "--vault-root",
        help="Optional override for vault root. Defaults to the repo-local workspace vault.",
    )
    parser.add_argument(
        "--prefer-config-vault-root",
        action="store_true",
        help="Use config.json vault_root instead of the repo-local workspace vault.",
    )
    parser.add_argument(
        "--no-daily-links",
        action="store_true",
        help="Skip linking restored conversation notes into daily notes.",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config = load_json(config_path)
    configured_vault = resolve_path(config.get("vault_root"), config_path.parent)
    workspace_vault = resolve_workspace_vault(config_path)
    if args.vault_root:
        vault_root = Path(args.vault_root).resolve()
    elif args.prefer_config_vault_root:
        if not configured_vault:
            raise SystemExit("vault_root is missing from config.json and --prefer-config-vault-root was requested.")
        vault_root = configured_vault
    else:
        vault_root = workspace_vault
    if args.scan_dir:
        scan_dir = Path(args.scan_dir).resolve()
        if not scan_dir.is_dir():
            raise SystemExit(f"Scan directory not found: {scan_dir}")
        sources = discover_conversation_sources(scan_dir)
        if not sources:
            raise SystemExit(f"No supported conversation backups found in: {scan_dir}")
        imported: list[dict] = []
        failures: list[dict] = []
        for source in sources:
            try:
                imported.append(
                    import_backup(
                        backup_path=source,
                        vault_root=vault_root,
                        config_path=config_path,
                        link_daily=not args.no_daily_links,
                        emit_summary=False,
                    )
                )
            except Exception as exc:  # pragma: no cover - batch import should continue on individual failures
                failures.append({"path": make_forward_slashes(source), "error": str(exc)})
        print(
            json.dumps(
                {
                    "scan_dir": make_forward_slashes(scan_dir),
                    "vault_root": make_forward_slashes(vault_root),
                    "discovered_sources": [make_forward_slashes(path) for path in sources],
                    "imported": imported,
                    "failures": failures,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        backup_path = Path(args.backup).resolve()
        import_backup(
            backup_path=backup_path,
            vault_root=vault_root,
            config_path=config_path,
            link_daily=not args.no_daily_links,
        )


if __name__ == "__main__":
    main()
