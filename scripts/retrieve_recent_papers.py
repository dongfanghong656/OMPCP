#!/usr/bin/env python
import argparse
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.error import URLError


OPENALEX_URL = "https://api.openalex.org/works"
ARXIV_URL = "http://export.arxiv.org/api/query"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_json(url: str):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str):
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def format_error(exc: Exception):
    reason = getattr(exc, "reason", None)
    if reason:
        return str(reason)
    return str(exc)


def query_openalex(keyword: str, max_results: int, mailto: str):
    params = {"search": keyword, "per-page": max_results}
    if mailto:
        params["mailto"] = mailto
    url = OPENALEX_URL + "?" + urllib.parse.urlencode(params)
    data = fetch_json(url)
    return [
        {
            "title": item.get("display_name", ""),
            "year": item.get("publication_year", ""),
            "url": item.get("primary_location", {}).get("landing_page_url", ""),
            "source": "openalex",
        }
        for item in data.get("results", [])
    ]


def query_arxiv(keyword: str, max_results: int):
    params = {
        "search_query": f'all:"{keyword}"',
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = ARXIV_URL + "?" + urllib.parse.urlencode(params)
    xml_text = fetch_text(url)
    root = ET.fromstring(xml_text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = []
    for entry in root.findall("atom:entry", ns):
        entries.append(
            {
                "title": (entry.findtext("atom:title", default="", namespaces=ns) or "").strip(),
                "year": (entry.findtext("atom:published", default="", namespaces=ns) or "")[:4],
                "url": entry.findtext("atom:id", default="", namespaces=ns) or "",
                "source": "arxiv",
            }
        )
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_json(Path(args.config))
    profile = load_json(Path(config["profile_path"]))
    vault_root = Path(config["vault_root"])
    retrieval_dir = vault_root / config["obsidian"]["retrieval_folder"]
    retrieval_dir.mkdir(parents=True, exist_ok=True)

    all_results = {}
    failures = []
    for interest in profile["interests"]:
        keyword = ", ".join(interest["keywords"])
        results = []
        if "openalex" in config["retrieval"]["sources"]:
            try:
                results.extend(
                    query_openalex(
                        keyword,
                        config["retrieval"]["max_results_per_interest"],
                        config["retrieval"]["openalex_mailto"],
                    )
                )
            except (URLError, TimeoutError, OSError) as exc:
                failures.append(
                    {
                        "interest": interest["name"],
                        "source": "openalex",
                        "error": format_error(exc),
                    }
                )
        if "arxiv" in config["retrieval"]["sources"]:
            try:
                results.extend(query_arxiv(keyword, min(5, config["retrieval"]["max_results_per_interest"])))
            except (URLError, TimeoutError, OSError, ET.ParseError) as exc:
                failures.append(
                    {
                        "interest": interest["name"],
                        "source": "arxiv",
                        "error": format_error(exc),
                    }
                )
        all_results[interest["name"]] = results

    json_path = retrieval_dir / f"{date.today().isoformat()}-retrieval.json"
    md_path = retrieval_dir / f"{date.today().isoformat()}-retrieval.md"
    payload = {
        "date": date.today().isoformat(),
        "results": all_results,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [f"# Retrieval Snapshot {date.today().isoformat()}", ""]
    if failures:
        lines.extend(["## Retrieval Failures", ""])
        for failure in failures:
            lines.append(f"- {failure['interest']} | {failure['source']} | {failure['error']}")
        lines.append("")
    for name, entries in all_results.items():
        lines.extend([f"## {name}", ""])
        if not entries:
            lines.append("- No results")
        else:
            for item in entries[:10]:
                lines.append(f"- {item['title']} | {item['year']} | {item['source']} | {item['url']}")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(str(md_path))


if __name__ == "__main__":
    main()
