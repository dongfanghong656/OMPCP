#!/usr/bin/env python
from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path


HEADING_RE = re.compile(
    r"(?im)^(?:#{1,6}\s*(references|bibliography|参考文献)\s*|references\s*$|bibliography\s*$|参考文献\s*$)"
)
NUMERIC_CITATION_RE = re.compile(r"\[(\d+(?:\s*[-–,，]\s*\d+)*)\]")
REFERENCE_LINE_RE = re.compile(r"^\s*(?:\[(\d+)\]|(\d+)[\.\)])\s+")
PLACEHOLDER_PATTERNS = [
    re.compile(r"citation needed", re.IGNORECASE),
    re.compile(r"todo[: ]*cite", re.IGNORECASE),
    re.compile(r"待补文献"),
    re.compile(r"Error! Reference source not found\.", re.IGNORECASE),
    re.compile(r"\[\s*\]"),
    re.compile(r"\[REF\]", re.IGNORECASE),
]


def split_body_and_references(text: str) -> tuple[str, str]:
    match = HEADING_RE.search(text)
    if not match:
        return text, ""
    return text[: match.start()], text[match.end() :]


def expand_citation_group(group: str) -> list[int]:
    values: list[int] = []
    parts = re.split(r"\s*[,，]\s*", group.strip())
    for part in parts:
        if not part:
            continue
        if re.search(r"[-–]", part):
            start_text, end_text = re.split(r"\s*[-–]\s*", part, maxsplit=1)
            start = int(start_text)
            end = int(end_text)
            if end < start:
                start, end = end, start
            values.extend(range(start, end + 1))
        else:
            values.append(int(part))
    return values


def extract_citations(body: str) -> list[int]:
    citations: list[int] = []
    for match in NUMERIC_CITATION_RE.finditer(body):
        citations.extend(expand_citation_group(match.group(1)))
    return citations


def extract_reference_numbers(reference_text: str) -> list[int]:
    numbers: list[int] = []
    for line in reference_text.splitlines():
        match = REFERENCE_LINE_RE.match(line)
        if match:
            numbers.append(int(match.group(1) or match.group(2)))
    return numbers


def detect_placeholders(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in PLACEHOLDER_PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return hits


def first_appearance_order(values: list[int]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def summarize(path: Path) -> tuple[list[str], list[str], list[str]]:
    text = path.read_text(encoding="utf-8")
    body, references = split_body_and_references(text)
    cited_numbers = extract_citations(body)
    reference_numbers = extract_reference_numbers(references)

    info: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []

    info.append(f"Detected numeric citation mentions: {len(cited_numbers)}")
    info.append(f"Detected unique cited references: {len(set(cited_numbers))}")
    info.append(f"Detected numbered bibliography entries: {len(reference_numbers)}")

    placeholders = detect_placeholders(text)
    if placeholders:
        errors.append(
            "Unresolved citation placeholders found: " + ", ".join(placeholders)
        )

    if cited_numbers and not reference_numbers:
        errors.append(
            "Numeric in-text citations were found, but no numbered reference list was detected."
        )

    if reference_numbers:
        reference_counter = Counter(reference_numbers)
        duplicate_numbers = sorted(
            number for number, count in reference_counter.items() if count > 1
        )
        if duplicate_numbers:
            errors.append(
                "Duplicate bibliography numbers found: "
                + ", ".join(map(str, duplicate_numbers))
            )

        max_number = max(reference_numbers)
        missing_sequence = [
            number for number in range(1, max_number + 1) if number not in reference_counter
        ]
        if missing_sequence:
            warnings.append(
                "Reference list numbering is not contiguous: missing "
                + ", ".join(map(str, missing_sequence))
            )

    if cited_numbers and reference_numbers:
        cited_set = set(cited_numbers)
        reference_set = set(reference_numbers)

        missing_references = sorted(cited_set - reference_set)
        if missing_references:
            errors.append(
                "In-text citations missing from the bibliography: "
                + ", ".join(map(str, missing_references))
            )

        uncited_entries = sorted(reference_set - cited_set)
        if uncited_entries:
            warnings.append(
                "Bibliography entries not cited in the text: "
                + ", ".join(map(str, uncited_entries))
            )

        appearance = first_appearance_order(cited_numbers)
        if appearance != sorted(appearance):
            warnings.append(
                "First appearance order is not ascending. Numeric styles usually expect first-use order."
            )

    if not cited_numbers and not reference_numbers:
        warnings.append(
            "No numeric citation pattern was detected. This script is most useful for numeric styles."
        )

    return info, warnings, errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit numeric in-text citations, numbered reference lists, and unresolved placeholders."
    )
    parser.add_argument("path", help="Path to the draft file to audit.")
    args = parser.parse_args()

    target = Path(args.path)
    info, warnings, errors = summarize(target)

    print(f"Document: {target}")
    print("")
    print("Summary")
    for item in info:
        print(f"- {item}")

    print("")
    print("Warnings")
    if warnings:
        for item in warnings:
            print(f"- {item}")
    else:
        print("- None")

    print("")
    print("Errors")
    if errors:
        for item in errors:
            print(f"- {item}")
    else:
        print("- None")


if __name__ == "__main__":
    main()
