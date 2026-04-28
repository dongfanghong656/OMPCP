#!/usr/bin/env python
import hashlib
import re


INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*]+')
WHITESPACE_RE = re.compile(r"\s+")
NON_SLUG_CHARS_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")
TITLE_SEPARATOR_RE = re.compile(r"[\[\]():;,_]+")


def _short_hash(value: str, length: int = 8) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def _truncate_with_hash(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    suffix = _short_hash(value)
    prefix_length = max(8, max_length - len(suffix) - 1)
    prefix = value[:prefix_length].rstrip(" .-_")
    if not prefix:
        return suffix[:max_length]
    return f"{prefix}-{suffix}"[:max_length].rstrip(" .-_")


def safe_filename_component(value: str, max_length: int = 80, fallback: str = "item") -> str:
    cleaned = INVALID_FILENAME_CHARS_RE.sub("", str(value))
    cleaned = WHITESPACE_RE.sub(" ", cleaned).strip().rstrip(".")
    if not cleaned:
        seed = str(value).strip() or fallback
        cleaned = f"{fallback}-{_short_hash(seed)}"
    return _truncate_with_hash(cleaned, max_length)


def safe_slug(value: str, max_length: int = 64, fallback: str = "item") -> str:
    source = str(value)
    cleaned = NON_SLUG_CHARS_RE.sub("-", source.lower()).strip("-")
    if not cleaned:
        seed = source.strip() or fallback
        cleaned = f"{fallback}-{_short_hash(seed)}"
    return _truncate_with_hash(cleaned, max_length).strip("-") or fallback


def hashed_label(value: str, prefix: str = "item") -> str:
    seed = str(value).strip() or prefix
    return f"{prefix}-{_short_hash(seed)}"


def paper_seed(title: str, year: str = "") -> str:
    parts = [str(year).strip(), str(title).strip()]
    return " - ".join(part for part in parts if part)


def paper_slug(title: str, year: str = "", max_length: int = 32, fallback: str = "paper") -> str:
    return safe_slug(paper_seed(title, year), max_length=max_length, fallback=fallback)


def paper_short_title(
    title: str,
    *,
    max_words: int = 6,
    max_length: int = 48,
    fallback: str = "paper",
) -> str:
    cleaned = TITLE_SEPARATOR_RE.sub(" ", str(title))
    cleaned = WHITESPACE_RE.sub(" ", cleaned).strip()
    words = cleaned.split()
    if not words:
        return safe_filename_component(fallback, max_length=max_length, fallback=fallback)
    return safe_filename_component(" ".join(words[:max_words]), max_length=max_length, fallback=fallback)


def paper_attachment_slug(
    title: str,
    *,
    year: str = "",
    author_label: str = "",
    max_length: int = 56,
    fallback: str = "paper",
) -> str:
    readable = " ".join(
        part
        for part in (
            str(year).strip(),
            str(author_label).strip(),
            paper_short_title(title, max_words=6, max_length=36, fallback=fallback),
        )
        if part
    )
    return safe_slug(readable, max_length=max_length, fallback=fallback)


def paper_artifact_label(title: str, year: str = "", prefix: str = "paper") -> str:
    return hashed_label(paper_seed(title, year), prefix=prefix)
