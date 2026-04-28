from __future__ import annotations

import json
import platform
import sys
from pathlib import Path
from typing import Any

from . import tmatrix_backend as legacy_backend
from .tmatrix_backend_contract import (
    BACKEND_CONTRACT_VERSION,
    TMATRIX_BACKEND_IDS,
    BackendProbe,
)


BACKEND_SELECTION_VERSION = "tmatrix_backend_registry_v1"


def normalize_backend_id(backend_id: str | None) -> str:
    selected = (backend_id or "auto").strip().lower()
    aliases = {
        "legacy": "auto",
        "pytmatrix": "vendored_pytmatrix",
        "python": "vendored_pytmatrix",
        "ctypes": "ctypes_legacy",
        "isoc": "portable_isoc",
    }
    selected = aliases.get(selected, selected)
    if selected not in TMATRIX_BACKEND_IDS:
        allowed = ", ".join(TMATRIX_BACKEND_IDS)
        raise ValueError(f"Unsupported T-matrix backend id {backend_id!r}; expected one of: {allowed}")
    return selected


def _legacy_probe(library_path: str | None = None) -> dict[str, Any]:
    legacy_backend.reset_tmatrix_backend_state()
    return legacy_backend.probe_tmatrix_backend(library_path=library_path)


def probe_backend(
    backend_id: str | None = "auto",
    *,
    library_path: str | None = None,
) -> BackendProbe:
    requested_backend_id = normalize_backend_id(backend_id)
    if requested_backend_id == "portable_isoc":
        return BackendProbe(
            available=False,
            backend_id=None,
            library_path=None,
            reason="portable ISO_C T-matrix backend is not implemented yet",
            requested_backend_id=requested_backend_id,
            diagnostics={"selection_version": BACKEND_SELECTION_VERSION},
        )

    payload = _legacy_probe(library_path=library_path)
    actual_backend = payload.get("backend")
    if requested_backend_id == "vendored_pytmatrix" and actual_backend != "python":
        return BackendProbe(
            available=False,
            backend_id=actual_backend,
            library_path=payload.get("library_path"),
            reason=payload.get("reason") or f"requested vendored_pytmatrix backend, got {actual_backend!r}",
            requested_backend_id=requested_backend_id,
            diagnostics={"selection_version": BACKEND_SELECTION_VERSION, "legacy_probe": payload},
        )
    if requested_backend_id == "ctypes_legacy" and actual_backend != "ctypes":
        return BackendProbe(
            available=False,
            backend_id=actual_backend,
            library_path=payload.get("library_path"),
            reason=payload.get("reason") or f"requested ctypes_legacy backend, got {actual_backend!r}",
            requested_backend_id=requested_backend_id,
            diagnostics={"selection_version": BACKEND_SELECTION_VERSION, "legacy_probe": payload},
        )
    return BackendProbe(
        available=bool(payload.get("available")),
        backend_id=actual_backend,
        library_path=payload.get("library_path"),
        reason=payload.get("reason"),
        requested_backend_id=requested_backend_id,
        diagnostics={"selection_version": BACKEND_SELECTION_VERSION, "legacy_probe": payload},
    )


def build_backend_provenance(
    backend_id: str | None = "auto",
    *,
    library_path: str | None = None,
) -> dict[str, Any]:
    probe = probe_backend(backend_id=backend_id, library_path=library_path)
    return {
        "report_kind": "tmatrix_backend_provenance",
        "contract_version": BACKEND_CONTRACT_VERSION,
        "selection_version": BACKEND_SELECTION_VERSION,
        "requested_backend_id": probe.requested_backend_id,
        "backend_available": probe.available,
        "backend_id": probe.backend_id,
        "library_path": probe.library_path,
        "reason": probe.reason,
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "sys_platform": sys.platform,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "diagnostics": probe.diagnostics,
    }


def write_backend_provenance(path: str | Path, provenance: dict[str, Any]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return output_path


def require_backend_available(provenance: dict[str, Any]) -> None:
    if provenance.get("backend_available"):
        return
    requested = provenance.get("requested_backend_id", "auto")
    reason = provenance.get("reason") or "T-matrix backend unavailable"
    raise RuntimeError(f"T-matrix backend {requested!r} is required but unavailable: {reason}")
