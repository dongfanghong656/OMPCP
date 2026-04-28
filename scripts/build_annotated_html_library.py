from __future__ import annotations

import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = WORKSPACE_ROOT / "reports" / "literature-html-pipeline"
REPORTS_BASE = WORKSPACE_ROOT / "reports"
ACTIVE_CORPORA = [
    ("local-literature-corpus", REPORTS_BASE / "local-literature-corpus" / "inventory.json"),
    ("additional-literature-corpus", REPORTS_BASE / "additional-literature-corpus" / "inventory.json"),
    ("additional-literature-corpus-fixes", REPORTS_BASE / "additional-literature-corpus-fixes" / "inventory.json"),
    ("knowledge-base-literature", REPORTS_BASE / "knowledge-base-literature" / "inventory.json"),
    ("full-local-literature-corpus", REPORTS_BASE / "full-local-literature-corpus" / "inventory.json"),
    (
        "archive-literature-corpus-sciencedirect-20250320",
        REPORTS_BASE / "archive-literature-corpus" / "sciencedirect-20250320" / "extracted" / "inventory.json",
    ),
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_year_sort(value: str) -> tuple[int, str]:
    try:
        return int(value), value
    except Exception:
        return 9999, value or ""


def rel_link(path: Path) -> str:
    return path.relative_to(REPORT_ROOT).as_posix()


def summarize_corpus(name: str, inventory_path: Path) -> dict[str, Any]:
    payload = load_json(inventory_path)
    records = payload.get("records", []) if isinstance(payload, dict) else payload
    statuses = Counter(str(record.get("status", "")) for record in records)
    usable_total = sum(count for status, count in statuses.items() if status in {"extracted", "skipped-existing"})
    failed_records = [record for record in records if str(record.get("status", "")).startswith("failed")]
    reason_counts = Counter((record.get("message") or "未注明原因").strip() for record in failed_records)
    return {
        "name": name,
        "total_records": len(records),
        "usable_total": usable_total,
        "failed_total": len(failed_records),
        "status_counts": dict(statuses),
        "failure_reason_counts": dict(reason_counts),
        "top_failure_reasons": reason_counts.most_common(4),
    }


def load_direct_html_records() -> list[dict[str, Any]]:
    batch_path = REPORT_ROOT / "generated" / "batch_inventory.json"
    payload = load_json(batch_path)
    records: list[dict[str, Any]] = []
    for record in payload.get("records", []):
        output_html = Path(record["output_html"])
        if not output_html.exists():
            continue
        records.append(
            {
                "year": str(record.get("year") or ""),
                "title": str(record.get("title") or output_html.stem),
                "title_original": str(record.get("title") or output_html.stem),
                "kind": "直连译注",
                "html_path": str(output_html),
                "html_link": rel_link(output_html),
                "paper_note_rel_path": str(record.get("paper_note_rel_path") or ""),
                "translated_note_rel_path": str(record.get("translated_note_rel_path") or ""),
            }
        )
    return sorted(records, key=lambda item: (as_year_sort(item["year"]), item["title"]))


def load_local_html_records() -> list[dict[str, Any]]:
    local_root = REPORT_ROOT / "local-translated-papers"
    output_root = REPORT_ROOT / "generated-local"
    records: list[dict[str, Any]] = []
    for folder in sorted(local_root.iterdir()):
        if not folder.is_dir():
            continue
        metadata_path = folder / "local-metadata.json"
        if not metadata_path.exists():
            continue
        metadata = load_json(metadata_path)
        html_path = output_root / f"{folder.name}-annotated.html"
        if not html_path.exists():
            continue
        records.append(
            {
                "year": str(metadata.get("year") or ""),
                "title": str(metadata.get("paper_title") or folder.name),
                "title_original": str(metadata.get("paper_title_original") or metadata.get("paper_title") or folder.name),
                "kind": "本地译注副本",
                "html_path": str(html_path),
                "html_link": rel_link(html_path),
                "paper_note_path": str(metadata.get("paper_note_path") or ""),
                "translated_note_path": str(folder / "translated.md"),
                "normalized_extract_path": str(folder / "normalized-extract.md"),
            }
        )
    return sorted(records, key=lambda item: (as_year_sort(item["year"]), item["title"]))


def load_crosswalk_summary() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = load_json(REPORT_ROOT / "local_literature_crosswalk.json")
    return payload.get("summary", {}), payload.get("records", [])


def load_effective_failure_summary() -> dict[str, Any]:
    payload = load_json(REPORTS_BASE / "failure-triage" / "effective-failure-overlap.json")
    return payload.get("summary", {})


def build_stats(direct_records: list[dict[str, Any]], local_records: list[dict[str, Any]]) -> dict[str, Any]:
    crosswalk_summary, crosswalk_records = load_crosswalk_summary()
    effective_failure_summary = load_effective_failure_summary()
    covered_note_paths = {
        str(record.get("paper_note_path") or "")
        for record in local_records
        if record.get("paper_note_path")
    }
    pending_local_translation = [
        record
        for record in crosswalk_records
        if record.get("local_match")
        and not record.get("translated_note_path")
        and str(record.get("paper_note_path") or "") not in covered_note_paths
    ]
    corpus_summaries = [summarize_corpus(name, inventory_path) for name, inventory_path in ACTIVE_CORPORA]
    usable_extract_total = sum(item["usable_total"] for item in corpus_summaries)
    failure_total_raw = sum(item["failed_total"] for item in corpus_summaries)
    summary_map = {item["name"]: item for item in corpus_summaries}
    missing_source_recovered = min(
        int(summary_map["additional-literature-corpus"]["failure_reason_counts"].get("Source file is missing at extraction time.", 0)),
        int(summary_map["additional-literature-corpus-fixes"]["usable_total"]),
    )
    failure_total_effective = int(effective_failure_summary.get("failed_without_known_duplicate_total") or (failure_total_raw - missing_source_recovered))
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "paper_note_total": int(crosswalk_summary.get("paper_note_total") or 0),
        "with_translation_total": int(crosswalk_summary.get("with_translation_total") or 0),
        "with_note_extract_total": int(crosswalk_summary.get("with_note_extract_total") or 0),
        "with_local_match_total": int(crosswalk_summary.get("with_local_match_total") or 0),
        "direct_html_total": len(direct_records),
        "local_html_total": len(local_records),
        "total_html": len(direct_records) + len(local_records),
        "pending_local_translation_total": len(pending_local_translation),
        "usable_extract_total": usable_extract_total,
        "failed_extract_total_raw": int(effective_failure_summary.get("failed_total") or failure_total_raw),
        "failed_extract_total_effective": failure_total_effective,
        "recovered_missing_source_total": missing_source_recovered,
        "corpus_summaries": corpus_summaries,
    }


def render_stat_card(label: str, value: Any, hint: str) -> str:
    return (
        '<div class="stat-card">'
        f'<div class="stat-value">{html.escape(str(value))}</div>'
        f'<div class="stat-label">{html.escape(label)}</div>'
        f'<div class="stat-hint">{html.escape(hint)}</div>'
        "</div>"
    )


def render_entry_card(record: dict[str, Any]) -> str:
    meta_parts = [part for part in [record.get("year"), record.get("kind")] if part]
    meta = " · ".join(str(part) for part in meta_parts)
    auxiliary = []
    if record.get("paper_note_rel_path"):
        auxiliary.append(f"Paper Note: {record['paper_note_rel_path']}")
    elif record.get("paper_note_path"):
        auxiliary.append(f"Paper Note: {record['paper_note_path']}")
    if record.get("translated_note_rel_path"):
        auxiliary.append(f"译注来源: {record['translated_note_rel_path']}")
    elif record.get("translated_note_path"):
        auxiliary.append(f"本地译注副本: {record['translated_note_path']}")
    aux_html = "".join(f'<div class="entry-aux">{html.escape(line)}</div>' for line in auxiliary)
    return (
        '<article class="entry-card">'
        f'<div class="entry-badge">{html.escape(str(record["kind"]))}</div>'
        f'<h3>{html.escape(str(record["title"]))}</h3>'
        f'<div class="entry-meta">{html.escape(meta)}</div>'
        f'<div class="entry-original">{html.escape(str(record.get("title_original") or ""))}</div>'
        f"{aux_html}"
        f'<a class="entry-link" href="{html.escape(str(record["html_link"]))}">打开双栏批注 HTML</a>'
        "</article>"
    )


def render_corpus_card(summary: dict[str, Any]) -> str:
    reasons = summary.get("top_failure_reasons") or []
    reason_html = "".join(
        f'<li><span>{html.escape(reason)}</span><strong>{count}</strong></li>'
        for reason, count in reasons
    )
    if not reason_html:
        reason_html = "<li><span>当前无失败项</span><strong>0</strong></li>"
    return (
        '<article class="corpus-card">'
        f'<h3>{html.escape(summary["name"])}</h3>'
        '<div class="corpus-grid">'
        f'<div><span>可用抽取</span><strong>{summary["usable_total"]}</strong></div>'
        f'<div><span>失败项</span><strong>{summary["failed_total"]}</strong></div>'
        f'<div><span>总记录</span><strong>{summary["total_records"]}</strong></div>'
        "</div>"
        '<div class="corpus-reasons-title">主要失败原因</div>'
        f'<ul class="corpus-reasons">{reason_html}</ul>'
        "</article>"
    )


def build_html(stats: dict[str, Any], direct_records: list[dict[str, Any]], local_records: list[dict[str, Any]]) -> str:
    stat_cards = "".join(
        [
            render_stat_card("已抽取正文", stats["usable_extract_total"], "六路活动语料合并后的可用抽取总量"),
            render_stat_card(
                "已生成 HTML",
                stats["total_html"],
                f"直连译注 {len(direct_records)} + 本地译注副本 {len(local_records)}",
            ),
            render_stat_card("已匹配到本地语料", stats["with_local_match_total"], "已有 paper note 且已对上本地全文抽取"),
            render_stat_card("待补本地译注", stats["pending_local_translation_total"], "当前已有 paper note 的 extract-backed 队列"),
        ]
    )
    direct_cards = "".join(render_entry_card(record) for record in direct_records)
    local_cards = "".join(render_entry_card(record) for record in local_records)
    corpus_cards = "".join(render_corpus_card(summary) for summary in stats["corpus_summaries"])
    generated_at = html.escape(stats["generated_at"])
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>本地文献双栏批注总览</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Lora:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --navy: #0f2747;
      --navy-soft: #1c3a63;
      --cream: #f6f0e5;
      --paper: #fffdf8;
      --ink: #1f2430;
      --muted: #5e6b7a;
      --border: #dccfb9;
      --accent: #ba8c4a;
      --accent-soft: #efe0c7;
      --green: #2d6a4f;
      --red: #8d3b3b;
      --shadow: 0 18px 40px rgba(14, 28, 51, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top, #fdf6eb 0%, var(--cream) 48%, #efe6d4 100%);
      color: var(--ink);
      font-family: "IBM Plex Sans", sans-serif;
      line-height: 1.6;
    }}
    .nav {{
      position: sticky;
      top: 0;
      z-index: 20;
      background: rgba(15, 39, 71, 0.96);
      color: #f8f3ea;
      backdrop-filter: blur(10px);
      box-shadow: 0 10px 30px rgba(9, 20, 38, 0.22);
    }}
    .nav-inner {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 18px 24px;
      display: flex;
      gap: 18px;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
    }}
    .brand h1 {{
      margin: 0;
      font-size: 1.18rem;
      letter-spacing: 0.01em;
    }}
    .brand p {{
      margin: 4px 0 0;
      color: #c8d5e6;
      font-size: 0.92rem;
    }}
    .nav-links {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .nav-links a {{
      color: #f8f3ea;
      text-decoration: none;
      padding: 8px 12px;
      border: 1px solid rgba(248, 243, 234, 0.18);
      border-radius: 999px;
      font-size: 0.92rem;
    }}
    .nav-links a:hover {{ background: rgba(255, 255, 255, 0.08); }}
    .page {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 28px 24px 64px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(255,255,255,0.88), rgba(255,248,236,0.94));
      border: 1px solid var(--border);
      border-radius: 28px;
      padding: 28px;
      box-shadow: var(--shadow);
    }}
    .hero h2 {{
      margin: 0 0 10px;
      font-size: 2rem;
      color: var(--navy);
    }}
    .hero p {{
      margin: 0;
      max-width: 900px;
      color: var(--muted);
      font-size: 1rem;
    }}
    .stats {{
      margin-top: 22px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
    }}
    .stat-card {{
      background: var(--paper);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 20px;
      box-shadow: var(--shadow);
    }}
    .stat-value {{
      font-size: 2rem;
      line-height: 1;
      color: var(--navy);
      font-weight: 700;
    }}
    .stat-label {{
      margin-top: 10px;
      font-weight: 600;
    }}
    .stat-hint {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .section {{
      margin-top: 28px;
      background: rgba(255, 253, 248, 0.76);
      border: 1px solid rgba(220, 207, 185, 0.8);
      border-radius: 26px;
      padding: 24px;
      box-shadow: var(--shadow);
    }}
    .section h2 {{
      margin: 0;
      color: var(--navy);
      font-size: 1.45rem;
    }}
    .section p {{
      margin: 10px 0 0;
      color: var(--muted);
    }}
    .entry-grid, .corpus-layout {{
      margin-top: 18px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }}
    .entry-card, .corpus-card {{
      background: var(--paper);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 18px 18px 20px;
      box-shadow: var(--shadow);
    }}
    .entry-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: #7a4d14;
      font-size: 0.84rem;
      font-weight: 600;
    }}
    .entry-card h3 {{
      margin: 14px 0 8px;
      font-family: "Lora", serif;
      font-size: 1.18rem;
      line-height: 1.45;
    }}
    .entry-meta {{
      color: var(--navy-soft);
      font-weight: 600;
      font-size: 0.92rem;
    }}
    .entry-original {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.94rem;
    }}
    .entry-aux {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.84rem;
      word-break: break-all;
    }}
    .entry-link {{
      display: inline-block;
      margin-top: 16px;
      padding: 10px 14px;
      background: var(--navy);
      color: #fff8ef;
      text-decoration: none;
      border-radius: 12px;
      font-weight: 600;
    }}
    .entry-link:hover {{ background: var(--navy-soft); }}
    .corpus-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 14px;
    }}
    .corpus-grid div {{
      background: #fbf6ee;
      border-radius: 14px;
      padding: 12px;
      border: 1px solid #eadfcf;
    }}
    .corpus-grid span {{
      display: block;
      color: var(--muted);
      font-size: 0.84rem;
    }}
    .corpus-grid strong {{
      display: block;
      margin-top: 4px;
      font-size: 1.1rem;
      color: var(--navy);
    }}
    .corpus-reasons-title {{
      margin-top: 14px;
      font-weight: 600;
      color: var(--navy-soft);
    }}
    .corpus-reasons {{
      list-style: none;
      padding: 0;
      margin: 10px 0 0;
    }}
    .corpus-reasons li {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 8px 0;
      border-top: 1px dashed #e8dbc7;
      font-size: 0.9rem;
    }}
    .corpus-reasons li:first-child {{ border-top: 0; }}
    .footer {{
      margin-top: 26px;
      color: var(--muted);
      text-align: center;
      font-size: 0.9rem;
    }}
    .good {{ color: var(--green); font-weight: 700; }}
    .warn {{ color: var(--red); font-weight: 700; }}
    @media (max-width: 720px) {{
      .page {{ padding: 18px 14px 40px; }}
      .hero, .section {{ padding: 18px; }}
      .hero h2 {{ font-size: 1.58rem; }}
      .corpus-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header class="nav">
    <div class="nav-inner">
      <div class="brand">
        <h1>本地文献双栏批注总览</h1>
        <p>OCT Research System · 已把现有可读成品汇成统一入口</p>
      </div>
      <nav class="nav-links">
        <a href="#overview">概览</a>
        <a href="#direct">直连译注</a>
        <a href="#local">本地副本</a>
        <a href="#corpus">语料健康</a>
      </nav>
    </div>
  </header>
  <main class="page">
    <section class="hero" id="overview">
      <h2>当前可直接阅读的双栏批注 HTML 已累计到 {stats["total_html"]} 份</h2>
      <p>
        这份总览页把现阶段所有双栏批注 HTML 汇成一个可持续续跑的入口。当前已有 paper note 且已抽取正文的队列已经清空，
        因而后续重点会逐步转向“尚无 paper note 的高价值文献直连链路”和少量仍受 OneDrive / 文件损坏限制的失败抽取项。
      </p>
      <div class="stats">{stat_cards}</div>
    </section>

    <section class="section" id="direct">
      <h2>直连译注 HTML · {len(direct_records)} 份</h2>
      <p>这部分直接使用 vault 中已有中文译注页生成，适合优先阅读你已经建立长期笔记链路的论文。</p>
      <div class="entry-grid">{direct_cards}</div>
    </section>

    <section class="section" id="local">
      <h2>本地译注副本 HTML · {len(local_records)} 份</h2>
      <p>这部分来自工作区内的本地译注副本链路，用来绕开 OneDrive 只读限制，并继续吸收“未入现有 note 链路”的高价值论文。</p>
      <div class="entry-grid">{local_cards}</div>
    </section>

    <section class="section" id="corpus">
      <h2>语料健康检查</h2>
      <p>
        六路活动语料当前合计 <span class="good">{stats["usable_extract_total"]}</span> 份可用抽取，
        当前仍未解决的失败项为 <span class="warn">{stats["failed_extract_total_effective"]}</span> 个。
        其中另有 <span class="good">{stats["recovered_missing_source_total"]}</span> 个“原路径失效”条目已经通过 fixes 批次救回，
        剩余问题主要集中在 OneDrive 长路径占位文件、锁文件、加密教材 PDF 与损坏缓存文件。
      </p>
      <div class="corpus-layout">{corpus_cards}</div>
    </section>

    <div class="footer">
      最近构建时间：{generated_at}
    </div>
  </main>
</body>
</html>
"""


def main() -> None:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    direct_records = load_direct_html_records()
    local_records = load_local_html_records()
    stats = build_stats(direct_records, local_records)
    payload = {
        "summary": stats,
        "direct_records": direct_records,
        "local_records": local_records,
    }
    (REPORT_ROOT / "annotated_html_library.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (REPORT_ROOT / "annotated_html_library.html").write_text(
        build_html(stats, direct_records, local_records),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "built",
                "output_html": str(REPORT_ROOT / "annotated_html_library.html"),
                "output_json": str(REPORT_ROOT / "annotated_html_library.json"),
                "total_html": stats["total_html"],
                "pending_local_translation_total": stats["pending_local_translation_total"],
                "failed_extract_total_effective": stats["failed_extract_total_effective"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
