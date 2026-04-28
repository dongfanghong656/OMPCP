from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SCRIPT_ROOTS = [SCRIPTS_DIR, PROJECT_ROOT]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.report_paths import resolve_reports_dir
from physics.tmatrix_backend import probe_tmatrix_backend


REPORTS_DIR = resolve_reports_dir(__file__)


def resolve_script_path(*names: str) -> Path:
    for base in SCRIPT_ROOTS:
        for name in names:
            candidate = base / name
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"Unable to resolve any of: {', '.join(names)}")


def load_module(module_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_module_with_alias(module_name: str, *candidate_names: str):
    module = sys.modules.get(module_name)
    if module is not None:
        return module
    try:
        return __import__(module_name)
    except ModuleNotFoundError:
        for candidate_name in candidate_names:
            for base in SCRIPT_ROOTS:
                candidate_path = base / candidate_name
                if candidate_path.exists():
                    spec = importlib.util.spec_from_file_location(module_name, candidate_path)
                    if spec is None or spec.loader is None:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    return module
        raise


def load_solver_module():
    return load_module_with_alias(
        "oct_nonspherical_psf_solver",
        "oct_nonspherical_psf_solver.py",
        "01_oct_nonspherical_psf_solver.py",
    )


def build_backend_skipped_report(
    *,
    title: str,
    backend_status: dict,
    report_version_tag: str = "round6p1",
    recommended_next_action: str = "configure_supported_tmatrix_backend_or_use_bundle_builder",
) -> dict:
    return {
        "report_version_tag": report_version_tag,
        "status": "skipped",
        "skip_reason": "tmatrix_backend_unavailable",
        "title": title,
        "tmatrix_backend_status": backend_status,
        "recommended_next_action": recommended_next_action,
    }


def write_skipped_report(
    *,
    json_path: Path,
    md_path: Path,
    title: str,
    backend_status: dict,
    report_version_tag: str = "round6p1",
    recommended_next_action: str = "configure_supported_tmatrix_backend_or_use_bundle_builder",
) -> dict:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_backend_skipped_report(
        title=title,
        backend_status=backend_status,
        report_version_tag=report_version_tag,
        recommended_next_action=recommended_next_action,
    )
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                f"# {title}",
                "",
                "Status: `skipped`",
                "",
                f"Reason: {backend_status.get('reason', 'T-matrix backend unavailable.')}",
                "",
                f"Recommended next action: `{recommended_next_action}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def probe_backend_or_write_skip(
    *,
    title: str,
    json_filename: str,
    md_filename: str,
    write_reports: bool,
    library_path: str | None,
    report_version_tag: str = "round6p1",
    recommended_next_action: str = "configure_supported_tmatrix_backend_or_use_bundle_builder",
) -> tuple[dict, dict | None]:
    backend_status = probe_tmatrix_backend(library_path)
    if backend_status.get("available", False):
        return backend_status, None
    json_path = REPORTS_DIR / json_filename
    md_path = REPORTS_DIR / md_filename
    payload = (
        write_skipped_report(
            json_path=json_path,
            md_path=md_path,
            title=title,
            backend_status=backend_status,
            report_version_tag=report_version_tag,
            recommended_next_action=recommended_next_action,
        )
        if write_reports
        else build_backend_skipped_report(
            title=title,
            backend_status=backend_status,
            report_version_tag=report_version_tag,
            recommended_next_action=recommended_next_action,
        )
    )
    return backend_status, payload
