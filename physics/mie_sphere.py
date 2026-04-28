"""Pure-Python Mie helpers for the sphere-only OCT branch.

This module is independent of the non-spherical T-matrix backend. It implements
the Bohren-Huffman S1/S2 convention used by many Mie references.

Inputs:
    m_rel: complex refractive index of sphere divided by medium index.
    x: size parameter in the embedding medium, x = 2*pi*a*n_medium/lambda0.
    mu: cos(scattering_angle), where mu=-1 is exact backscatter.

The default channel mapping matches the current round6 fixed-basis T-matrix
smoke gate: S22 is mapped to the Mie S2 amplitude. At exact backscatter,
S1 = -S2 under this convention.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


SUPPORTED_MIE_CHANNELS = ("S11", "S22", "S12", "S21", "CO_POL", "AVG_DIAG", "S1", "S2")


@dataclass(frozen=True)
class MieSphereResult:
    """Container for validated sphere Mie amplitudes."""

    m_rel: complex
    x: float
    mu: np.ndarray
    a_n: np.ndarray
    b_n: np.ndarray
    s1: np.ndarray
    s2: np.ndarray
    nmax: int
    convention_id: str = "bohren_huffman_s1_s2"


def wiscombe_nmax(x: float) -> int:
    """Return a conservative Mie-series truncation order."""

    x = float(abs(x))
    if x < 1e-12:
        return 5
    return max(int(x + 4.05 * x ** (1.0 / 3.0) + 2) + 2, 5)


def mie_size_parameter(radius_um: float, wavelength_vacuum_um: float, n_medium: complex | float) -> float:
    """Return x = 2*pi*a*n_medium/lambda0 using the real medium phase index."""

    return float(2.0 * np.pi * float(np.real(n_medium)) * float(radius_um) / float(wavelength_vacuum_um))


def mie_ab(m_rel: complex, x: float, nmax: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Compute Mie a_n and b_n coefficients for a homogeneous sphere."""

    x = float(x)
    if nmax is None:
        nmax = wiscombe_nmax(x)
    nmax = int(nmax)
    if nmax < 1:
        raise ValueError("nmax must be positive.")
    if x < 1e-12:
        return np.zeros(nmax, dtype=np.complex128), np.zeros(nmax, dtype=np.complex128)

    m = complex(m_rel)
    mx = m * x
    if abs(mx) < 1e-14:
        raise ValueError("m_rel*x is too small for stable Mie coefficient evaluation.")

    nmx = max(nmax + 1, int(abs(mx)) + 1) + 20
    d = np.zeros(nmx + 2, dtype=np.complex128)
    for n in range(nmx, 0, -1):
        d[n - 1] = n / mx - 1.0 / (d[n] + n / mx)

    psi = np.zeros(nmax + 2, dtype=float)
    chi = np.zeros(nmax + 2, dtype=float)
    psi[0] = np.sin(x)
    psi[1] = np.sin(x) / x - np.cos(x)
    chi[0] = np.cos(x)
    chi[1] = np.cos(x) / x + np.sin(x)
    for n in range(1, nmax + 1):
        psi[n + 1] = (2 * n + 1) / x * psi[n] - psi[n - 1]
        chi[n + 1] = (2 * n + 1) / x * chi[n] - chi[n - 1]

    xi = psi - 1j * chi
    a = np.zeros(nmax, dtype=np.complex128)
    b = np.zeros(nmax, dtype=np.complex128)
    for n in range(1, nmax + 1):
        a[n - 1] = ((d[n] / m + n / x) * psi[n] - psi[n - 1]) / (
            (d[n] / m + n / x) * xi[n] - xi[n - 1]
        )
        b[n - 1] = ((m * d[n] + n / x) * psi[n] - psi[n - 1]) / (
            (m * d[n] + n / x) * xi[n] - xi[n - 1]
        )
    return a, b


def mie_pi_tau(mu: np.ndarray | float, nmax: int) -> tuple[np.ndarray, np.ndarray]:
    """Return angular functions pi_n(mu), tau_n(mu)."""

    mu_arr = np.asarray(mu, dtype=float)
    if nmax < 1:
        raise ValueError("nmax must be positive.")
    pi_all = np.zeros((nmax,) + mu_arr.shape, dtype=float)
    tau_all = np.zeros_like(pi_all)
    pi_nm1 = np.zeros_like(mu_arr, dtype=float)
    pi_n = np.ones_like(mu_arr, dtype=float)
    for n in range(1, nmax + 1):
        tau_n = n * mu_arr * pi_n - (n + 1) * pi_nm1
        pi_all[n - 1] = pi_n
        tau_all[n - 1] = tau_n
        pi_np1 = ((2 * n + 1) * mu_arr * pi_n - (n + 1) * pi_nm1) / n
        pi_nm1, pi_n = pi_n, pi_np1
    return pi_all, tau_all


def mie_s1_s2_from_ab(a_n: np.ndarray, b_n: np.ndarray, mu: np.ndarray | float) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate Bohren-Huffman complex amplitude functions S1 and S2."""

    a = np.asarray(a_n, dtype=np.complex128)
    b = np.asarray(b_n, dtype=np.complex128)
    if a.shape != b.shape or a.ndim != 1:
        raise ValueError("a_n and b_n must be one-dimensional arrays with matching shape.")
    mu_arr = np.asarray(mu, dtype=float)
    pi_all, tau_all = mie_pi_tau(mu_arr, len(a))
    s1 = np.zeros_like(mu_arr, dtype=np.complex128)
    s2 = np.zeros_like(mu_arr, dtype=np.complex128)
    for idx, n in enumerate(range(1, len(a) + 1)):
        factor = (2 * n + 1) / (n * (n + 1))
        s1 = s1 + factor * (a[idx] * pi_all[idx] + b[idx] * tau_all[idx])
        s2 = s2 + factor * (a[idx] * tau_all[idx] + b[idx] * pi_all[idx])
    return s1, s2


def mie_s1_s2(m_rel: complex, x: float, mu: np.ndarray | float, nmax: int | None = None) -> MieSphereResult:
    """Compute Mie S1/S2 amplitudes for one wavelength and many angles."""

    a, b = mie_ab(m_rel, x, nmax=nmax)
    s1, s2 = mie_s1_s2_from_ab(a, b, mu)
    return MieSphereResult(
        m_rel=complex(m_rel),
        x=float(x),
        mu=np.asarray(mu, dtype=float),
        a_n=a,
        b_n=b,
        s1=s1,
        s2=s2,
        nmax=len(a),
    )


def select_mie_channel(s1: np.ndarray, s2: np.ndarray, channel: str = "S22") -> np.ndarray:
    """Map scalar Mie amplitudes to the round6 fixed-basis channel labels."""

    label = str(channel).strip().upper()
    s1_arr = np.asarray(s1, dtype=np.complex128)
    s2_arr = np.asarray(s2, dtype=np.complex128)
    if s1_arr.shape != s2_arr.shape:
        raise ValueError("s1 and s2 must have the same shape.")
    mapping = {
        "S11": s1_arr,
        "S22": s2_arr,
        "S1": s1_arr,
        "S2": s2_arr,
        "S12": np.zeros_like(s1_arr),
        "S21": np.zeros_like(s1_arr),
        "CO_POL": 0.5 * (s1_arr + s2_arr),
        "AVG_DIAG": 0.5 * (s1_arr + s2_arr),
    }
    if label not in mapping:
        raise ValueError(f"Unsupported sphere Mie channel {channel!r}; expected one of {SUPPORTED_MIE_CHANNELS}.")
    return mapping[label]


def mie_backscatter_amplitude(m_rel: complex, x: float, nmax: int | None = None, *, channel: str = "S22") -> complex:
    """Return exact-backscatter amplitude for the requested fixed-basis channel."""

    result = mie_s1_s2(m_rel, x, np.array([-1.0]), nmax=nmax)
    return complex(select_mie_channel(result.s1, result.s2, channel)[0])


def mie_efficiencies(m_rel: complex, x: float, nmax: int | None = None) -> dict[str, float]:
    """Return standard efficiency factors Qext, Qsca, Qabs, Qback."""

    x = float(x)
    if x < 1e-12:
        return {"qext": 0.0, "qsca": 0.0, "qabs": 0.0, "qback": 0.0}
    a, b = mie_ab(m_rel, x, nmax=nmax)
    n = np.arange(1, len(a) + 1, dtype=float)
    weights = 2 * n + 1
    qext = (2.0 / x**2) * np.sum(weights * np.real(a + b))
    qsca = (2.0 / x**2) * np.sum(weights * (np.abs(a) ** 2 + np.abs(b) ** 2))
    back_sum = np.sum(weights * ((-1.0) ** n) * (a - b))
    qback = np.abs(back_sum) ** 2 / x**2
    return {
        "qext": float(np.real(qext)),
        "qsca": float(np.real(qsca)),
        "qabs": float(np.real(qext - qsca)),
        "qback": float(np.real(qback)),
    }


def compare_backscatter_convention(m_rel: complex, x: float) -> dict[str, float]:
    """Diagnostic showing that S22 equals the current round6 s_back_full convention."""

    a, b = mie_ab(m_rel, x)
    n = np.arange(1, len(a) + 1)
    s_back_round6 = 0.5 * np.sum((2 * n + 1) * ((-1) ** n) * (a - b))
    s1, s2 = mie_s1_s2_from_ab(a, b, np.array([-1.0]))
    return {
        "abs_s22_minus_round6": float(abs(s2[0] - s_back_round6)),
        "abs_s11_plus_s22": float(abs(s1[0] + s2[0])),
        "round6_backscatter_abs": float(abs(s_back_round6)),
    }
