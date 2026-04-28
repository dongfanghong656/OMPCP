from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
DEFAULT_READINESS_JSON = REPORTS_DIR / "round6p1_cp310_evidence_rebuild_readiness.json"
DEFAULT_READINESS_MD = REPORTS_DIR / "round6p1_cp310_evidence_rebuild_readiness.md"


def _split_command(value: str) -> list[str]:
    return shlex.split(value, posix=os.name != "nt")


def build_candidate_python_commands(*, explicit_python: str | None = None, env: dict | None = None) -> list[list[str]]:
    env = env or os.environ
    candidates: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()

    def add(command: list[str]) -> None:
        key = tuple(command)
        if command and key not in seen:
            seen.add(key)
            candidates.append(command)

    if explicit_python:
        add(_split_command(explicit_python))
    for env_name in ("ROUND6P1_CP310_PYTHON", "OCT_CP310_PYTHON"):
        value = env.get(env_name)
        if value:
            add(_split_command(value))
    add(["py", "-3.10"])
    add(["python3.10"])
    add(["python"])
    return candidates


def _run_json_command(command: list[str], *, timeout_s: int = 60) -> tuple[int | None, str, str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except FileNotFoundError as exc:
        return None, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        return None, exc.stdout or "", f"timeout after {timeout_s}s: {exc.stderr or ''}".strip()
    return completed.returncode, completed.stdout, completed.stderr


def probe_python_runtime(
    python_command: list[str],
    *,
    project_root: Path = PROJECT_ROOT,
    library_path: str | None = None,
    backend_id: str = "auto",
) -> dict:
    probe_code = f"""
import json
import platform
import sys
from pathlib import Path
project_root = Path({str(project_root)!r})
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
from physics.tmatrix_backend_registry import build_backend_provenance
library_path = {library_path!r}
backend_id = {backend_id!r}
provenance = build_backend_provenance(backend_id, library_path=library_path)
payload = {{
    "python_executable": sys.executable,
    "python_version": platform.python_version(),
    "python_version_info": list(sys.version_info[:3]),
    "sys_platform": sys.platform,
    "platform": platform.platform(),
    "is_cp310": sys.version_info[:2] == (3, 10),
    "is_windows": sys.platform.startswith("win"),
    "tmatrix_backend_status": {{
        "available": provenance.get("backend_available"),
        "backend": provenance.get("backend_id"),
        "library_path": provenance.get("library_path"),
        "reason": provenance.get("reason"),
    }},
    "tmatrix_backend_provenance": provenance,
}}
print(json.dumps(payload))
"""
    return_code, stdout, stderr = _run_json_command([*python_command, "-c", probe_code])
    payload = {
        "python_command": python_command,
        "return_code": return_code,
        "stdout": stdout,
        "stderr": stderr,
    }
    if return_code != 0 or not stdout.strip():
        payload["probe_status"] = "runtime_probe_failed"
        return payload
    try:
        payload.update(json.loads(stdout.strip().splitlines()[-1]))
        payload["probe_status"] = "runtime_probe_ok"
    except json.JSONDecodeError as exc:
        payload["probe_status"] = "runtime_probe_invalid_json"
        payload["json_error"] = str(exc)
    return payload


def classify_probe_payload(probe: dict) -> dict:
    if probe.get("probe_status") != "runtime_probe_ok":
        return {
            "readiness_status": "cp310_runtime_unavailable",
            "ready_to_rebuild": False,
            "reason": probe.get("stderr") or probe.get("json_error") or "runtime probe failed",
        }
    if not probe.get("is_cp310"):
        return {
            "readiness_status": "wrong_python_runtime",
            "ready_to_rebuild": False,
            "reason": f"expected CPython 3.10, got {probe.get('python_version')}",
        }
    provenance = probe.get("tmatrix_backend_provenance") or {}
    backend = probe.get("tmatrix_backend_status") or {}
    backend_available = provenance.get("backend_available") if provenance else backend.get("available")
    if not backend_available:
        return {
            "readiness_status": "backend_unavailable_in_cp310_runtime",
            "ready_to_rebuild": False,
            "reason": provenance.get("reason") or backend.get("reason", "T-matrix backend unavailable"),
        }
    return {
        "readiness_status": "ready_to_rebuild",
        "ready_to_rebuild": True,
        "reason": "CPython 3.10 runtime and T-matrix backend are available.",
    }


def find_first_readiness_candidate(
    candidates: list[list[str]],
    *,
    library_path: str | None = None,
    backend_id: str = "auto",
) -> dict:
    probes = []
    for command in candidates:
        probe = probe_python_runtime(command, library_path=library_path, backend_id=backend_id)
        probe["classification"] = classify_probe_payload(probe)
        probes.append(probe)
        if probe["classification"].get("ready_to_rebuild"):
            return {"selected_probe": probe, "probes": probes}
    selected = probes[0] if probes else {
        "probe_status": "no_candidate_commands",
        "classification": {
            "readiness_status": "cp310_runtime_unavailable",
            "ready_to_rebuild": False,
            "reason": "No candidate Python commands were available.",
        },
    }
    return {"selected_probe": selected, "probes": probes}


def run_evidence_builder(
    python_command: list[str],
    *,
    rebuild_reports_dir: Path,
    library_path: str | None = None,
) -> dict:
    command = [
        *python_command,
        str(PROJECT_ROOT / "scripts" / "build_round6p1_evidence_package.py"),
        "--reports-dir",
        str(rebuild_reports_dir),
    ]
    if library_path:
        command.extend(["--library-path", library_path])
    return_code, stdout, stderr = _run_json_command(command, timeout_s=1800)
    return {
        "command": command,
        "return_code": return_code,
        "stdout": stdout,
        "stderr": stderr,
        "rebuild_reports_dir": str(rebuild_reports_dir),
    }


def render_readiness_markdown(report: dict) -> str:
    selected = report.get("selected_probe") or {}
    classification = selected.get("classification") or {}
    lines = [
        "# round6p1 CPython 3.10 Evidence Rebuild Readiness",
        "",
        f"- readiness_status: `{classification.get('readiness_status')}`",
        f"- ready_to_rebuild: `{classification.get('ready_to_rebuild')}`",
        f"- selected_python_command: `{selected.get('python_command')}`",
        f"- selected_python_version: `{selected.get('python_version')}`",
        f"- reason: {classification.get('reason')}",
        f"- execute_requested: `{report.get('execute_requested')}`",
        "",
        "## Scope",
        "",
        "This report only answers whether the local runtime can regenerate T-matrix-backed round6p1 evidence.",
        "It does not replace the Plus/Pro review bundle and does not imply fresh numerical evidence unless `rebuild_result` is present and successful.",
    ]
    rebuild = report.get("rebuild_result")
    if rebuild:
        lines.extend(
            [
                "",
                "## Rebuild Result",
                "",
                f"- return_code: `{rebuild.get('return_code')}`",
                f"- rebuild_reports_dir: `{rebuild.get('rebuild_reports_dir')}`",
            ]
        )
    return "\n".join(lines) + "\n"


def build_readiness_report(args) -> dict:
    candidates = build_candidate_python_commands(explicit_python=args.python_executable)
    library_path = args.tmatrix_lib_path or args.library_path
    candidate_result = find_first_readiness_candidate(
        candidates,
        library_path=library_path,
        backend_id=args.tmatrix_backend,
    )
    selected = candidate_result["selected_probe"]
    classification = selected["classification"]
    report = {
        "report_kind": "round6p1_cp310_evidence_rebuild_readiness",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(PROJECT_ROOT),
        "candidate_python_commands": candidates,
        "selected_probe": selected,
        "all_probes": candidate_result["probes"],
        "readiness_status": classification.get("readiness_status"),
        "ready_to_rebuild": bool(classification.get("ready_to_rebuild")),
        "execute_requested": bool(args.execute),
        "strict_requested": bool(args.strict),
        "library_path": library_path,
        "tmatrix_backend_requested_id": args.tmatrix_backend,
    }
    if args.execute:
        if classification.get("ready_to_rebuild"):
            rebuild_dir = Path(args.rebuild_reports_dir) if args.rebuild_reports_dir else REPORTS_DIR / (
                "round6p1_cp310_rebuild_" + datetime.now().strftime("%Y%m%d-%H%M%S")
            )
            report["rebuild_result"] = run_evidence_builder(
                selected["python_command"],
                rebuild_reports_dir=rebuild_dir,
                library_path=library_path,
            )
            report["rebuild_status"] = (
                "rebuild_completed"
                if report["rebuild_result"].get("return_code") == 0
                else "rebuild_failed"
            )
        else:
            report["rebuild_status"] = "not_executed_not_ready"
    else:
        report["rebuild_status"] = "not_requested"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe and optionally run a controlled CPython 3.10 round6p1 evidence rebuild."
    )
    parser.add_argument("--python-executable", default=None, help="Explicit Python command, e.g. py -3.10 or C:/Python310/python.exe.")
    parser.add_argument("--library-path", default=None, help="Optional explicit T-matrix library path.")
    parser.add_argument("--tmatrix-backend", default="auto", help="T-matrix backend id to require during the CPython 3.10 probe.")
    parser.add_argument("--tmatrix-lib-path", default=None, help="Alias for --library-path used by the backend registry/provenance contract.")
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR), help="Directory for readiness report artifacts.")
    parser.add_argument("--output-json", default=None, help="Optional readiness JSON path.")
    parser.add_argument("--output-md", default=None, help="Optional readiness Markdown path.")
    parser.add_argument("--rebuild-reports-dir", default=None, help="Reports directory to use when --execute is requested.")
    parser.add_argument("--execute", action="store_true", help="Run the evidence builder if CPython 3.10 and T-matrix backend are ready.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when readiness or rebuild fails.")
    parser.add_argument("--no-write", action="store_true", help="Print report without writing readiness artifacts.")
    args = parser.parse_args(argv)

    reports_dir = Path(args.reports_dir)
    output_json = Path(args.output_json) if args.output_json else reports_dir / DEFAULT_READINESS_JSON.name
    output_md = Path(args.output_md) if args.output_md else reports_dir / DEFAULT_READINESS_MD.name
    report = build_readiness_report(args)
    payload = json.dumps(report, indent=2)
    print(payload)
    if not args.no_write:
        reports_dir.mkdir(parents=True, exist_ok=True)
        output_json.write_text(payload + "\n", encoding="utf-8")
        output_md.write_text(render_readiness_markdown(report), encoding="utf-8")
    if not args.strict:
        return 0
    if not report.get("ready_to_rebuild"):
        return 2
    if report.get("rebuild_status") == "rebuild_failed":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
