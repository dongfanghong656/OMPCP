from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np


BACKEND_CONTRACT_VERSION = "tmatrix_backend_contract_v1"
TMATRIX_BACKEND_IDS = (
    "auto",
    "vendored_pytmatrix",
    "ctypes_legacy",
    "portable_isoc",
)


@dataclass(frozen=True)
class BackendProbe:
    available: bool
    backend_id: str | None
    library_path: str | None
    reason: str | None = None
    requested_backend_id: str = "auto"
    contract_version: str = BACKEND_CONTRACT_VERSION
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TMatrixRequest:
    radius_um: float
    wavelength_medium_um: float
    m_rel: complex
    axis_ratio: float
    shape: int = -1
    rat: float = 1.0
    ddelt: float = 1e-3
    ndgs: int = 2
    thet0: float = 90.0
    thet: float = 90.0
    phi0: float = 0.0
    phi: float = 180.0
    alpha: float = 0.0
    beta: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["m_rel"] = [float(np.real(self.m_rel)), float(np.imag(self.m_rel))]
        return payload


@dataclass(frozen=True)
class TMatrixResult:
    s_matrix: np.ndarray
    z_matrix: np.ndarray
    backend_id: str
    convention_id: str
    request: TMatrixRequest
    nmax: int | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "convention_id": self.convention_id,
            "request": self.request.to_dict(),
            "nmax": self.nmax,
            "diagnostics": dict(self.diagnostics),
            "s_matrix_shape": list(np.asarray(self.s_matrix).shape),
            "z_matrix_shape": list(np.asarray(self.z_matrix).shape),
        }
