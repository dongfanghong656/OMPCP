#!/usr/bin/env python
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from research_question_flow import load_json, to_portable_path, write_json, write_text


DEFAULT_REPORT_FOLDER_NAME = "results-analysis"
RANKING_SUMMARY_NAME = "ranking_summary.json"
UNIFIED_RANKING_NAME = "unified_ranking.csv"
THEORY_SUMMARY_NAME = "theory_summary.csv"
SYNTHETIC_SCENE_NAME = "synthetic_scene_rmse.csv"


def normalize_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_csv_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def infer_run_title(experiment_dir: Path, explicit_title: str | None):
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()
    return experiment_dir.name


def create_run_dir(config: dict, explicit_dir: str | None, title: str):
    if explicit_dir:
        run_dir = Path(explicit_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    output_root = Path(config["output_root"])
    run_dir = output_root / DEFAULT_REPORT_FOLDER_NAME / f"{datetime.now().strftime('%Y-%m-%d')}-{title}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def find_default_artifacts(experiment_dir: Path):
    return {
        "ranking_summary": experiment_dir / RANKING_SUMMARY_NAME,
        "unified_ranking": experiment_dir / UNIFIED_RANKING_NAME,
        "theory_summary": experiment_dir / THEORY_SUMMARY_NAME,
        "synthetic_scene_rmse": experiment_dir / SYNTHETIC_SCENE_NAME,
    }


def extract_top_windows(ranking_summary_path: Path):
    if not ranking_summary_path.exists():
        return []
    payload = load_json(ranking_summary_path)
    return payload.get("top_windows", [])


def extract_unified_ranking_summary(path: Path):
    if not path.exists():
        return {}
    rows = load_csv_rows(path)
    if not rows:
        return {}

    best = rows[0]
    worst = rows[-1]
    return {
        "row_count": len(rows),
        "best_name": best.get("Name", ""),
        "best_unified_score": normalize_number(best.get("UnifiedScore")),
        "best_score_theory": normalize_number(best.get("ScoreTheory")),
        "best_score_paper_like": normalize_number(best.get("ScorePaperLike")),
        "best_score_scenes": normalize_number(best.get("ScoreScenes")),
        "worst_name": worst.get("Name", ""),
        "worst_unified_score": normalize_number(worst.get("UnifiedScore")),
    }


def extract_theory_summary(path: Path):
    if not path.exists():
        return {}
    rows = load_csv_rows(path)
    if not rows:
        return {}

    min_width = None
    max_sharpness = None
    min_width_name = ""
    max_sharpness_name = ""
    for row in rows:
        width = normalize_number(row.get("MeanMainlobeWidth3dB"))
        sharpness = normalize_number(row.get("MeanSharpness"))
        if width is not None and (min_width is None or width < min_width):
            min_width = width
            min_width_name = row.get("Name", "")
        if sharpness is not None and (max_sharpness is None or sharpness > max_sharpness):
            max_sharpness = sharpness
            max_sharpness_name = row.get("Name", "")

    return {
        "row_count": len(rows),
        "narrowest_mainlobe_name": min_width_name,
        "narrowest_mainlobe_width_3db": min_width,
        "highest_sharpness_name": max_sharpness_name,
        "highest_mean_sharpness": max_sharpness,
    }


def extract_scene_summary(path: Path):
    if not path.exists():
        return {}
    rows = load_csv_rows(path)
    if not rows:
        return {}

    best_rmse = None
    best_name = ""
    scenario_counts = {}
    for row in rows:
        rmse = normalize_number(row.get("scene_rmse") or row.get("rmse") or row.get("SceneRmse"))
        scenario = row.get("scenario", "") or row.get("Scene", "")
        if scenario:
            scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1
        if rmse is not None and (best_rmse is None or rmse < best_rmse):
            best_rmse = rmse
            best_name = row.get("Name", "") or row.get("window", "")

    return {
        "row_count": len(rows),
        "scenario_counts": scenario_counts,
        "best_scene_rmse_name": best_name,
        "best_scene_rmse": best_rmse,
    }


def build_analysis_payload(title: str, experiment_dir: Path, artifact_paths: dict):
    top_windows = extract_top_windows(artifact_paths["ranking_summary"])
    unified = extract_unified_ranking_summary(artifact_paths["unified_ranking"])
    theory = extract_theory_summary(artifact_paths["theory_summary"])
    scene = extract_scene_summary(artifact_paths["synthetic_scene_rmse"])

    findings = []
    if top_windows:
        leader = top_windows[0]
        findings.append(
            {
                "type": "ranking_leader",
                "claim": f"{leader.get('Name', 'Unknown')} leads the current ranking.",
                "evidence": f"UnifiedScore={leader.get('UnifiedScore')}, ScoreTheory={leader.get('ScoreTheory')}, ScorePaperLike={leader.get('ScorePaperLike')}, ScoreScenes={leader.get('ScoreScenes')}",
            }
        )
    if unified:
        findings.append(
            {
                "type": "ranking_span",
                "claim": "The unified ranking separates best and worst candidates clearly enough to guide follow-up choices.",
                "evidence": f"Best={unified.get('best_name')} ({unified.get('best_unified_score')}), Worst={unified.get('worst_name')} ({unified.get('worst_unified_score')})",
            }
        )
    if theory:
        findings.append(
            {
                "type": "theory_tradeoff",
                "claim": "Theoretical width and sharpness are not necessarily optimized by the same window.",
                "evidence": f"Narrowest mainlobe={theory.get('narrowest_mainlobe_name')} ({theory.get('narrowest_mainlobe_width_3db')}), Highest sharpness={theory.get('highest_sharpness_name')} ({theory.get('highest_mean_sharpness')})",
            }
        )
    if scene:
        findings.append(
            {
                "type": "scene_behavior",
                "claim": "Scene-level behavior should still be treated as a separate validation layer rather than inferred from theory alone.",
                "evidence": f"Best scene RMSE={scene.get('best_scene_rmse_name')} ({scene.get('best_scene_rmse')}), scenarios={scene.get('scenario_counts')}",
            }
        )

    return {
        "title": title,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "experiment_dir": to_portable_path(experiment_dir),
        "artifacts": {key: to_portable_path(value) for key, value in artifact_paths.items() if value.exists()},
        "top_windows": top_windows,
        "unified_ranking_summary": unified,
        "theory_summary": theory,
        "scene_summary": scene,
        "findings": findings,
    }


def build_results_report(analysis: dict):
    leader = analysis.get("unified_ranking_summary", {}).get("best_name") or "No clear leader"
    leader_score = analysis.get("unified_ranking_summary", {}).get("best_unified_score")
    theory = analysis.get("theory_summary", {})
    scene = analysis.get("scene_summary", {})

    report = {
        "headline": f"{leader} is the current best candidate under the available ranking bundle." if leader_score is not None else "No stable ranking conclusion could be extracted.",
        "decision_summary": [
            f"Current leader: {leader} (UnifiedScore={leader_score})" if leader_score is not None else "Current leader is unavailable.",
            "Treat theory, scene RMSE, and paper-like scores as complementary evidence rather than interchangeable proofs.",
            "Use the leader only as the next follow-up candidate, not as a publication-grade conclusion by itself.",
        ],
        "safe_claims": [
            f"{leader} is the strongest current candidate within this benchmark bundle." if leader_score is not None else "No safe ranking claim available.",
            "The current evidence supports prioritizing a small number of top candidates for follow-up validation.",
        ],
        "unsupported_claims": [
            "This benchmark alone proves general superiority across all OCT conditions.",
            "A single ranking bundle is sufficient to justify manuscript-level claims about transferability.",
        ],
        "recommended_next_steps": [
            "Carry the top-ranked candidates into a more realistic or physically grounded validation setting.",
            "Check whether the same leader remains stable under changed noise, drift, or field-dependence assumptions.",
            "Convert the current ranking evidence into a task-specific decision instead of a generic best-window narrative.",
        ],
        "risk_flags": [
            "The benchmark may overstate confidence if theoretical and scene metrics diverge.",
            "Transfer from synthetic ranking to real OCT evidence still requires a separate validation step.",
        ],
        "supporting_context": {
            "narrowest_mainlobe_name": theory.get("narrowest_mainlobe_name"),
            "highest_sharpness_name": theory.get("highest_sharpness_name"),
            "best_scene_rmse_name": scene.get("best_scene_rmse_name"),
        },
    }
    return report


def render_results_report_markdown(analysis: dict, report: dict):
    lines = [
        f"# Results Report - {analysis['title']}",
        "",
        f"- Generated: {analysis['generated_at']}",
        f"- Experiment directory: `{analysis['experiment_dir']}`",
        "",
        "## Headline",
        "",
        report["headline"],
        "",
        "## Decision Summary",
        "",
    ]
    lines.extend([f"- {item}" for item in report["decision_summary"]])
    lines.extend(["", "## Safe Claims", ""])
    lines.extend([f"- {item}" for item in report["safe_claims"]])
    lines.extend(["", "## Unsupported Claims", ""])
    lines.extend([f"- {item}" for item in report["unsupported_claims"]])
    lines.extend(["", "## Recommended Next Steps", ""])
    lines.extend([f"- {item}" for item in report["recommended_next_steps"]])
    lines.extend(["", "## Risk Flags", ""])
    lines.extend([f"- {item}" for item in report["risk_flags"]])
    lines.extend(["", "## Analysis Findings", ""])
    for item in analysis.get("findings", []):
        lines.append(f"- {item['claim']}")
        lines.append(f"  Evidence: {item['evidence']}")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def write_progress_note(config: dict, title: str, analysis_path: Path, report_path: Path):
    vault_root = Path(config["vault_root"])
    note_folder = vault_root / config["obsidian"]["progress_folder"]
    note_folder.mkdir(parents=True, exist_ok=True)
    note_path = note_folder / f"Results Report - {title}.md"
    lines = [
        f"# Results Report - {title}",
        "",
        f"- Analysis JSON: `{to_portable_path(analysis_path)}`",
        f"- Report Markdown: `{to_portable_path(report_path)}`",
        "",
        "This note points to the latest strict analysis package and decision-oriented report for this experiment bundle.",
        "",
    ]
    write_text(note_path, "\n".join(lines))
    return note_path


def main():
    parser = argparse.ArgumentParser(description="Turn experiment artifacts into a strict analysis package and a decision-oriented results report.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--experiment-dir", required=True)
    parser.add_argument("--title")
    parser.add_argument("--output-dir")
    parser.add_argument("--write-progress-note", action="store_true")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    experiment_dir = Path(args.experiment_dir)
    title = infer_run_title(experiment_dir, args.title)
    run_dir = create_run_dir(config, args.output_dir, title)
    artifact_paths = find_default_artifacts(experiment_dir)

    analysis = build_analysis_payload(title, experiment_dir, artifact_paths)
    report = build_results_report(analysis)

    analysis_path = run_dir / "analysis.json"
    report_json_path = run_dir / "results_report.json"
    report_md_path = run_dir / "results_report.md"

    write_json(analysis_path, analysis)
    write_json(report_json_path, report)
    write_text(report_md_path, render_results_report_markdown(analysis, report))

    outputs = {
        "run_dir": to_portable_path(run_dir),
        "analysis_json": to_portable_path(analysis_path),
        "results_report_json": to_portable_path(report_json_path),
        "results_report_markdown": to_portable_path(report_md_path),
    }
    if args.write_progress_note:
        note_path = write_progress_note(config, title, analysis_path, report_md_path)
        outputs["progress_note"] = to_portable_path(note_path)

    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
