#!/usr/bin/env python
from __future__ import annotations

import argparse
import ctypes
import email.policy
import hashlib
import io
import json
import os
import re
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from pypdf import PdfReader


CANDIDATE_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".html", ".htm"}
WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
NON_WORD_RE = re.compile(r"[^A-Za-z0-9._-]+")
HTML_PREFIX_MARKERS = ("<!doctype html", "<html", "<head", "<body")
FILE_ATTRIBUTE_ARCHIVE = 0x20
FILE_ATTRIBUTE_SPARSE_FILE = 0x200
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
FILE_ATTRIBUTE_PINNED = 0x80000
FILE_ATTRIBUTE_UNPINNED = 0x100000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000
ONEDRIVE_PLACEHOLDER_BITS = (
    FILE_ATTRIBUTE_OFFLINE
    | FILE_ATTRIBUTE_RECALL_ON_OPEN
    | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
    | FILE_ATTRIBUTE_UNPINNED
)
WINDOWS_ATTRIBUTE_NAMES = {
    FILE_ATTRIBUTE_ARCHIVE: "archive",
    FILE_ATTRIBUTE_SPARSE_FILE: "sparse",
    FILE_ATTRIBUTE_REPARSE_POINT: "reparse",
    FILE_ATTRIBUTE_OFFLINE: "offline",
    FILE_ATTRIBUTE_RECALL_ON_OPEN: "recall_on_open",
    FILE_ATTRIBUTE_PINNED: "pinned",
    FILE_ATTRIBUTE_UNPINNED: "unpinned",
    FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS: "recall_on_data_access",
}


class TextOnlyHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in {"br", "p", "div", "section", "article", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in {"p", "div", "section", "article", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if data:
            self.parts.append(data)

    def text(self) -> str:
        merged = "".join(self.parts)
        merged = re.sub(r"\r\n?", "\n", merged)
        merged = re.sub(r"\n{3,}", "\n\n", merged)
        merged = re.sub(r"[ \t]+\n", "\n", merged)
        return merged.strip()


@dataclass
class ExtractRecord:
    source_path: str
    relative_path: str
    extension: str
    size_bytes: int
    modified_at: str
    extractor: str
    status: str
    title: str
    char_count: int
    page_count: int
    extract_path: str
    message: str = ""


@dataclass
class CandidateFile:
    source_path: str
    relative_path: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan and extract a local literature corpus into workspace files.")
    parser.add_argument("--source-root", default="")
    parser.add_argument("--manifest-json", default="")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def normalize_whitespace(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def io_path(path: Path) -> str:
    raw = str(path)
    if os.name != "nt":
        return raw
    if raw.startswith("\\\\?\\"):
        return raw
    if raw.startswith("\\\\"):
        return "\\\\?\\UNC\\" + raw.lstrip("\\")
    return "\\\\?\\" + raw


def read_path_candidates(path: Path) -> list[str]:
    raw = str(path)
    long_path = io_path(path)
    if raw == long_path:
        return [raw]
    if len(raw) >= 240:
        return [long_path, raw]
    return [raw, long_path]


def sanitize_text(value: str) -> str:
    if not value:
        return ""
    value = value.replace("\x00", "")
    return value.encode("utf-8", errors="replace").decode("utf-8")


def read_binary_with_rescue(path: Path, size: int | None = None) -> bytes:
    last_error: Exception | None = None
    tried_hydration = False
    for _attempt in range(2):
        for candidate in read_path_candidates(path):
            try:
                with open(candidate, "rb") as handle:
                    return handle.read() if size is None else handle.read(size)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        if tried_hydration or not is_onedrive_placeholder(path):
            break
        detail = try_hydrate_onedrive_placeholder(path)
        tried_hydration = True
        if detail and "云操作无效" in detail:
            raise format_onedrive_placeholder_error(path, detail) from last_error
    if is_onedrive_placeholder(path):
        raise format_onedrive_placeholder_error(path, str(last_error) if last_error else None) from last_error
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Unable to read binary file: {path}")


def read_binary(path: Path) -> bytes:
    return read_binary_with_rescue(path)


def read_binary_prefix(path: Path, size: int = 512) -> bytes:
    return read_binary_with_rescue(path, size=size)


def get_windows_file_attributes(path: Path) -> int | None:
    if os.name != "nt":
        return None
    getter = getattr(ctypes.windll.kernel32, "GetFileAttributesW", None)
    if getter is None:
        return None
    getter.argtypes = [ctypes.c_wchar_p]
    getter.restype = ctypes.c_uint32
    attrs = getter(str(path))
    if attrs == 0xFFFFFFFF:
        return None
    return int(attrs)


def describe_windows_file_attributes(attrs: int | None) -> list[str]:
    if attrs is None:
        return []
    return [name for bit, name in WINDOWS_ATTRIBUTE_NAMES.items() if attrs & bit]


def is_onedrive_placeholder(path: Path) -> bool:
    attrs = get_windows_file_attributes(path)
    return bool(attrs is not None and attrs & ONEDRIVE_PLACEHOLDER_BITS)


def format_windows_error(code: int) -> str:
    try:
        return ctypes.FormatError(code).strip() or f"WinError {code}"
    except Exception:  # noqa: BLE001
        return f"WinError {code}"


def try_hydrate_onedrive_placeholder(path: Path) -> str | None:
    if os.name != "nt" or not is_onedrive_placeholder(path):
        return None

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    cldapi = ctypes.WinDLL("CldApi.dll", use_last_error=True)

    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    create_file.restype = ctypes.c_void_p

    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [ctypes.c_void_p]
    close_handle.restype = ctypes.c_int

    cf_hydrate = cldapi.CfHydratePlaceholder
    cf_hydrate.argtypes = [
        ctypes.c_void_p,
        ctypes.c_longlong,
        ctypes.c_longlong,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    cf_hydrate.restype = ctypes.c_long

    handle = create_file(
        str(path),
        0x80000000,
        0x1 | 0x2 | 0x4,
        None,
        3,
        0x80,
        None,
    )
    if handle in (None, ctypes.c_void_p(-1).value):
        winerr = ctypes.get_last_error()
        return f"hydrate-open-failed: {format_windows_error(winerr)}"

    try:
        hr = int(cf_hydrate(handle, 0, -1, 0, None))
    finally:
        close_handle(handle)

    if hr == 0:
        return None

    winerr = hr & 0xFFFF
    return f"hydrate-failed: {format_windows_error(winerr)}"


def format_onedrive_placeholder_error(path: Path, detail: str | None = None) -> RuntimeError:
    attrs = get_windows_file_attributes(path)
    attr_text = ",".join(describe_windows_file_attributes(attrs)) or "unknown"
    message = f"OneDrive placeholder unavailable [{attr_text}]"
    if detail:
        message += f": {detail}"
    return RuntimeError(message)


def safe_label(value: str) -> str:
    label = NON_WORD_RE.sub("_", value).strip("._-")
    return label[:80] or "item"


def stable_extract_folder(relative_path: str, index: int) -> str:
    digest = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:10]
    stem = safe_label(Path(relative_path).stem)
    return f"{index:03d}-{stem}-{digest}"


def best_effort_title(text: str, fallback: str) -> str:
    for raw_line in text.splitlines():
        line = normalize_whitespace(raw_line)
        if not line:
            continue
        if len(line) < 6:
            continue
        return line[:180]
    return fallback


def read_text_file(path: Path) -> tuple[str, str]:
    raw = read_binary(path)
    decoded, encoding = decode_text_bytes(raw)
    return decoded, encoding


def decode_text_bytes(payload: bytes) -> tuple[str, str]:
    encodings = ("utf-8-sig", "utf-8", "gb18030", "gbk", "utf-16", "latin-1")
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            return payload.decode(encoding), encoding
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(f"Unable to decode text bytes: {last_error}")


def looks_like_html_bytes(payload: bytes) -> bool:
    sample = payload[:512].decode("ascii", errors="ignore").lstrip().lower()
    return any(sample.startswith(marker) for marker in HTML_PREFIX_MARKERS)


def extract_pdf_text(path: Path) -> tuple[str, int]:
    reader = PdfReader(io.BytesIO(read_binary(path)), strict=False)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:  # noqa: BLE001
            pass
    chunks: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            page_text = (page.extract_text() or "").strip()
        except Exception as exc:  # noqa: BLE001
            page_text = f"[Page {index} extraction failed: {exc}]"
        chunks.append(f"## Page {index}\n\n{page_text}")
    return "\n\n".join(chunks).strip(), len(reader.pages)


def extract_html_from_binary(path: Path) -> tuple[str, str]:
    raw = read_binary(path)
    decoded, encoding = decode_text_bytes(raw)
    parser = TextOnlyHTMLParser()
    parser.feed(decoded)
    return parser.text(), encoding


def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(io.BytesIO(read_binary(path))) as archive:
        xml_bytes = archive.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        paragraphs: list[str] = []
        for paragraph in root.findall(".//w:p", WORD_NS):
            runs = []
            for node in paragraph.findall(".//w:t", WORD_NS):
                if node.text:
                    runs.append(node.text)
            text = "".join(runs).strip()
            if text:
                paragraphs.append(text)
        if paragraphs:
            return "\n\n".join(paragraphs).strip()

        for member in archive.namelist():
            if not member.lower().endswith((".mht", ".mhtml")):
                continue
            parsed = BytesParser(policy=email.policy.default).parsebytes(archive.read(member))
            for part in parsed.walk():
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                charset = part.get_content_charset() or "utf-8"
                content_type = part.get_content_type()
                text = payload.decode(charset, errors="replace")
                if content_type == "text/plain":
                    return text.strip()
                if content_type == "text/html":
                    parser = TextOnlyHTMLParser()
                    parser.feed(text)
                    html_text = parser.text()
                    if html_text:
                        return html_text
    return ""


def extract_html_text(path: Path) -> tuple[str, str]:
    raw, encoding = read_text_file(path)
    parser = TextOnlyHTMLParser()
    parser.feed(raw)
    return parser.text(), encoding


def read_existing_utf8(path: Path) -> str:
    with open(io_path(path), "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def write_utf8_text(path: Path, content: str) -> None:
    with open(io_path(path), "w", encoding="utf-8") as handle:
        handle.write(content)


def extract_source(path: Path) -> tuple[str, str, int]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        prefix = read_binary_prefix(path)
        if looks_like_html_bytes(prefix):
            text, encoding = extract_html_from_binary(path)
            return text, f"pdf-html:{encoding}", 0
        text, page_count = extract_pdf_text(path)
        return text, "pypdf", page_count
    if ext == ".docx":
        return extract_docx_text(path), "docx-xml", 0
    if ext in {".txt", ".md"}:
        text, encoding = read_text_file(path)
        return text.strip(), f"text:{encoding}", 0
    if ext in {".html", ".htm"}:
        text, encoding = extract_html_text(path)
        return text, f"html:{encoding}", 0
    raise RuntimeError(f"Unsupported extension: {ext}")


def build_extract_markdown(record: ExtractRecord, body: str) -> str:
    header = [
        "---",
        f'source_path: "{record.source_path.replace("\\\\", "/")}"',
        f'source_relative_path: "{record.relative_path}"',
        f'extension: "{record.extension}"',
        f'extractor: "{record.extractor}"',
        f'extracted_at: "{datetime.now().isoformat(timespec="seconds")}"',
        f"page_count: {record.page_count}",
        f"char_count: {record.char_count}",
        "---",
        "",
        f"# {record.title}",
        "",
    ]
    return "\n".join(header) + body.strip() + ("\n" if body.strip() else "")


def render_inventory_markdown(summary: dict[str, Any], records: list[ExtractRecord]) -> str:
    lines = [
        "# 本地文献候选清单与抽取结果",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- 候选文件总数：`{summary['candidate_total']}`",
        f"- 成功抽取：`{summary['extracted_total']}`",
        f"- 已跳过：`{summary['skipped_total']}`",
        f"- 失败：`{summary['failed_total']}`",
        "",
        "## 按扩展名统计",
        "",
    ]
    for extension, count in summary["by_extension"].items():
        lines.append(f"- {extension}: {count}")
    lines.extend(["", "## 文件明细", ""])
    for record in records:
        lines.append(
            f"- [{record.status}] {record.relative_path} | {record.extension} | chars={record.char_count} | pages={record.page_count}"
        )
        if record.extract_path:
            lines.append(f"  - extract: `{record.extract_path}`")
        if record.message:
            lines.append(f"  - note: {record.message}")
    lines.append("")
    return "\n".join(lines)


def load_manifest_candidates(path: Path) -> list[CandidateFile]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("Manifest must be a JSON array.")

    candidates: list[CandidateFile] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        source_path = str(item.get("source_path", "")).strip()
        if not source_path:
            continue
        relative_path = str(item.get("relative_path", "")).strip() or Path(source_path).name
        candidates.append(CandidateFile(source_path=source_path, relative_path=relative_path))
    return candidates


def load_root_candidates(source_root: Path) -> list[CandidateFile]:
    candidates: list[CandidateFile] = []
    for path in sorted(source_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in CANDIDATE_EXTENSIONS:
            continue
        candidates.append(
            CandidateFile(
                source_path=str(path),
                relative_path=path.relative_to(source_root).as_posix(),
            )
        )
    return candidates


def main() -> None:
    args = parse_args()
    if not args.source_root and not args.manifest_json:
        raise SystemExit("Either --source-root or --manifest-json is required.")

    source_root = Path(args.source_root) if args.source_root else None
    output_root = Path(args.output_root)
    extract_root = output_root / "extracts"
    extract_root.mkdir(parents=True, exist_ok=True)

    candidate_files = (
        load_manifest_candidates(Path(args.manifest_json))
        if args.manifest_json
        else load_root_candidates(source_root)
    )

    records: list[ExtractRecord] = []
    extension_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()

    for index, candidate in enumerate(candidate_files, start=1):
        path = Path(candidate.source_path)
        relative_path = candidate.relative_path
        extension = path.suffix.lower()
        extension_counter[extension] += 1
        folder_name = stable_extract_folder(relative_path, index)
        target_dir = extract_root / folder_name
        target_path = target_dir / "source-extract.md"

        if not path.exists():
            record = ExtractRecord(
                source_path=str(path),
                relative_path=relative_path,
                extension=extension,
                size_bytes=0,
                modified_at="",
                extractor="",
                status="failed",
                title=path.stem,
                char_count=0,
                page_count=0,
                extract_path=str(target_path),
                message="Source file is missing at extraction time.",
            )
            status_counter[record.status] += 1
            records.append(record)
            continue

        record = ExtractRecord(
            source_path=str(path),
            relative_path=relative_path,
            extension=extension,
            size_bytes=path.stat().st_size,
            modified_at=datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
            extractor="",
            status="pending",
            title=path.stem,
            char_count=0,
            page_count=0,
            extract_path=str(target_path),
        )

        try:
            if args.skip_existing and target_path.exists():
                existing_text = read_existing_utf8(target_path)
                record.status = "skipped-existing"
                record.extractor = "cached"
                record.char_count = len(existing_text)
                record.title = best_effort_title(existing_text, path.stem)
                status_counter[record.status] += 1
                records.append(record)
                continue

            body, extractor, page_count = extract_source(path)
            body = sanitize_text(body)
            record.extractor = extractor
            record.page_count = page_count
            record.char_count = len(body)
            record.title = best_effort_title(body, path.stem)
            target_dir.mkdir(parents=True, exist_ok=True)
            write_utf8_text(target_path, build_extract_markdown(record, body))
            record.status = "extracted"
            status_counter[record.status] += 1
            records.append(record)
        except Exception as exc:  # noqa: BLE001
            record.status = "failed"
            record.message = str(exc)
            status_counter[record.status] += 1
            records.append(record)

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_root": str(source_root) if source_root else "",
        "manifest_json": args.manifest_json,
        "output_root": str(output_root),
        "candidate_total": len(records),
        "extracted_total": status_counter.get("extracted", 0),
        "skipped_total": status_counter.get("skipped-existing", 0),
        "failed_total": status_counter.get("failed", 0),
        "by_extension": dict(sorted(extension_counter.items())),
        "by_status": dict(sorted(status_counter.items())),
    }

    payload = {
        "summary": summary,
        "records": [asdict(record) for record in records],
    }
    output_root.mkdir(parents=True, exist_ok=True)
    write_utf8_text(output_root / "inventory.json", json.dumps(payload, ensure_ascii=False, indent=2))
    write_utf8_text(output_root / "inventory.md", render_inventory_markdown(summary, records))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
