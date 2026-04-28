import argparse
import ctypes
import importlib.util
import json
import math
import os
import sys
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.interpolate import RectBivariateSpline
from scipy.signal import find_peaks

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.report_paths import resolve_reports_dir, resolve_runtime_root
from physics.tmatrix_backend_contract import TMATRIX_BACKEND_IDS
from physics.tmatrix_backend_registry import (
    build_backend_provenance,
    require_backend_available,
    write_backend_provenance,
)
from physics.sphere_mie_pupil import build_sphere_mie_bfp_field
from solvers.coefficient_path_bundle import (
    COEFFICIENT_MAP_MODEL_IDS,
    RENDERED_BASIS_SHIFT_TARGETS,
)

sys.modules.setdefault("oct_nonspherical_psf_solver", sys.modules[__name__])

COEFFICIENT_MAP_RUNTIME_MODES = (
    "native_branch_assembly",
    "rendered_basis_override",
)
SPHERE_MIE_EPS_TOL = 1e-12

_ROUND6_EXTENSION_ALIASES = {
    "10_vector_pupil_overlap_bridge.py": ("10_vector_pupil_overlap_bridge.py", "02_vector_pupil_overlap_bridge.py"),
    "11_low_na_asymptotic.py": ("11_low_na_asymptotic.py", "03_low_na_asymptotic.py"),
    "validate_oct_nonspherical_psf_solver.py": (
        "validate_oct_nonspherical_psf_solver.py",
        "04_validate_oct_nonspherical_psf_solver.py",
    ),
}
def mie_ab(m, x, nmax=None):
    if x < 1e-12:
        nmax = nmax or 5
        return np.zeros(nmax, dtype=complex), np.zeros(nmax, dtype=complex)
    if nmax is None:
        nmax = max(int(x + 4.05 * x ** (1.0 / 3.0) + 2) + 2, 5)
    mx = m * x
    nmx = max(nmax + 1, int(abs(mx)) + 1) + 20
    d = np.zeros(nmx + 2, dtype=complex)
    for n in range(nmx, 0, -1):
        d[n - 1] = n / mx - 1.0 / (d[n] + n / mx)
    psi = np.zeros(nmax + 2)
    chi = np.zeros(nmax + 2)
    psi[0], psi[1] = np.sin(x), np.sin(x) / x - np.cos(x)
    chi[0], chi[1] = np.cos(x), np.cos(x) / x + np.sin(x)
    for n in range(1, nmax + 1):
        psi[n + 1] = (2 * n + 1) / x * psi[n] - psi[n - 1]
        chi[n + 1] = (2 * n + 1) / x * chi[n] - chi[n - 1]
    xi = psi - 1j * chi
    a = np.zeros(nmax, dtype=complex)
    b = np.zeros(nmax, dtype=complex)
    for n in range(1, nmax + 1):
        a[n - 1] = ((d[n] / m + n / x) * psi[n] - psi[n - 1]) / ((d[n] / m + n / x) * xi[n] - xi[n - 1])
        b[n - 1] = ((m * d[n] + n / x) * psi[n] - psi[n - 1]) / ((m * d[n] + n / x) * xi[n] - xi[n - 1])
    return a, b


def s_back_full(a, b):
    return 0.5 * sum((2 * n + 1) * ((-1) ** n) * (a[n - 1] - b[n - 1]) for n in range(1, len(a) + 1))


def n_tio2_anatase(l_um):
    return np.sqrt(5.825 + 0.2441 / (l_um**2 - 0.0803))


_FE2O3_O_DATA = np.array(
    [
        [0.70, 2.972, 0.031], [0.71, 2.956, 0.028], [0.72, 2.942, 0.026], [0.73, 2.929, 0.024],
        [0.74, 2.916, 0.022], [0.75, 2.903, 0.021], [0.76, 2.892, 0.020], [0.77, 2.882, 0.020],
        [0.78, 2.872, 0.019], [0.79, 2.862, 0.019], [0.80, 2.853, 0.020], [0.81, 2.845, 0.022],
        [0.82, 2.838, 0.024], [0.83, 2.833, 0.025], [0.84, 2.828, 0.026], [0.85, 2.824, 0.027],
        [0.86, 2.820, 0.027], [0.87, 2.816, 0.026], [0.88, 2.813, 0.026], [0.89, 2.809, 0.026],
        [0.90, 2.805, 0.024], [0.91, 2.801, 0.024], [0.92, 2.798, 0.023], [0.93, 2.794, 0.023],
        [0.94, 2.791, 0.023], [0.95, 2.789, 0.022], [0.96, 2.787, 0.021], [0.97, 2.784, 0.020],
        [0.98, 2.781, 0.018], [0.99, 2.778, 0.017], [1.00, 2.775, 0.015], [1.01, 2.771, 0.015],
        [1.02, 2.768, 0.014], [1.03, 2.765, 0.013], [1.04, 2.762, 0.012], [1.05, 2.759, 0.011],
        [1.06, 2.755, 0.011], [1.07, 2.753, 0.011], [1.08, 2.750, 0.011], [1.09, 2.747, 0.011],
        [1.10, 2.745, 0.011],
    ]
)
_FE2O3_E_DATA = np.array(
    [
        [0.70, 2.675, 0.075], [0.71, 2.662, 0.072], [0.72, 2.652, 0.068], [0.73, 2.641, 0.066],
        [0.74, 2.631, 0.063], [0.75, 2.621, 0.061], [0.76, 2.612, 0.060], [0.77, 2.604, 0.059],
        [0.78, 2.596, 0.058], [0.79, 2.589, 0.057], [0.80, 2.582, 0.057], [0.81, 2.575, 0.057],
        [0.82, 2.570, 0.058], [0.83, 2.566, 0.059], [0.84, 2.562, 0.059], [0.85, 2.559, 0.059],
        [0.86, 2.555, 0.058], [0.87, 2.552, 0.058], [0.88, 2.549, 0.057], [0.89, 2.547, 0.056],
        [0.90, 2.544, 0.054], [0.91, 2.541, 0.053], [0.92, 2.537, 0.053], [0.93, 2.535, 0.052],
        [0.94, 2.533, 0.051], [0.95, 2.531, 0.051], [0.96, 2.529, 0.049], [0.97, 2.527, 0.048],
        [0.98, 2.525, 0.046], [0.99, 2.522, 0.045], [1.00, 2.520, 0.043], [1.01, 2.517, 0.042],
        [1.02, 2.515, 0.042], [1.03, 2.512, 0.040], [1.04, 2.510, 0.039], [1.05, 2.507, 0.039],
        [1.06, 2.504, 0.038], [1.07, 2.502, 0.038], [1.08, 2.500, 0.037], [1.09, 2.498, 0.037],
        [1.10, 2.496, 0.036],
    ]
)


def _validate_wavelength_range(model_name, l_um, minimum_um, maximum_um):
    values = np.asarray(l_um, dtype=float)
    if np.any((values < minimum_um) | (values > maximum_um)):
        raise ValueError(
            f"{model_name} is only configured for wavelengths in [{minimum_um:.3f}, {maximum_um:.3f}] um; "
            f"got {values.min():.3f} to {values.max():.3f} um."
        )


def _interp_tabulated_material(model_name, dataset, l_um):
    _validate_wavelength_range(model_name, l_um, float(dataset[0, 0]), float(dataset[-1, 0]))
    return np.interp(l_um, dataset[:, 0], dataset[:, 1]) + 1j * np.interp(l_um, dataset[:, 0], dataset[:, 2])


def n_fe2o3_o(l_um):
    return _interp_tabulated_material("Fe2O3-o", _FE2O3_O_DATA, l_um)


def n_fe2o3_e(l_um):
    return _interp_tabulated_material("Fe2O3-e", _FE2O3_E_DATA, l_um)


def n_ps(l_um):
    return np.sqrt(2.3809 + 0.01233 / (l_um**2 - 0.01615))


def n_sio2(l_um):
    l2 = l_um**2
    return np.sqrt(1 + 0.6961663 * l2 / (l2 - 0.0684043**2) + 0.4079426 * l2 / (l2 - 0.1162414**2) + 0.8974794 * l2 / (l2 - 9.896161**2))


def n_pdms(l_um):
    return 1.3997 + 4.20e-3 / l_um**2


MATERIALS = {
    "TiO2-anatase": n_tio2_anatase,
    "Fe2O3-o": n_fe2o3_o,
    "Fe2O3-e": n_fe2o3_e,
    "PS": n_ps,
    "SiO2": n_sio2,
    "PDMS": n_pdms,
}

PROJECT_OCT_MATERIAL_SUPPORT_RANGE_UM = (0.700, 1.100)

MATERIAL_SUPPORT = {
    "TiO2-anatase": {
        "kind": "analytic_formula",
        "range_um": PROJECT_OCT_MATERIAL_SUPPORT_RANGE_UM,
        "source": "encoded analytic dispersion formula used by the round6 OCT particle solver",
        "range_basis": "project OCT operating window guard",
        "units": "um",
        "extrapolation_policy": "error_outside_encoded_range",
    },
    "Fe2O3-o": {
        "kind": "tabulated",
        "range_um": (0.700, 1.100),
        "source": "encoded Querry ordinary-index table",
        "range_basis": "tabulated data endpoints",
        "units": "um",
        "extrapolation_policy": "error_outside_encoded_range",
    },
    "Fe2O3-e": {
        "kind": "tabulated",
        "range_um": (0.700, 1.100),
        "source": "encoded Querry extraordinary-index table",
        "range_basis": "tabulated data endpoints",
        "units": "um",
        "extrapolation_policy": "error_outside_encoded_range",
    },
    "PS": {
        "kind": "analytic_formula",
        "range_um": PROJECT_OCT_MATERIAL_SUPPORT_RANGE_UM,
        "source": "encoded analytic dispersion formula used by the round6 OCT particle solver",
        "range_basis": "project OCT operating window guard",
        "units": "um",
        "extrapolation_policy": "error_outside_encoded_range",
    },
    "SiO2": {
        "kind": "analytic_formula",
        "range_um": PROJECT_OCT_MATERIAL_SUPPORT_RANGE_UM,
        "source": "encoded analytic Sellmeier-style dispersion formula used by the round6 OCT particle solver",
        "range_basis": "project OCT operating window guard",
        "units": "um",
        "extrapolation_policy": "error_outside_encoded_range",
    },
    "PDMS": {
        "kind": "analytic_formula",
        "range_um": PROJECT_OCT_MATERIAL_SUPPORT_RANGE_UM,
        "source": "encoded analytic engineering PDMS approximation used by the round6 OCT particle solver",
        "range_basis": "project OCT operating window guard",
        "units": "um",
        "extrapolation_policy": "error_outside_encoded_range",
    },
}

MATERIAL_RANGE_NOTES = {
    "TiO2-anatase": "analytic dispersion formula guarded to the project OCT operating window 0.700-1.100 um; no extrapolation outside this range",
    "Fe2O3-o": "tabulated Querry data with enforced wavelength support from 0.700 um to 1.100 um",
    "Fe2O3-e": "tabulated Querry data with enforced wavelength support from 0.700 um to 1.100 um",
    "PS": "analytic dispersion formula guarded to the project OCT operating window 0.700-1.100 um; no extrapolation outside this range",
    "SiO2": "analytic dispersion formula guarded to the project OCT operating window 0.700-1.100 um; no extrapolation outside this range",
    "PDMS": "analytic engineering approximation guarded to the project OCT operating window 0.700-1.100 um; no extrapolation outside this range",
}

_MATERIAL_SUPPORT_WARNING_CACHE = set()

SCHEMA_VERSION = "round6-v1"

LOW_NA_APPROXIMATION_LABEL = "separable low-NA spectral-envelope approximation"
FULL_NA_APPROXIMATION_LABEL = "fixed-basis single-channel scalar pupil-propagation approximation"
LOW_NA_DISPLAY_LABEL = "low_na_separable_baseline"
LOW_NA_ASYMPTOTIC_DISPLAY_LABEL = "low_na_asymptotic"
FULL_NA_DISPLAY_LABEL = "full_na_scalar_fixed_basis_baseline"
VECTOR_BRIDGE_DISPLAY_LABEL = "vector_pupil_overlap_bridge"
LOW_NA_BASELINE_MODE = "low_na_separable_baseline"
LOW_NA_ASYMPTOTIC_MODE = "low_na_asymptotic"
FULL_NA_BASELINE_MODE = "full_na_scalar_fixed_basis"
VECTOR_BRIDGE_MODE = "vector_pupil_overlap_bridge"
VECTOR_BRIDGE_APPROXIMATION_LABEL = "vector Jones-projected scalar pupil-propagation bridge approximation"
AMP_COMPONENT_SEMANTICS = (
    "amp_component selects one scattering-matrix element in a fixed internal backscatter basis; "
    "it is not a rigorously projected OCT tx/rx detection channel."
)
FULL_NA_PROPAGATION_NOTE = (
    "full_na currently applies scalar pupil propagation with a sqrt(cos(theta)) obliquity factor, "
    "but it does not implement a full vector Debye/Richards-Wolf or c_rx^H T c_tx imaging model."
)
SHAPE_PARAMETERIZATION_NOTE = (
    "non-spherical support is limited to an axisymmetric deformation family controlled by eps plus a single beta_deg tilt; "
    "it is not a general Euler-angle / general-shape solver."
)
SPECTRAL_MODEL_NOTE = (
    "the source is sampled uniformly in wavelength and reconstructed through a nu=n/lambda integral; "
    "this models a theoretical axial response, not a full swept-source OCT interferogram pipeline with k-linearization and dispersion compensation."
)
OPD_AXIS_NOTE = (
    "The axial reconstruction axis is currently an optical-path-difference (OPD) axis defined through exp(i 2*pi*nu*opd) with nu=n/lambda; "
    "it is not yet relabeled as single-pass physical depth."
)
PUBLIC_AMP_COMPONENTS = ("S22", "CO_POL")
PUBLIC_JONES_MODES = ("linear_x", "linear_y", "co_pol", "cross_pol")

_EXTENSION_MODULE_CACHE = {}


def resolve_material_model(name):
    if not isinstance(name, str) and np.isscalar(name):
        return lambda _l_um, value=complex(name): value
    if callable(name):
        return name
    if isinstance(name, str) and name not in MATERIALS:
        try:
            value = complex(name)
            return lambda _l_um, numeric=value: numeric
        except ValueError:
            pass
    if name not in MATERIALS:
        raise KeyError(f"Unknown material: {name}")
    return MATERIALS[name]


def material_support_metadata(name):
    if callable(name):
        return {
            "material": getattr(name, "__name__", "callable_material"),
            "kind": "callable",
            "range_um": None,
            "has_explicit_range": False,
            "policy_note": "user-supplied callable material; wavelength support is not encoded",
        }
    if not isinstance(name, str) and np.isscalar(name):
        return {
            "material": repr(complex(name)),
            "kind": "constant",
            "range_um": None,
            "has_explicit_range": True,
            "policy_note": "explicit constant refractive index supplied by caller",
        }
    if isinstance(name, str) and name not in MATERIALS:
        try:
            return {
                "material": repr(complex(name)),
                "kind": "constant",
                "range_um": None,
                "has_explicit_range": True,
                "policy_note": "explicit constant refractive index supplied by caller",
            }
        except ValueError:
            pass
    support = MATERIAL_SUPPORT.get(name, {"kind": "unknown", "range_um": None})
    range_um = support.get("range_um")
    return {
        "material": str(name),
        "kind": support.get("kind", "unknown"),
        "range_um": range_um,
        "has_explicit_range": range_um is not None,
        "wavelength_units": support.get("units", "um"),
        "support_source": support.get("source"),
        "range_basis": support.get("range_basis"),
        "extrapolation_policy": support.get(
            "extrapolation_policy",
            "error_outside_encoded_range" if range_um is not None else "not_encoded",
        ),
        "policy_note": MATERIAL_RANGE_NOTES.get(str(name), "no material support note recorded"),
    }


def validate_material_support(material, lambda_nm, *, strict_material_range=False, role="material"):
    metadata = material_support_metadata(material)
    metadata["role"] = role
    metadata["strict_material_range"] = bool(strict_material_range)
    range_um = metadata.get("range_um")
    lam_um = np.asarray(lambda_nm, dtype=float) / 1000.0
    if range_um is not None:
        _validate_wavelength_range(str(metadata["material"]), lam_um, float(range_um[0]), float(range_um[1]))
        metadata["status"] = "validated_range"
        metadata["validated_wavelength_min_um"] = float(np.min(lam_um))
        metadata["validated_wavelength_max_um"] = float(np.max(lam_um))
        return metadata
    if strict_material_range and metadata["kind"] not in {"constant"}:
        raise ValueError(
            f"{role}={metadata['material']} does not have an explicit encoded wavelength support range; "
            "strict_material_range=True requires a validated range-backed material model."
        )
    if metadata["kind"] in {"analytic_formula", "callable"}:
        warning_key = (role, metadata["material"], metadata["kind"])
        if warning_key not in _MATERIAL_SUPPORT_WARNING_CACHE:
            warnings.warn(
                f"{role}={metadata['material']} is being used without an explicit encoded wavelength support range; "
                "set strict_material_range=True for paper-grade runs.",
                RuntimeWarning,
                stacklevel=2,
            )
            _MATERIAL_SUPPORT_WARNING_CACHE.add(warning_key)
        metadata["status"] = "warning_no_explicit_range"
    else:
        metadata["status"] = "accepted_without_range_check"
    return metadata


def reset_material_support_warning_cache():
    _MATERIAL_SUPPORT_WARNING_CACHE.clear()


def resolve_round6_extension_path(module_filename: str) -> Path:
    script_dir = Path(__file__).resolve().parent
    candidate_names = _ROUND6_EXTENSION_ALIASES.get(module_filename, (module_filename,))
    for candidate in candidate_names:
        candidate_path = script_dir / candidate
        if candidate_path.exists():
            return candidate_path
    raise ImportError(
        f"Unable to locate round6 extension '{module_filename}'. Tried: "
        + ", ".join(str(script_dir / candidate) for candidate in candidate_names)
    )


def load_round6_extension(module_filename, module_name):
    module_path = resolve_round6_extension_path(module_filename)
    cache_key = (str(module_path), module_name)
    cached = _EXTENSION_MODULE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load extension module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    _EXTENSION_MODULE_CACHE[cache_key] = module
    return module


def source_spectrum_lambda(lambda0_nm=855.0, fwhm_nm=56.0, npts=201):
    sigma = fwhm_nm / (2 * np.sqrt(2 * np.log(2)))
    lam = np.linspace(lambda0_nm - 5 * sigma, lambda0_nm + 5 * sigma, npts)
    return lam, np.exp(-0.5 * ((lam - lambda0_nm) / sigma) ** 2)


def trapezoid_weights(axis):
    axis = np.asarray(axis, dtype=float)
    w = np.zeros_like(axis)
    w[1:-1] = 0.5 * (axis[2:] - axis[:-2])
    w[0] = 0.5 * (axis[1] - axis[0])
    w[-1] = 0.5 * (axis[-1] - axis[-2])
    return w


def integrate_trapezoid(values, axis):
    if hasattr(np, "trapezoid"):
        return np.trapezoid(values, axis)
    return np.trapz(values, axis)


def normalize_intensity(values, return_scale=False):
    values = np.asarray(values, dtype=float)
    vmax = float(np.max(values)) if values.size else 1.0
    normalized = values / vmax if vmax > 0 else values
    if return_scale:
        return normalized, vmax
    return normalized


def interp_crossing(x, y, level, left=True):
    idx = np.where(y < level)[0]
    if len(idx) == 0:
        return float(x[0] if left else x[-1])
    if left:
        pos = idx[-1]
        x1, x2, y1, y2 = x[pos], x[pos + 1], y[pos], y[pos + 1]
    else:
        pos = idx[0]
        x1, x2, y1, y2 = x[pos - 1], x[pos], y[pos - 1], y[pos]
    return float(x1 + (level - y1) * (x2 - x1) / (y2 - y1 + 1e-30))


def axial_profile_metrics(opd_um, profile, *, quantity_kind="intensity"):
    opd_um = np.asarray(opd_um, dtype=float)
    profile = normalize_intensity(profile)
    pk = int(np.argmax(profile))
    peak_opd = float(opd_um[pk])
    zl = interp_crossing(opd_um[: pk + 1], profile[: pk + 1], 0.5, left=True)
    zr = interp_crossing(opd_um[pk:], profile[pk:], 0.5, left=False)
    fwhm = zr - zl
    mask = (opd_um >= peak_opd - 1.5 * fwhm) & (opd_um <= peak_opd + 1.5 * fwhm)
    centroid = float(np.sum(opd_um[mask] * profile[mask]) / (np.sum(profile[mask]) + 1e-30))
    sidelobes = profile.copy()
    sidelobes[mask] = 0.0
    peaks, _ = find_peaks(sidelobes, prominence=1e-6)
    if len(peaks):
        sidelobe_peak = float(np.max(sidelobes[peaks]))
        log_factor = 10.0 if quantity_kind == "intensity" else 20.0
        psr = float(log_factor * np.log10(sidelobe_peak + 1e-30))
    else:
        sidelobe_peak = 0.0
        psr = float("-inf")
    rejection_db = float("inf") if not np.isfinite(psr) else float(-psr)
    total_energy = float(integrate_trapezoid(profile, opd_um))
    sidelobe_energy = float(integrate_trapezoid(sidelobes, opd_um))
    return {
        "axis_kind": "opd",
        "quantity_kind": quantity_kind,
        "normalization_mode": "unit_peak_profile",
        "shape_metric_note": "profile is normalized to unit peak before FWHM/centroid/PSR evaluation; metrics are shape-oriented, not absolute-amplitude observables",
        "peak_opd_um": peak_opd,
        "centroid_opd_um": centroid,
        "fwhm_opd_um": float(fwhm),
        "psr_db": psr,
        "psr_definition": "sidelobe_to_main_db",
        "psr_reference": quantity_kind,
        "sidelobe_to_main_db": psr,
        "main_to_sidelobe_rejection_db": rejection_db,
        "peak_value": float(profile[pk]),
        "strongest_sidelobe_value": sidelobe_peak,
        "sidelobe_energy_fraction": float(sidelobe_energy / (total_energy + 1e-30)),
    }


def serialize_geometry_series(geometry_series):
    return {
        "lambda_nm": geometry_series["lambda_nm"].tolist(),
        "n_medium": geometry_series["n_medium"].tolist(),
        "sin_theta_max": geometry_series["sin_theta_max"].tolist(),
        "theta_max_rad": geometry_series["theta_max_rad"].tolist(),
        "theta_max_deg": geometry_series["theta_max_deg"].tolist(),
    }


def to_json_compatible(value):
    if isinstance(value, np.ndarray):
        return [to_json_compatible(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, complex):
        return {"real": float(np.real(value)), "imag": float(np.imag(value))}
    if isinstance(value, dict):
        return {str(key): to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_compatible(item) for item in value]
    return value


def build_depth_convention_helper(opd_um, reference_n_medium):
    reference_n_medium = float(np.real(reference_n_medium))
    opd_um = np.asarray(opd_um, dtype=float)
    return {
        "axis_kind": "opd",
        "depth_axis_status": "helper_only_not_frozen_for_paper",
        "paper_depth_axis_kind": "opd_interpreted_via_reference_n",
        "reference_n_medium": reference_n_medium,
        "single_pass_depth_from_reference_n_note": "single_pass_depth_from_reference_n_um ~= opd_um / (2 * reference_n_medium)",
        "single_pass_depth_from_reference_n_scale": 1.0 / (2.0 * reference_n_medium),
        "double_pass_depth_from_reference_n_note": "double_pass_depth_from_reference_n_um ~= opd_um / reference_n_medium",
        "double_pass_depth_from_reference_n_scale": 1.0 / reference_n_medium,
        "opd_span_um": [float(opd_um.min()), float(opd_um.max())],
        "single_pass_depth_from_reference_n_span_um": [
            float(opd_um.min() / (2.0 * reference_n_medium)),
            float(opd_um.max() / (2.0 * reference_n_medium)),
        ],
        "double_pass_depth_from_reference_n_span_um": [
            float(opd_um.min() / reference_n_medium),
            float(opd_um.max() / reference_n_medium),
        ],
        "conversion_scope_note": "These helper scales use the center-wavelength reference medium index and are provided for interpretation only.",
    }


def build_normalization_metadata(*, normalized_fields, raw_fields, normalization_scope, absolute_amplitude_supported):
    return {
        "normalization_scope": normalization_scope,
        "absolute_amplitude_supported": bool(absolute_amplitude_supported),
        "normalized_fields": list(normalized_fields),
        "raw_fields": list(raw_fields),
        "note": "Normalized outputs are intended for shape comparisons. Raw outputs preserve pre-normalization magnitudes but do not, by themselves, constitute a fully calibrated OCT throughput model.",
    }


def build_base_result_metadata(*, approximation_label, solver_output_kind="xz_slice", quantity_kind="intensity", axial_axis_kind="opd", paper_safe=False):
    return {
        "approximation_label": approximation_label,
        "solver_output_kind": solver_output_kind,
        "quantity_kind": quantity_kind,
        "axial_axis_kind": axial_axis_kind,
        "schema_version": SCHEMA_VERSION,
        "paper_safe": bool(paper_safe),
    }


def build_full_na_axial_views(x_um, opd_um, raw_intensity_xz, raw_envelope_xz):
    center_idx = int(np.argmin(np.abs(x_um)))
    peak_index = np.unravel_index(int(np.argmax(raw_intensity_xz)), raw_intensity_xz.shape)
    peakline_idx = int(peak_index[0])
    raw_peak_intensity = float(raw_intensity_xz[peak_index])
    raw_peak_envelope = float(raw_envelope_xz[peak_index])
    centerline_raw_axial_intensity = np.asarray(raw_intensity_xz[center_idx, :], dtype=float)
    centerline_raw_axial_envelope = np.asarray(raw_envelope_xz[center_idx, :], dtype=float)
    peakline_raw_axial_intensity = np.asarray(raw_intensity_xz[peakline_idx, :], dtype=float)
    peakline_raw_axial_envelope = np.asarray(raw_envelope_xz[peakline_idx, :], dtype=float)
    centerline_axial_intensity = normalize_intensity(centerline_raw_axial_intensity)
    centerline_axial_envelope = normalize_intensity(centerline_raw_axial_envelope)
    peakline_axial_intensity = normalize_intensity(peakline_raw_axial_intensity)
    peakline_axial_envelope = normalize_intensity(peakline_raw_axial_envelope)
    return {
        "global_peak_index": [int(peak_index[0]), int(peak_index[1])],
        "raw_peak_intensity": raw_peak_intensity,
        "raw_peak_envelope": raw_peak_envelope,
        "centerline_x_index": center_idx,
        "centerline_x_um": float(x_um[center_idx]),
        "peakline_x_index": peakline_idx,
        "peakline_x_um": float(x_um[peakline_idx]),
        "centerline_raw_axial_intensity": centerline_raw_axial_intensity,
        "centerline_raw_axial_envelope": centerline_raw_axial_envelope,
        "peakline_raw_axial_intensity": peakline_raw_axial_intensity,
        "peakline_raw_axial_envelope": peakline_raw_axial_envelope,
        "centerline_axial_intensity": centerline_axial_intensity,
        "centerline_axial_envelope": centerline_axial_envelope,
        "peakline_axial_intensity": peakline_axial_intensity,
        "peakline_axial_envelope": peakline_axial_envelope,
        "centerline_axial_intensity_metrics": axial_profile_metrics(opd_um, centerline_axial_intensity, quantity_kind="intensity"),
        "centerline_axial_envelope_metrics": axial_profile_metrics(opd_um, centerline_axial_envelope, quantity_kind="envelope"),
        "peakline_axial_intensity_metrics": axial_profile_metrics(opd_um, peakline_axial_intensity, quantity_kind="intensity"),
        "peakline_axial_envelope_metrics": axial_profile_metrics(opd_um, peakline_axial_envelope, quantity_kind="envelope"),
        "primary_axial_metrics_line": "peakline",
        "primary_axial_metrics_note": "full_na primary axial metrics are reported on the x-line that contains the global intensity maximum; centerline metrics are returned separately for comparison.",
    }


def derive_na_geometry(na, n_medium):
    n_medium_real = float(np.real(n_medium))
    if n_medium_real <= 0:
        raise ValueError(f"Medium refractive index must be positive, got {n_medium!r}")
    if na < 0:
        raise ValueError(f"Sample-side NA must be non-negative, got {na!r}")
    sin_theta_max = na / n_medium_real
    if sin_theta_max > 1.0 + 1e-12:
        raise ValueError(f"Sample-side NA={na!r} exceeds n_medium={n_medium_real!r}; cannot derive a real theta_max.")
    sin_theta_max = float(np.clip(sin_theta_max, 0.0, 1.0))
    theta_max_rad = float(np.arcsin(sin_theta_max))
    return {
        "na": float(na),
        "n_medium": n_medium_real,
        "sin_theta_max": sin_theta_max,
        "theta_max_rad": theta_max_rad,
        "theta_max_deg": float(np.rad2deg(theta_max_rad)),
    }


def derive_na_geometry_series(lambda_nm, medium_material, na):
    medium_fn = resolve_material_model(medium_material)
    lam_um = np.asarray(lambda_nm, dtype=float) / 1000.0
    n_medium = np.array([float(np.real(medium_fn(l_um))) for l_um in lam_um], dtype=float)
    per_lambda = [derive_na_geometry(na, n_value) for n_value in n_medium]
    return {
        "lambda_nm": np.asarray(lambda_nm, dtype=float),
        "n_medium": n_medium,
        "sin_theta_max": np.array([entry["sin_theta_max"] for entry in per_lambda], dtype=float),
        "theta_max_rad": np.array([entry["theta_max_rad"] for entry in per_lambda], dtype=float),
        "theta_max_deg": np.array([entry["theta_max_deg"] for entry in per_lambda], dtype=float),
    }


def gaussian_lateral_intensity(x_um, lambda0_nm, na):
    if na <= 0:
        return np.ones_like(x_um, dtype=float)
    fwhm_um = 0.37 * (lambda0_nm / 1000.0) / na
    return normalize_intensity(np.exp(-4 * np.log(2) * (x_um / max(fwhm_um, 1e-9)) ** 2))


DEFAULT_LIB_CANDIDATES: list[Path] = []


def _build_local_pytmatrix_source_roots():
    runtime_root = resolve_runtime_root(__file__)
    candidate_roots = []
    for root in (SCRIPT_DIR, runtime_root, runtime_root.parent, SCRIPT_DIR.parent):
        if root is None:
            continue
        if root not in candidate_roots:
            candidate_roots.append(root)
    candidate_paths = []
    for root in candidate_roots:
        for relative in (
            Path("vendor") / "pytmatrix-0.3.3",
            Path("vendor") / "pytmatrix-src" / "pytmatrix-0.3.3",
        ):
            candidate = root / relative
            if candidate not in candidate_paths:
                candidate_paths.append(candidate)
    return candidate_paths


LOCAL_PYTMATRIX_SOURCE_ROOTS = _build_local_pytmatrix_source_roots()
_TMATRIX_LIB = None
_CALCTMAT = None
_CALCAMPL = None
_TMATRIX_LIB_PATH = None
_TMATRIX_BACKEND = None
_PYTMATRIX_MODULE = None
_DLL_DIRECTORY_HANDLES = []
_DLL_DIRECTORY_PATHS = set()


def reset_tmatrix_backend_state(*, drop_python_modules: bool = False):
    global _TMATRIX_LIB, _CALCTMAT, _CALCAMPL, _TMATRIX_LIB_PATH, _TMATRIX_BACKEND, _PYTMATRIX_MODULE
    _TMATRIX_LIB = None
    _CALCTMAT = None
    _CALCAMPL = None
    _TMATRIX_LIB_PATH = None
    _TMATRIX_BACKEND = None
    _PYTMATRIX_MODULE = None
    while _DLL_DIRECTORY_HANDLES:
        handle = _DLL_DIRECTORY_HANDLES.pop()
        try:
            handle.close()
        except Exception:
            pass
    _DLL_DIRECTORY_PATHS.clear()
    if drop_python_modules:
        for module_name in list(sys.modules):
            if module_name == "pytmatrix" or module_name.startswith("pytmatrix."):
                sys.modules.pop(module_name, None)


@dataclass
class SourceConfig:
    lambda0_nm: float = 855.0
    fwhm_nm: float = 56.0
    n_lambda: int = 201


@dataclass
class GridConfig:
    z_span_um: float = 40.0
    n_z: int = 2001
    x_span_um: float = 8.0
    n_x: int = 129
    na: float = 0.05
    n_bfp_dense: int = 129
    n_bfp_sparse: int = 11


@dataclass
class SolverConfig:
    mode: str = "low_na"
    particle_material: str = "TiO2-anatase"
    medium_material: str = "PDMS"
    diameter_nm: float = 200.0
    eps: float = 0.0
    beta_deg: float = 0.0
    amp_component: str = "S22"
    ideal: bool = False
    force_tmatrix: bool = False
    library_path: str | None = None
    tmatrix_backend: str = "auto"
    strict_material_range: bool = False
    incident_mode: str = "linear_x"
    detection_mode: str = "co_pol"
    second_order_model: str = "tensor_closure"
    mu2_wavelength_model: str = "frozen_at_lambda0"
    lateral_shift_model: str = "none"
    lateral_shift_coupling: str = "envelope_only"
    lateral_shift_impl: str = "interp"
    lateral_slice_axis: str = "x"
    effective_channel_fit_strategy: str = "split_even_odd"
    effective_channel_theta_fit_max_rad: float | None = None
    effective_channel_theta_fit_fraction: float = 0.35
    effective_channel_theta_fit_cap_rad: float = 0.08
    effective_channel_n_theta_fit: int = 9
    effective_channel_n_azimuth_fit: int = 4
    coefficient_map_model_id: str = "identity_slice_projected_rendered_basis"
    coefficient_map_runtime_mode: str = "native_branch_assembly"
    coefficient_map_artifact_path: str | None = None
    rendered_basis_shift_target: str = "baseline_envelope_ratio"


def _candidate_library_paths(library_path=None):
    candidates = []
    if library_path:
        candidates.append(Path(library_path))
    env_path = os.environ.get("PYTMATRIX_LIB")
    if env_path:
        candidates.append(Path(env_path))
    runtime_root = resolve_runtime_root(__file__)
    for search_root in (SCRIPT_DIR, runtime_root):
        candidates.extend(
            [
                search_root / "libpytmatrix.dll",
                search_root / "libpytmatrix.so",
                search_root / "libpytmatrix.dylib",
            ]
        )
    candidates.extend(DEFAULT_LIB_CANDIDATES)
    unique = []
    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _add_python_backend_search_paths():
    for source_root in LOCAL_PYTMATRIX_SOURCE_ROOTS:
        if source_root.exists() and str(source_root) not in sys.path:
            sys.path.insert(0, str(source_root))
        fortran_dir = source_root / "pytmatrix" / "fortran_tm"
        if fortran_dir.exists() and hasattr(os, "add_dll_directory"):
            directory_key = str(fortran_dir)
            if directory_key in _DLL_DIRECTORY_PATHS:
                continue
            handle = os.add_dll_directory(directory_key)
            _DLL_DIRECTORY_HANDLES.append(handle)
            _DLL_DIRECTORY_PATHS.add(directory_key)


def _vendored_python_backend_note():
    binary_names = []
    for source_root in LOCAL_PYTMATRIX_SOURCE_ROOTS:
        fortran_dir = source_root / "pytmatrix" / "fortran_tm"
        if not fortran_dir.exists():
            continue
        binary_names.extend(path.name for path in fortran_dir.glob("pytmatrix.*") if path.is_file())
    if not binary_names:
        return None
    runtime_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    is_windows_runtime = sys.platform.startswith("win")
    compatible = any(
        runtime_tag in binary_name and (("win" in binary_name.lower()) == is_windows_runtime)
        for binary_name in binary_names
    )
    if compatible:
        return None
    joined = ", ".join(sorted(binary_names))
    return (
        f"vendored pytmatrix backend inventory is incompatible with the current runtime "
        f"(platform={sys.platform}, python={runtime_tag}); found: {joined}"
    )


def ensure_tmatrix_loaded(library_path=None):
    global _TMATRIX_LIB, _CALCTMAT, _CALCAMPL, _TMATRIX_LIB_PATH, _TMATRIX_BACKEND, _PYTMATRIX_MODULE
    if _TMATRIX_BACKEND is not None:
        return _TMATRIX_LIB_PATH
    errors = []
    for candidate in _candidate_library_paths(library_path):
        try:
            lib = ctypes.CDLL(str(candidate))
            _TMATRIX_LIB = lib
            _CALCTMAT = lib.calctmat_
            _CALCAMPL = lib.calcampl_
            _TMATRIX_LIB_PATH = str(candidate)
            _TMATRIX_BACKEND = "ctypes"
            return _TMATRIX_LIB_PATH
        except OSError as error:
            errors.append(f"{candidate}: {error}")
    _add_python_backend_search_paths()
    try:
        from pytmatrix.fortran_tm import pytmatrix as pytmatrix_module

        _PYTMATRIX_MODULE = pytmatrix_module
        _TMATRIX_LIB_PATH = "python:pytmatrix.fortran_tm.pytmatrix"
        _TMATRIX_BACKEND = "python"
        return _TMATRIX_LIB_PATH
    except Exception as error:  # pragma: no cover - diagnostic path
        errors.append(f"python:pytmatrix.fortran_tm.pytmatrix: {error}")
    vendor_note = _vendored_python_backend_note()
    if vendor_note:
        errors.append(vendor_note)
    raise FileNotFoundError("Unable to load libpytmatrix. " + " | ".join(errors))


def probe_tmatrix_backend(library_path=None):
    try:
        backend_path = ensure_tmatrix_loaded(library_path=library_path)
        return {
            "available": True,
            "backend": _TMATRIX_BACKEND,
            "library_path": backend_path,
            "reason": None,
        }
    except FileNotFoundError as error:
        return {
            "available": False,
            "backend": None,
            "library_path": None,
            "reason": str(error),
        }


def calc_sz(radius_um, wavelength_medium_um, m_rel, axis_ratio, *, thet0=90.0, thet=90.0, phi0=0.0, phi=180.0, alpha=0.0, beta=0.0, shape=-1, rat=1.0, ddelt=1e-3, ndgs=2, library_path=None):
    ensure_tmatrix_loaded(library_path=library_path)
    if _TMATRIX_BACKEND == "python":
        nmax = _PYTMATRIX_MODULE.calctmat(radius_um, rat, wavelength_medium_um, float(np.real(m_rel)), float(np.imag(m_rel)), axis_ratio, shape, ddelt, ndgs)
        s, z = _PYTMATRIX_MODULE.calcampl(nmax, wavelength_medium_um, thet0, thet, phi0, phi, alpha, beta)
        return np.asarray(s, dtype=np.complex128), np.asarray(z, dtype=np.float64)
    nmax = ctypes.c_int()
    args1 = [
        ctypes.c_double(radius_um),
        ctypes.c_double(rat),
        ctypes.c_double(wavelength_medium_um),
        ctypes.c_double(float(np.real(m_rel))),
        ctypes.c_double(float(np.imag(m_rel))),
        ctypes.c_double(axis_ratio),
        ctypes.c_int(shape),
        ctypes.c_double(ddelt),
        ctypes.c_int(ndgs),
        nmax,
    ]
    _CALCTMAT(*[ctypes.byref(x) for x in args1])
    s = np.zeros((2, 2), dtype=np.complex128, order="F")
    z = np.zeros((4, 4), dtype=np.float64, order="F")
    args2 = [ctypes.c_int(nmax.value), ctypes.c_double(wavelength_medium_um), ctypes.c_double(thet0), ctypes.c_double(thet), ctypes.c_double(phi0), ctypes.c_double(phi), ctypes.c_double(alpha), ctypes.c_double(beta)]
    _CALCAMPL(
        *[ctypes.byref(x) for x in args2],
        s.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        z.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
    )
    return s, z


def select_amplitude_component(s_matrix, amp_component="S22"):
    # This is a fixed-basis channel pick, not a rigorous OCT tx/rx projection.
    component = amp_component.upper()
    mapping = {
        "S11": s_matrix[0, 0],
        "S12": s_matrix[0, 1],
        "S21": s_matrix[1, 0],
        "S22": s_matrix[1, 1],
        "CO_POL": 0.5 * (s_matrix[0, 0] + s_matrix[1, 1]),
        "AVG_DIAG": 0.5 * (s_matrix[0, 0] + s_matrix[1, 1]),
    }
    if component not in mapping:
        raise ValueError(f"Unsupported amp_component: {amp_component}")
    return mapping[component]


def spectral_cube_to_xz(lambda_nm, spectral_cube, opd_um, medium_material):
    cube = np.asarray(spectral_cube, dtype=np.complex128)
    cube = cube[:, None] if cube.ndim == 1 else cube
    lam_um = np.asarray(lambda_nm, dtype=float) / 1000.0
    medium_fn = resolve_material_model(medium_material)
    n_medium = np.array([float(np.real(medium_fn(l))) for l in lam_um], dtype=float)
    nu = n_medium / lam_um
    order = np.argsort(nu)
    kernel = np.exp(1j * 2 * np.pi * nu[order, None] * opd_um[None, :]) * trapezoid_weights(nu[order])[:, None]
    return cube[order, :].T @ kernel


def mie_backscatter_spectrum(diameter_nm, particle_material, medium_material, lambda_nm):
    particle_fn = resolve_material_model(particle_material)
    medium_fn = resolve_material_model(medium_material)
    out = np.zeros(len(lambda_nm), dtype=np.complex128)
    for i, lam_nm in enumerate(lambda_nm):
        lam_um = lam_nm / 1000.0
        n_medium = medium_fn(lam_um)
        m = particle_fn(lam_um) / n_medium
        x = np.pi * diameter_nm * float(np.real(n_medium)) / lam_nm
        a, b = mie_ab(m, x)
        out[i] = s_back_full(a, b)
    return out


def tmatrix_backscatter_spectrum(diameter_nm, eps, beta_deg, particle_material, medium_material, lambda_nm, amp_component="S22", library_path=None):
    particle_fn = resolve_material_model(particle_material)
    medium_fn = resolve_material_model(medium_material)
    out = np.zeros(len(lambda_nm), dtype=np.complex128)
    radius_um = diameter_nm / 2000.0
    for i, lam_nm in enumerate(lambda_nm):
        lam_um = lam_nm / 1000.0
        n_medium = medium_fn(lam_um)
        s_matrix, _ = calc_sz(radius_um, lam_um / float(np.real(n_medium)), particle_fn(lam_um) / n_medium, 1.0 + eps, beta=beta_deg, library_path=library_path)
        out[i] = select_amplitude_component(s_matrix, amp_component=amp_component)
    return out


def _spherical_to_cart(theta_deg, phi_deg):
    theta = np.deg2rad(theta_deg)
    phi = np.deg2rad(phi_deg)
    return np.array([math.sin(theta) * math.cos(phi), math.sin(theta) * math.sin(phi), math.cos(theta)], dtype=float)


def _backscatter_basis(thet0_deg=90.0, phi0_deg=0.0):
    incident = _spherical_to_cart(thet0_deg, phi0_deg)
    backscatter = -incident
    reference = np.array([0.0, 0.0, 1.0], dtype=float)
    if abs(np.dot(reference, backscatter)) > 0.99:
        reference = np.array([0.0, 1.0, 0.0], dtype=float)
    tangent_u = np.cross(reference, backscatter)
    tangent_u /= np.linalg.norm(tangent_u)
    tangent_v = np.cross(backscatter, tangent_u)
    tangent_v /= np.linalg.norm(tangent_v)
    return backscatter, tangent_u, tangent_v


def _build_unit_pupil_grid(n_bfp=129):
    pupil_axis = np.linspace(-1.0, 1.0, n_bfp)
    u_pupil, v_pupil = np.meshgrid(pupil_axis, pupil_axis)
    valid_mask = (u_pupil**2 + v_pupil**2) <= 1.0
    return {"pupil_axis": pupil_axis, "u_pupil": u_pupil, "v_pupil": v_pupil, "valid_mask": valid_mask}


def build_bfp_angle_map(sin_theta_max=0.0, n_bfp=129, thet0_deg=90.0, phi0_deg=0.0):
    base_grid = _build_unit_pupil_grid(n_bfp=n_bfp)
    tx = sin_theta_max * base_grid["u_pupil"]
    ty = sin_theta_max * base_grid["v_pupil"]
    tz = np.sqrt(np.clip(1.0 - tx**2 - ty**2, 0.0, None))
    backscatter, tangent_u, tangent_v = _backscatter_basis(thet0_deg=thet0_deg, phi0_deg=phi0_deg)
    directions = backscatter[None, None, :] * tz[..., None] + tangent_u[None, None, :] * tx[..., None] + tangent_v[None, None, :] * ty[..., None]
    directions /= np.linalg.norm(directions, axis=-1, keepdims=True)
    theta_deg = np.rad2deg(np.arccos(np.clip(directions[..., 2], -1.0, 1.0)))
    phi_deg = np.rad2deg(np.arctan2(directions[..., 1], directions[..., 0])) % 360.0
    return {
        "pupil_axis": base_grid["pupil_axis"],
        "u_pupil": base_grid["u_pupil"],
        "v_pupil": base_grid["v_pupil"],
        "valid_mask": base_grid["valid_mask"],
        "theta_deg": theta_deg,
        "phi_deg": phi_deg,
        "sin_theta_max": float(sin_theta_max),
    }


def _interpolate_sparse_complex_grid(sparse_samples, sparse_axis, dense_axis, dense_valid_mask):
    order = 3 if len(sparse_axis) >= 4 else 1
    real_spline = RectBivariateSpline(sparse_axis, sparse_axis, np.ascontiguousarray(np.real(sparse_samples)), kx=order, ky=order)
    imag_spline = RectBivariateSpline(sparse_axis, sparse_axis, np.ascontiguousarray(np.imag(sparse_samples)), kx=order, ky=order)
    dense = real_spline(dense_axis, dense_axis) + 1j * imag_spline(dense_axis, dense_axis)
    dense[~dense_valid_mask] = 0.0
    return dense


def build_particle_bfp_field(diameter_nm, eps, beta_deg, particle_material, medium_material, lambda_nm, *, sin_theta_max, n_bfp_dense=129, n_bfp_sparse=11, amp_component="S22", library_path=None):
    particle_fn = resolve_material_model(particle_material)
    medium_fn = resolve_material_model(medium_material)
    sin_theta_max_values = np.asarray(sin_theta_max, dtype=float)
    if sin_theta_max_values.ndim == 0:
        sin_theta_max_values = np.full(len(lambda_nm), float(sin_theta_max_values), dtype=float)
    if sin_theta_max_values.shape != (len(lambda_nm),):
        raise ValueError("sin_theta_max must be scalar or match lambda_nm length")
    dense_grid = _build_unit_pupil_grid(n_bfp=n_bfp_dense)
    sparse_grid = _build_unit_pupil_grid(n_bfp=n_bfp_sparse)
    field_dense = np.zeros((n_bfp_dense, n_bfp_dense, len(lambda_nm)), dtype=np.complex128)
    radius_um = diameter_nm / 2000.0
    for k, lam_nm in enumerate(lambda_nm):
        lam_um = lam_nm / 1000.0
        n_medium = medium_fn(lam_um)
        sparse_map = build_bfp_angle_map(sin_theta_max=sin_theta_max_values[k], n_bfp=n_bfp_sparse)
        sparse_samples = np.zeros((n_bfp_sparse, n_bfp_sparse), dtype=np.complex128)
        for row in range(n_bfp_sparse):
            for col in range(n_bfp_sparse):
                if not sparse_grid["valid_mask"][row, col]:
                    continue
                s_matrix, _ = calc_sz(radius_um, lam_um / float(np.real(n_medium)), particle_fn(lam_um) / n_medium, 1.0 + eps, thet=sparse_map["theta_deg"][row, col], phi=sparse_map["phi_deg"][row, col], beta=beta_deg, library_path=library_path)
                sparse_samples[row, col] = select_amplitude_component(s_matrix, amp_component=amp_component)
        field_dense[:, :, k] = _interpolate_sparse_complex_grid(sparse_samples, sparse_grid["pupil_axis"], dense_grid["pupil_axis"], dense_grid["valid_mask"])
    return {
        "field_cube": field_dense,
        "pupil_axis": dense_grid["pupil_axis"],
        "u_pupil": dense_grid["u_pupil"],
        "v_pupil": dense_grid["v_pupil"],
        "valid_mask": dense_grid["valid_mask"],
    }


def build_ideal_bfp_field(lambda_nm, *, n_bfp_dense=129):
    dense_map = _build_unit_pupil_grid(n_bfp=n_bfp_dense)
    field_dense = np.zeros((n_bfp_dense, n_bfp_dense, len(lambda_nm)), dtype=np.complex128)
    field_dense[dense_map["valid_mask"], :] = 1.0
    return {
        "field_cube": field_dense,
        "pupil_axis": dense_map["pupil_axis"],
        "u_pupil": dense_map["u_pupil"],
        "v_pupil": dense_map["v_pupil"],
        "valid_mask": dense_map["valid_mask"],
    }


def should_use_sphere_mie_full_na_branch(solver):
    return (
        not bool(getattr(solver, "ideal", False))
        and not bool(getattr(solver, "force_tmatrix", False))
        and abs(float(getattr(solver, "eps", 0.0))) <= SPHERE_MIE_EPS_TOL
    )


def pupil_field_to_lateral_line(bundle, lambda_nm, x_um, sin_theta_max, medium_material, lateral_slice_axis="x"):
    medium_fn = resolve_material_model(medium_material)
    sin_theta_max_values = np.asarray(sin_theta_max, dtype=float)
    if sin_theta_max_values.ndim == 0:
        sin_theta_max_values = np.full(len(lambda_nm), float(sin_theta_max_values), dtype=float)
    if sin_theta_max_values.shape != (len(lambda_nm),):
        raise ValueError("sin_theta_max must be scalar or match lambda_nm length")
    weights_1d = trapezoid_weights(bundle["pupil_axis"])
    weights_2d = np.outer(weights_1d, weights_1d)
    mask = bundle["valid_mask"]
    u_flat = bundle["u_pupil"][mask]
    v_flat = bundle["v_pupil"][mask]
    axis = str(lateral_slice_axis).strip().lower()
    if axis == "x":
        lateral_coordinate = u_flat
    elif axis == "y":
        lateral_coordinate = v_flat
    else:
        raise ValueError(f"Unsupported lateral_slice_axis: {lateral_slice_axis}")
    radial_sq = u_flat**2 + v_flat**2
    w_flat = weights_2d[mask]
    field_line = np.zeros((len(lambda_nm), len(x_um)), dtype=np.complex128)
    for k, lam_nm in enumerate(lambda_nm):
        k_medium = 2 * np.pi * float(np.real(medium_fn(lam_nm / 1000.0))) / (lam_nm / 1000.0)
        # k_medium * sin(theta_max) is equivalent to k0 * NA when NA = n_medium * sin(theta_max).
        phase = np.exp(1j * k_medium * sin_theta_max_values[k] * np.outer(x_um, lateral_coordinate))
        local_cos_theta = np.sqrt(np.clip(1.0 - (sin_theta_max_values[k] ** 2) * radial_sq, 0.0, None))
        obliquity_weight = np.sqrt(local_cos_theta)
        field_line[k, :] = phase @ (w_flat * obliquity_weight * bundle["field_cube"][:, :, k][mask])
    return field_line


def solve_low_na_slice(source, grid, solver):
    lambda_nm, source_power = source_spectrum_lambda(source.lambda0_nm, source.fwhm_nm, source.n_lambda)
    x_um = np.linspace(-0.5 * grid.x_span_um, 0.5 * grid.x_span_um, grid.n_x)
    opd_um = np.linspace(-grid.z_span_um, grid.z_span_um, grid.n_z)
    material_support = {
        "medium_material": validate_material_support(solver.medium_material, lambda_nm, strict_material_range=solver.strict_material_range, role="medium_material"),
    }
    if solver.ideal:
        spectrum = np.ones_like(lambda_nm, dtype=np.complex128)
        tmatrix_used = False
        material_support["particle_material"] = {"role": "particle_material", "status": "skipped_ideal_mode"}
    elif solver.force_tmatrix or abs(solver.eps) > 0:
        material_support["particle_material"] = validate_material_support(
            solver.particle_material,
            lambda_nm,
            strict_material_range=solver.strict_material_range,
            role="particle_material",
        )
        spectrum = tmatrix_backscatter_spectrum(solver.diameter_nm, solver.eps, solver.beta_deg, solver.particle_material, solver.medium_material, lambda_nm, amp_component=solver.amp_component, library_path=solver.library_path)
        tmatrix_used = True
    else:
        material_support["particle_material"] = validate_material_support(
            solver.particle_material,
            lambda_nm,
            strict_material_range=solver.strict_material_range,
            role="particle_material",
        )
        spectrum = mie_backscatter_spectrum(solver.diameter_nm, solver.particle_material, solver.medium_material, lambda_nm)
        tmatrix_used = False
    axial_spectral_field = source_power[:, None] * spectrum[:, None]
    axial_field = spectral_cube_to_xz(lambda_nm, axial_spectral_field, opd_um, solver.medium_material)[0, :]
    raw_axial_envelope = np.abs(axial_field)
    raw_axial_intensity = raw_axial_envelope ** 2
    lateral_intensity = gaussian_lateral_intensity(x_um, source.lambda0_nm, grid.na)
    lateral_envelope = normalize_intensity(np.sqrt(lateral_intensity))
    sample_arm_spectral_cube = axial_spectral_field * lateral_envelope[None, :]
    raw_envelope_xz = lateral_envelope[:, None] * raw_axial_envelope[None, :]
    raw_intensity_xz = lateral_intensity[:, None] * raw_axial_intensity[None, :]
    envelope_xz, envelope_xz_scale = normalize_intensity(raw_envelope_xz, return_scale=True)
    intensity_xz, intensity_xz_scale = normalize_intensity(raw_intensity_xz, return_scale=True)
    axial_views = build_full_na_axial_views(x_um, opd_um, raw_intensity_xz, raw_envelope_xz)
    return {
        "mode": LOW_NA_BASELINE_MODE,
        "display_mode_label": LOW_NA_DISPLAY_LABEL,
        "lateral_slice_axis": str(getattr(solver, "lateral_slice_axis", "x")).strip().lower(),
        "x_um": x_um,
        "opd_um": opd_um,
        "lambda_nm": lambda_nm,
        "sample_arm_spectral_cube": sample_arm_spectral_cube,
        "axial_field": axial_field,
        "raw_envelope_xz": raw_envelope_xz,
        "raw_intensity_xz": raw_intensity_xz,
        "envelope_xz": envelope_xz,
        "intensity_xz": intensity_xz,
        "centerline_raw_axial_envelope": axial_views["centerline_raw_axial_envelope"],
        "centerline_raw_axial_intensity": axial_views["centerline_raw_axial_intensity"],
        "peakline_raw_axial_envelope": axial_views["peakline_raw_axial_envelope"],
        "peakline_raw_axial_intensity": axial_views["peakline_raw_axial_intensity"],
        "centerline_axial_envelope": axial_views["centerline_axial_envelope"],
        "centerline_axial_intensity": axial_views["centerline_axial_intensity"],
        "peakline_axial_envelope": axial_views["peakline_axial_envelope"],
        "peakline_axial_intensity": axial_views["peakline_axial_intensity"],
        "centerline_axial_intensity_metrics": axial_views["centerline_axial_intensity_metrics"],
        "centerline_axial_envelope_metrics": axial_views["centerline_axial_envelope_metrics"],
        "peakline_axial_intensity_metrics": axial_views["peakline_axial_intensity_metrics"],
        "peakline_axial_envelope_metrics": axial_views["peakline_axial_envelope_metrics"],
        "axial_intensity_metrics": axial_views["peakline_axial_intensity_metrics"],
        "axial_envelope_metrics": axial_views["peakline_axial_envelope_metrics"],
        "global_peak_index": axial_views["global_peak_index"],
        "raw_peak_intensity": axial_views["raw_peak_intensity"],
        "raw_peak_envelope": axial_views["raw_peak_envelope"],
        "centerline_x_index": axial_views["centerline_x_index"],
        "centerline_x_um": axial_views["centerline_x_um"],
        "peakline_x_index": axial_views["peakline_x_index"],
        "peakline_x_um": axial_views["peakline_x_um"],
        "primary_axial_metrics_line": axial_views["primary_axial_metrics_line"],
        "primary_axial_metrics_note": "low_na baseline remains symmetric in typical cases, but primary axial metrics follow the explicit peakline schema used across round6 solvers.",
        "normalization": {
            **build_normalization_metadata(
                normalized_fields=[
                    "envelope_xz",
                    "intensity_xz",
                    "centerline_axial_envelope",
                    "centerline_axial_intensity",
                    "peakline_axial_envelope",
                    "peakline_axial_intensity",
                ],
                raw_fields=[
                    "axial_field",
                    "raw_envelope_xz",
                    "raw_intensity_xz",
                    "centerline_raw_axial_envelope",
                    "centerline_raw_axial_intensity",
                    "peakline_raw_axial_envelope",
                    "peakline_raw_axial_intensity",
                ],
                normalization_scope="per-array peak normalization",
                absolute_amplitude_supported=False,
            ),
            "scales": {
                "envelope_xz_peak": float(envelope_xz_scale),
                "intensity_xz_peak": float(intensity_xz_scale),
                "centerline_axial_envelope_peak": float(np.max(axial_views["centerline_raw_axial_envelope"])),
                "centerline_axial_intensity_peak": float(np.max(axial_views["centerline_raw_axial_intensity"])),
                "peakline_axial_envelope_peak": float(np.max(axial_views["peakline_raw_axial_envelope"])),
                "peakline_axial_intensity_peak": float(np.max(axial_views["peakline_raw_axial_intensity"])),
            },
        },
        "tmatrix_used": tmatrix_used,
        "tmatrix_library": _TMATRIX_LIB_PATH if tmatrix_used else None,
        "lateral_response_model": "gaussian_system_surrogate",
        "particle_lateral_scattering_enters_profile": False,
        "baseline_scope_note": (
            "low_na_separable_baseline applies particle scattering only through the axial spectrum; "
            "the lateral profile is a Gaussian system surrogate and should not be interpreted as a "
            "particle-aware lateral PSF measurement baseline."
        ),
        "spectral_model_note": SPECTRAL_MODEL_NOTE,
        "depth_axis_note": OPD_AXIS_NOTE,
        "material_range_notes": {
            "particle_material": MATERIAL_RANGE_NOTES.get(str(solver.particle_material)),
            "medium_material": MATERIAL_RANGE_NOTES.get(str(solver.medium_material)),
        },
        "material_support": material_support,
        **build_base_result_metadata(
            approximation_label=LOW_NA_APPROXIMATION_LABEL,
            paper_safe=solver.strict_material_range,
        ),
    }


def solve_full_na_slice(source, grid, solver):
    lambda_nm, source_power = source_spectrum_lambda(source.lambda0_nm, source.fwhm_nm, source.n_lambda)
    x_um = np.linspace(-0.5 * grid.x_span_um, 0.5 * grid.x_span_um, grid.n_x)
    opd_um = np.linspace(-grid.z_span_um, grid.z_span_um, grid.n_z)
    material_support = {
        "medium_material": validate_material_support(solver.medium_material, lambda_nm, strict_material_range=solver.strict_material_range, role="medium_material"),
    }
    geometry = derive_na_geometry_series(lambda_nm, solver.medium_material, grid.na)
    sphere_mie_metadata = None
    sphere_mie_nmax_min = None
    sphere_mie_nmax_max = None
    sphere_mie_used = False
    tmatrix_backend_required = False
    scattering_branch = "unresolved"
    lateral_response_model = "unresolved"
    particle_lateral_scattering_enters_profile = False
    if solver.ideal:
        bundle = build_ideal_bfp_field(lambda_nm, n_bfp_dense=grid.n_bfp_dense)
        tmatrix_used = False
        scattering_branch = "ideal_uniform_pupil_reference"
        lateral_response_model = "ideal_uniform_pupil_reference"
        material_support["particle_material"] = {"role": "particle_material", "status": "skipped_ideal_mode"}
    elif should_use_sphere_mie_full_na_branch(solver):
        material_support["particle_material"] = validate_material_support(
            solver.particle_material,
            lambda_nm,
            strict_material_range=solver.strict_material_range,
            role="particle_material",
        )
        bundle = build_sphere_mie_bfp_field(
            diameter_nm=solver.diameter_nm,
            particle_index_fn=resolve_material_model(solver.particle_material),
            medium_index_fn=resolve_material_model(solver.medium_material),
            lambda_nm=lambda_nm,
            sin_theta_max=geometry["sin_theta_max"],
            n_bfp_dense=grid.n_bfp_dense,
            amp_component=solver.amp_component,
        )
        tmatrix_used = False
        sphere_mie_used = True
        tmatrix_backend_required = False
        scattering_branch = "sphere_mie_full_na"
        lateral_response_model = "sphere_mie_angle_resolved_pupil_field"
        particle_lateral_scattering_enters_profile = True
        sphere_mie_metadata = bundle.get("sphere_mie_metadata")
        sphere_mie_nmax_min = bundle.get("sphere_mie_nmax_min")
        sphere_mie_nmax_max = bundle.get("sphere_mie_nmax_max")
    else:
        material_support["particle_material"] = validate_material_support(
            solver.particle_material,
            lambda_nm,
            strict_material_range=solver.strict_material_range,
            role="particle_material",
        )
        bundle = build_particle_bfp_field(solver.diameter_nm, solver.eps, solver.beta_deg, solver.particle_material, solver.medium_material, lambda_nm, sin_theta_max=geometry["sin_theta_max"], n_bfp_dense=grid.n_bfp_dense, n_bfp_sparse=grid.n_bfp_sparse, amp_component=solver.amp_component, library_path=solver.library_path)
        tmatrix_used = True
        tmatrix_backend_required = True
        scattering_branch = "non_spherical_tmatrix_full_na"
        lateral_response_model = "tmatrix_angle_resolved_pupil_field"
        particle_lateral_scattering_enters_profile = True
    lateral_slice_axis = str(getattr(solver, "lateral_slice_axis", "x")).strip().lower()
    lateral_field = pupil_field_to_lateral_line(
        bundle,
        lambda_nm,
        x_um,
        geometry["sin_theta_max"],
        solver.medium_material,
        lateral_slice_axis=lateral_slice_axis,
    )
    sample_arm_spectral_cube = source_power[:, None] * lateral_field
    field_xz = spectral_cube_to_xz(lambda_nm, sample_arm_spectral_cube, opd_um, solver.medium_material)
    raw_envelope_xz = np.abs(field_xz)
    raw_intensity_xz = raw_envelope_xz ** 2
    envelope_xz, envelope_xz_scale = normalize_intensity(raw_envelope_xz, return_scale=True)
    intensity_xz, intensity_xz_scale = normalize_intensity(raw_intensity_xz, return_scale=True)
    axial_views = build_full_na_axial_views(x_um, opd_um, raw_intensity_xz, raw_envelope_xz)
    return {
        "mode": FULL_NA_BASELINE_MODE,
        "display_mode_label": FULL_NA_DISPLAY_LABEL,
        "lateral_slice_axis": lateral_slice_axis,
        "x_um": x_um,
        "opd_um": opd_um,
        "lambda_nm": lambda_nm,
        "sample_arm_spectral_cube": sample_arm_spectral_cube,
        "field_xz": field_xz,
        "raw_envelope_xz": raw_envelope_xz,
        "raw_intensity_xz": raw_intensity_xz,
        "envelope_xz": envelope_xz,
        "intensity_xz": intensity_xz,
        "centerline_raw_axial_envelope": axial_views["centerline_raw_axial_envelope"],
        "centerline_raw_axial_intensity": axial_views["centerline_raw_axial_intensity"],
        "peakline_raw_axial_envelope": axial_views["peakline_raw_axial_envelope"],
        "peakline_raw_axial_intensity": axial_views["peakline_raw_axial_intensity"],
        "centerline_axial_envelope": axial_views["centerline_axial_envelope"],
        "centerline_axial_intensity": axial_views["centerline_axial_intensity"],
        "peakline_axial_envelope": axial_views["peakline_axial_envelope"],
        "peakline_axial_intensity": axial_views["peakline_axial_intensity"],
        "centerline_axial_envelope_metrics": axial_views["centerline_axial_envelope_metrics"],
        "centerline_axial_intensity_metrics": axial_views["centerline_axial_intensity_metrics"],
        "peakline_axial_envelope_metrics": axial_views["peakline_axial_envelope_metrics"],
        "peakline_axial_intensity_metrics": axial_views["peakline_axial_intensity_metrics"],
        "global_peak_index": axial_views["global_peak_index"],
        "raw_peak_intensity": axial_views["raw_peak_intensity"],
        "raw_peak_envelope": axial_views["raw_peak_envelope"],
        "centerline_x_index": axial_views["centerline_x_index"],
        "centerline_x_um": axial_views["centerline_x_um"],
        "peakline_x_index": axial_views["peakline_x_index"],
        "peakline_x_um": axial_views["peakline_x_um"],
        "primary_axial_metrics_line": axial_views["primary_axial_metrics_line"],
        "primary_axial_metrics_note": axial_views["primary_axial_metrics_note"],
        "axial_intensity_metrics": axial_views["peakline_axial_intensity_metrics"],
        "axial_envelope_metrics": axial_views["peakline_axial_envelope_metrics"],
        "normalization": {
            **build_normalization_metadata(
                normalized_fields=[
                    "envelope_xz",
                    "intensity_xz",
                    "centerline_axial_envelope",
                    "centerline_axial_intensity",
                    "peakline_axial_envelope",
                    "peakline_axial_intensity",
                ],
                raw_fields=[
                    "field_xz",
                    "raw_envelope_xz",
                    "raw_intensity_xz",
                    "centerline_raw_axial_envelope",
                    "centerline_raw_axial_intensity",
                    "peakline_raw_axial_envelope",
                    "peakline_raw_axial_intensity",
                ],
                normalization_scope="per-array peak normalization",
                absolute_amplitude_supported=False,
            ),
            "scales": {
                "envelope_xz_peak": float(envelope_xz_scale),
                "intensity_xz_peak": float(intensity_xz_scale),
                "centerline_axial_envelope_peak": float(np.max(axial_views["centerline_raw_axial_envelope"])),
                "centerline_axial_intensity_peak": float(np.max(axial_views["centerline_raw_axial_intensity"])),
                "peakline_axial_envelope_peak": float(np.max(axial_views["peakline_raw_axial_envelope"])),
                "peakline_axial_intensity_peak": float(np.max(axial_views["peakline_raw_axial_intensity"])),
            },
        },
        "tmatrix_used": tmatrix_used,
        "tmatrix_library": _TMATRIX_LIB_PATH if tmatrix_used else None,
        "sphere_mie_used": sphere_mie_used,
        "tmatrix_backend_required": tmatrix_backend_required,
        "scattering_branch": scattering_branch,
        "lateral_response_model": lateral_response_model,
        "particle_lateral_scattering_enters_profile": particle_lateral_scattering_enters_profile,
        "sphere_mie_metadata": sphere_mie_metadata,
        "sphere_mie_nmax_min": sphere_mie_nmax_min,
        "sphere_mie_nmax_max": sphere_mie_nmax_max,
        "pupil_shape": list(bundle["field_cube"].shape),
        "amp_component_semantics": AMP_COMPONENT_SEMANTICS,
        "propagation_note": FULL_NA_PROPAGATION_NOTE,
        "shape_parameterization_note": SHAPE_PARAMETERIZATION_NOTE,
        "spectral_model_note": SPECTRAL_MODEL_NOTE,
        "depth_axis_note": OPD_AXIS_NOTE,
        "obliquity_model": "sqrt_cos_theta_scalar",
        "material_range_notes": {
            "particle_material": MATERIAL_RANGE_NOTES.get(str(solver.particle_material)),
            "medium_material": MATERIAL_RANGE_NOTES.get(str(solver.medium_material)),
        },
        "material_support": material_support,
        **build_base_result_metadata(
            approximation_label=FULL_NA_APPROXIMATION_LABEL,
            paper_safe=solver.strict_material_range,
        ),
    }


def solve_oct_particle_response(source=None, grid=None, solver=None):
    source = source or SourceConfig()
    grid = grid or GridConfig()
    solver = solver or SolverConfig()
    if solver.mode in {"low_na", LOW_NA_BASELINE_MODE}:
        result = solve_low_na_slice(source, grid, solver)
    elif solver.mode in {"full_na", FULL_NA_BASELINE_MODE}:
        result = solve_full_na_slice(source, grid, solver)
    elif solver.mode == VECTOR_BRIDGE_MODE:
        bridge_module = load_round6_extension("10_vector_pupil_overlap_bridge.py", "round6_vector_pupil_overlap_bridge")
        result = bridge_module.solve_vector_pupil_overlap_bridge_slice(
            source,
            grid,
            solver,
            strict_material_range=solver.strict_material_range,
        )
    elif solver.mode == LOW_NA_ASYMPTOTIC_MODE:
        asymptotic_module = load_round6_extension("11_low_na_asymptotic.py", "round6_low_na_asymptotic")
        result = asymptotic_module.solve_low_na_asymptotic_slice(
            source,
            grid,
            solver,
            strict_material_range=solver.strict_material_range,
        )
    else:
        raise ValueError(f"Unsupported mode: {solver.mode}")
    result["source"] = asdict(source)
    result["grid"] = asdict(grid)
    result["solver"] = asdict(solver)
    reference_medium = resolve_material_model(solver.medium_material)(source.lambda0_nm / 1000.0)
    result["reference_n_medium"] = float(np.real(reference_medium))
    result["na_convention"] = "external na is sample-side NA = n_medium * sin(theta_max); internal geometry uses sin_theta_max = na / n_medium"
    result["derived_geometry_center"] = derive_na_geometry(grid.na, reference_medium)
    result["derived_geometry_series"] = serialize_geometry_series(derive_na_geometry_series(result["lambda_nm"], solver.medium_material, grid.na))
    result["depth_convention_helper"] = build_depth_convention_helper(result["opd_um"], reference_medium)
    result["single_pass_depth_from_reference_n_um"] = result["opd_um"] * result["depth_convention_helper"]["single_pass_depth_from_reference_n_scale"]
    result["double_pass_depth_from_reference_n_um"] = result["opd_um"] * result["depth_convention_helper"]["double_pass_depth_from_reference_n_scale"]
    result["derived_geometry"] = result["derived_geometry_center"]
    result["paper_safe"] = bool(result.get("paper_safe", solver.strict_material_range))
    result["schema_version"] = result.get("schema_version", SCHEMA_VERSION)
    return result


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Non-spherical OCT low-NA / full-NA approximation solver.")
    parser.add_argument(
        "--mode",
        default="low_na",
        choices=[
            "low_na",
            LOW_NA_BASELINE_MODE,
            LOW_NA_ASYMPTOTIC_MODE,
            "full_na",
            FULL_NA_BASELINE_MODE,
            VECTOR_BRIDGE_MODE,
        ],
    )
    parser.add_argument("--ideal", action="store_true")
    parser.add_argument("--force-tmatrix", action="store_true")
    parser.add_argument("--particle-material", default="TiO2-anatase")
    parser.add_argument("--medium-material", default="PDMS")
    parser.add_argument("--diameter-nm", type=float, default=200.0)
    parser.add_argument("--eps", type=float, default=0.0)
    parser.add_argument("--beta-deg", type=float, default=0.0)
    parser.add_argument("--amp-component", default="S22", choices=list(PUBLIC_AMP_COMPONENTS), help="Public fixed-basis scattering channel for the full_na approximation. Advanced matrix elements remain available only through the programmatic API.")
    parser.add_argument("--incident-mode", default="linear_x", choices=list(PUBLIC_JONES_MODES))
    parser.add_argument("--detection-mode", default="co_pol", choices=list(PUBLIC_JONES_MODES))
    parser.add_argument("--lambda0-nm", type=float, default=855.0)
    parser.add_argument("--fwhm-nm", type=float, default=56.0)
    parser.add_argument("--n-lambda", type=int, default=201)
    parser.add_argument("--z-span-um", type=float, default=40.0)
    parser.add_argument("--n-z", type=int, default=2001)
    parser.add_argument("--x-span-um", type=float, default=8.0)
    parser.add_argument("--n-x", type=int, default=129)
    parser.add_argument("--na", type=float, default=0.05, help="Sample-side numerical aperture NA = n_medium * sin(theta_max).")
    parser.add_argument("--n-bfp-dense", type=int, default=129)
    parser.add_argument("--n-bfp-sparse", type=int, default=11)
    parser.add_argument("--strict-material-range", action="store_true", help="Require every non-constant material model used in a run to have an explicit encoded wavelength support range.")
    parser.add_argument(
        "--second-order-model",
        default="tensor_closure",
        choices=["tensor_closure", "slice_projected", "directional_field_expansion", "directional_field_expansion_first_order"],
        help="Second-order asymptotic correction model. Only used by low_na_asymptotic.",
    )
    parser.add_argument(
        "--mu2-wavelength-model",
        default="frozen_at_lambda0",
        choices=["frozen_at_lambda0", "endpoint_refit"],
        help="Reference-pupil wavelength model used by low_na_asymptotic. endpoint_refit is a cheap band-edge refit experiment, not a full x,k closure.",
    )
    parser.add_argument(
        "--lateral-shift-model",
        default="none",
        choices=["none", "first_order"],
        help="Experimental lateral-shift augmentation for low_na_asymptotic. first_order estimates a wavelength-dependent envelope shift from the fitted slice-directed linear effective-channel term.",
    )
    parser.add_argument(
        "--lateral-shift-coupling",
        default="envelope_only",
        choices=["envelope_only", "shift_envelope_and_mu2"],
        help="How the experimental lateral shift couples into low_na_asymptotic. shift_envelope_and_mu2 also shifts the x-dependent second-order correction.",
    )
    parser.add_argument(
        "--lateral-shift-impl",
        default="interp",
        choices=["interp", "interp_edge_hold", "analytic_gaussian"],
        help="Implementation used for shifting the shared lateral envelope in experimental lateral-shift runs.",
    )
    parser.add_argument("--lib-path")
    parser.add_argument(
        "--tmatrix-backend",
        default="auto",
        choices=list(TMATRIX_BACKEND_IDS),
        help="Select the T-matrix backend contract to probe before solving.",
    )
    parser.add_argument(
        "--tmatrix-lib-path",
        help="Alias for --lib-path used by the backend registry/provenance contract.",
    )
    parser.add_argument(
        "--require-tmatrix-backend",
        action="store_true",
        help="Fail before solving when the requested T-matrix backend is unavailable.",
    )
    parser.add_argument(
        "--backend-provenance-out",
        help="Write T-matrix backend provenance to this JSON path.",
    )
    parser.add_argument(
        "--coefficient-map-model-id",
        default="identity_slice_projected_rendered_basis",
        choices=list(COEFFICIENT_MAP_MODEL_IDS),
        help=(
            "Projected-to-rendered coefficient map model used by low_na_asymptotic. "
            "Non-identity runtime maps require --coefficient-map-artifact-path."
        ),
    )
    parser.add_argument(
        "--coefficient-map-runtime-mode",
        default="native_branch_assembly",
        choices=list(COEFFICIENT_MAP_RUNTIME_MODES),
        help=(
            "How low_na_asymptotic applies the coefficient-map stage. "
            "'native_branch_assembly' keeps each asymptotic branch's native field assembly; "
            "'rendered_basis_override' forces the canonical rendered R0/R1/R2 basis assembly as an explicit runtime contract."
        ),
    )
    parser.add_argument(
        "--coefficient-map-artifact-path",
        help=(
            "Validated shared coefficient-map candidate artifact used to promote a non-identity runtime map into the "
            "low_na_asymptotic solver path."
        ),
    )
    parser.add_argument(
        "--rendered-basis-shift-target",
        default="baseline_envelope_ratio",
        choices=list(RENDERED_BASIS_SHIFT_TARGETS),
        help=(
            "When coefficient_map_runtime_mode='rendered_basis_override' and a first-order lateral shift is active, "
            "choose whether to shift by applying a baseline-envelope ratio or by directly shifting the rendered field."
        ),
    )
    parser.add_argument("--output-json")
    parser.add_argument("--output-npz")
    return parser


def main():
    args = build_arg_parser().parse_args()
    effective_lib_path = args.tmatrix_lib_path or args.lib_path
    backend_provenance = build_backend_provenance(args.tmatrix_backend, library_path=effective_lib_path)
    backend_provenance_path = None
    if args.backend_provenance_out:
        backend_provenance_path = write_backend_provenance(args.backend_provenance_out, backend_provenance)
    try:
        if args.require_tmatrix_backend or args.tmatrix_backend != "auto":
            require_backend_available(backend_provenance)
    except RuntimeError as error:
        failure_payload = {
            "error": "tmatrix_backend_unavailable",
            "mode": args.mode,
            "reason": str(error),
            "tmatrix_backend_provenance": backend_provenance,
            "backend_provenance_path": str(backend_provenance_path) if backend_provenance_path else None,
            "runtime_root": str(resolve_runtime_root(__file__)),
            "reports_dir": str(resolve_reports_dir(__file__)),
        }
        payload = json.dumps(failure_payload, indent=2)
        if args.output_json:
            Path(args.output_json).write_text(payload + "\n", encoding="utf-8")
        else:
            sys.stderr.write(payload + "\n")
        raise SystemExit(2)
    try:
        result = solve_oct_particle_response(
            SourceConfig(
                lambda0_nm=args.lambda0_nm,
                fwhm_nm=args.fwhm_nm,
                n_lambda=args.n_lambda,
            ),
            GridConfig(
                z_span_um=args.z_span_um,
                n_z=args.n_z,
                x_span_um=args.x_span_um,
                n_x=args.n_x,
                na=args.na,
                n_bfp_dense=args.n_bfp_dense,
                n_bfp_sparse=args.n_bfp_sparse,
            ),
            SolverConfig(
                mode=args.mode,
                particle_material=args.particle_material,
                medium_material=args.medium_material,
                diameter_nm=args.diameter_nm,
                eps=args.eps,
                beta_deg=args.beta_deg,
                amp_component=args.amp_component,
                ideal=args.ideal,
                force_tmatrix=args.force_tmatrix,
                library_path=effective_lib_path,
                tmatrix_backend=args.tmatrix_backend,
                strict_material_range=args.strict_material_range,
                incident_mode=args.incident_mode,
                detection_mode=args.detection_mode,
                second_order_model=args.second_order_model,
                mu2_wavelength_model=args.mu2_wavelength_model,
                lateral_shift_model=args.lateral_shift_model,
                lateral_shift_coupling=args.lateral_shift_coupling,
                lateral_shift_impl=args.lateral_shift_impl,
                coefficient_map_model_id=args.coefficient_map_model_id,
                coefficient_map_runtime_mode=args.coefficient_map_runtime_mode,
                coefficient_map_artifact_path=args.coefficient_map_artifact_path,
                rendered_basis_shift_target=args.rendered_basis_shift_target,
            ),
        )
    except FileNotFoundError as error:
        if "Unable to load libpytmatrix" not in str(error):
            raise
        failure_payload = {
            "error": "tmatrix_backend_unavailable",
            "mode": args.mode,
            "reason": str(error),
            "tmatrix_backend_status": probe_tmatrix_backend(effective_lib_path),
            "tmatrix_backend_provenance": backend_provenance,
            "backend_provenance_path": str(backend_provenance_path) if backend_provenance_path else None,
            "runtime_root": str(resolve_runtime_root(__file__)),
            "reports_dir": str(resolve_reports_dir(__file__)),
        }
        payload = json.dumps(failure_payload, indent=2)
        if args.output_json:
            Path(args.output_json).write_text(payload + "\n", encoding="utf-8")
        else:
            sys.stderr.write(payload + "\n")
        raise SystemExit(2)
    if args.output_npz:
        npz_payload = {
            "x_um": result["x_um"],
            "opd_um": result["opd_um"],
            "single_pass_depth_from_reference_n_um": result["single_pass_depth_from_reference_n_um"],
            "double_pass_depth_from_reference_n_um": result["double_pass_depth_from_reference_n_um"],
            "lambda_nm": result["lambda_nm"],
            "envelope_xz": result["envelope_xz"],
            "intensity_xz": result["intensity_xz"],
        }
        for key in [
            "raw_envelope_xz",
            "raw_intensity_xz",
            "centerline_axial_envelope",
            "centerline_axial_intensity",
            "centerline_raw_axial_envelope",
            "centerline_raw_axial_intensity",
            "peakline_axial_envelope",
            "peakline_axial_intensity",
            "peakline_raw_axial_envelope",
            "peakline_raw_axial_intensity",
        ]:
            if key in result:
                npz_payload[key] = result[key]
        np.savez_compressed(args.output_npz, **npz_payload)
    summary = {
        "mode": result["mode"],
        "display_mode_label": result.get("display_mode_label"),
        "solver_output_kind": result.get("solver_output_kind"),
        "lateral_slice_axis": result.get("lateral_slice_axis"),
        "axial_axis_kind": result.get("axial_axis_kind"),
        "axial_intensity_metrics": result.get("axial_intensity_metrics"),
        "axial_envelope_metrics": result.get("axial_envelope_metrics"),
        "schema_version": result.get("schema_version"),
        "paper_safe": result.get("paper_safe"),
        "tmatrix_used": result["tmatrix_used"],
        "tmatrix_library": result["tmatrix_library"],
        "sphere_mie_used": result.get("sphere_mie_used"),
        "tmatrix_backend_required": result.get("tmatrix_backend_required"),
        "scattering_branch": result.get("scattering_branch"),
        "lateral_response_model": result.get("lateral_response_model"),
        "particle_lateral_scattering_enters_profile": result.get("particle_lateral_scattering_enters_profile"),
        "sphere_mie_metadata": result.get("sphere_mie_metadata"),
        "sphere_mie_nmax_min": result.get("sphere_mie_nmax_min"),
        "sphere_mie_nmax_max": result.get("sphere_mie_nmax_max"),
        "tmatrix_backend_requested_id": args.tmatrix_backend,
        "tmatrix_backend_available": backend_provenance.get("backend_available"),
        "tmatrix_backend_id": backend_provenance.get("backend_id"),
        "tmatrix_backend_library_path": backend_provenance.get("library_path"),
        "tmatrix_backend_reason": backend_provenance.get("reason"),
        "tmatrix_backend_provenance": backend_provenance,
        "backend_provenance_path": str(backend_provenance_path) if backend_provenance_path else None,
        "na_convention": result["na_convention"],
        "derived_geometry_center": result["derived_geometry_center"],
        "derived_geometry_series": result["derived_geometry_series"],
        "approximation_label": result.get("approximation_label"),
        "amp_component_semantics": result.get("amp_component_semantics"),
        "propagation_note": result.get("propagation_note"),
        "shape_parameterization_note": result.get("shape_parameterization_note"),
        "spectral_model_note": result.get("spectral_model_note"),
        "depth_axis_note": result.get("depth_axis_note"),
        "depth_convention_helper": result.get("depth_convention_helper"),
        "depth_axis_status": result.get("depth_convention_helper", {}).get("depth_axis_status"),
        "single_pass_depth_from_reference_n_um": result.get("single_pass_depth_from_reference_n_um"),
        "double_pass_depth_from_reference_n_um": result.get("double_pass_depth_from_reference_n_um"),
        "obliquity_model": result.get("obliquity_model"),
        "channel_projection_kind": result.get("channel_projection_kind"),
        "channel_definition": result.get("channel_definition"),
        "channel_alignment_note": result.get("channel_alignment_note"),
        "incident_mode": result.get("incident_mode"),
        "detection_mode": result.get("detection_mode"),
        "supported_polarization_modes": result.get("supported_polarization_modes"),
        "polarization_model_kind": result.get("polarization_model_kind"),
        "polarization_projection_level": result.get("polarization_projection_level"),
        "projection_semantics_note": result.get("projection_semantics_note"),
        "requested_second_order_model": result.get("requested_second_order_model"),
        "second_order_model": result.get("second_order_model"),
        "runtime_field_assembly_contract": result.get("runtime_field_assembly_contract"),
        "runtime_field_assembly_contract_note": result.get("runtime_field_assembly_contract_note"),
        "runtime_field_assembly_supported_lateral_shift_models": result.get(
            "runtime_field_assembly_supported_lateral_shift_models"
        ),
        "runtime_field_assembly_lateral_shift_constraint": result.get(
            "runtime_field_assembly_lateral_shift_constraint"
        ),
        "runtime_field_assembly_shift_target": result.get("runtime_field_assembly_shift_target"),
        "runtime_field_assembly_shift_target_note": result.get("runtime_field_assembly_shift_target_note"),
        "coefficient_map_model_id": result.get("coefficient_map_model_id"),
        "coefficient_map_runtime_mode": result.get("coefficient_map_runtime_mode"),
        "coefficient_map_runtime_status": result.get("coefficient_map_runtime_status"),
        "coefficient_map_runtime_contract_status": result.get("coefficient_map_runtime_contract_status"),
        "coefficient_map_artifact_path": result.get("coefficient_map_artifact_path"),
        "rendered_basis_shift_target": result.get("rendered_basis_shift_target"),
        "coefficient_map_note": result.get("coefficient_map_note"),
        "coefficient_map_matrix_condition_number": result.get("coefficient_map_matrix_condition_number"),
        "coefficient_map_matrix_rank": result.get("coefficient_map_matrix_rank"),
        "na_scalar_validity_status": result.get("na_scalar_validity_status"),
        "na_scalar_validity_note": result.get("na_scalar_validity_note"),
        "requires_vector_diffraction": result.get("requires_vector_diffraction"),
        "na_scalar_validity_threshold": result.get("na_scalar_validity_threshold"),
        "lateral_shift_model": result.get("lateral_shift_model"),
        "lateral_shift_model_note": result.get("lateral_shift_model_note"),
        "lateral_shift_delta_x_k_um": result.get("lateral_shift_delta_x_k_um"),
        "lateral_shift_delta_summary": result.get("lateral_shift_delta_summary"),
        "lateral_shift_coupling": result.get("lateral_shift_coupling"),
        "lateral_shift_coupling_note": result.get("lateral_shift_coupling_note"),
        "lateral_shift_impl": result.get("lateral_shift_impl"),
        "lateral_shift_impl_note": result.get("lateral_shift_impl_note"),
        "mu2_wavelength_model": result.get("mu2_wavelength_model"),
        "mu2_wavelength_model_note": result.get("mu2_wavelength_model_note"),
        "mu2_wavelength_samples_nm": result.get("mu2_wavelength_samples_nm"),
        "c2_estimation_method": result.get("c2_estimation_method"),
        "C2_tensor_kind": result.get("C2_tensor_kind"),
        "C2_tensor_basis": result.get("C2_tensor_basis"),
        "C2_scalar_weighting_kind": result.get("C2_scalar_weighting_kind"),
        "C2_slice_projection_note": result.get("C2_slice_projection_note"),
        "C2_azimuth_variation_note": result.get("C2_azimuth_variation_note"),
        "C2_azimuth_variation_summary": result.get("C2_azimuth_variation_summary"),
        "mu2_profile_kind": result.get("mu2_profile_kind"),
        "mu2_profile_semantics_note": result.get("mu2_profile_semantics_note"),
        "mu2_profile_complexity_note": result.get("mu2_profile_complexity_note"),
        "mu2_reference_wavelength_nm": result.get("mu2_reference_wavelength_nm"),
        "mu2_wavelength_model": result.get("mu2_wavelength_model"),
        "mu2_dispersion_sensitivity": result.get("mu2_dispersion_sensitivity"),
        "mu2_spatial_model": result.get("mu2_spatial_model"),
        "mu2_spatial_model_note": result.get("mu2_spatial_model_note"),
        "second_order_closure_note": result.get("second_order_closure_note"),
        "C2_scalar_validity_indicator": result.get("C2_scalar_validity_indicator"),
        "material_range_notes": result.get("material_range_notes"),
        "material_support": result.get("material_support"),
        "normalization": result.get("normalization"),
        "source": result["source"],
        "grid": result["grid"],
        "solver": result["solver"],
    }
    if "primary_axial_metrics_line" in result:
        summary["primary_axial_metrics_line"] = result["primary_axial_metrics_line"]
        summary["primary_axial_metrics_note"] = result["primary_axial_metrics_note"]
        summary["centerline_x_um"] = result["centerline_x_um"]
        summary["peakline_x_um"] = result["peakline_x_um"]
        summary["centerline_axial_intensity_metrics"] = result["centerline_axial_intensity_metrics"]
        summary["centerline_axial_envelope_metrics"] = result["centerline_axial_envelope_metrics"]
        summary["peakline_axial_intensity_metrics"] = result["peakline_axial_intensity_metrics"]
        summary["peakline_axial_envelope_metrics"] = result["peakline_axial_envelope_metrics"]
        summary["global_peak_index"] = result["global_peak_index"]
    if "raw_peak_intensity" in result:
        summary["raw_peak_intensity"] = float(result["raw_peak_intensity"])
    if "pupil_shape" in result:
        summary["pupil_shape"] = result["pupil_shape"]
    if "C2_abs_std_over_azimuth" in result:
        summary["C2_abs_std_over_azimuth_mean"] = float(np.mean(np.asarray(result["C2_abs_std_over_azimuth"], dtype=float)))
        summary["C2_abs_std_over_azimuth_max"] = float(np.max(np.asarray(result["C2_abs_std_over_azimuth"], dtype=float)))
    if "C2_tensor_k" in result:
        tensor = np.asarray(result["C2_tensor_k"])
        summary["C2_tensor_abs_max"] = float(np.max(np.abs(tensor)))
    if "C2_slice_k" in result:
        summary["C2_slice_abs_max"] = float(np.max(np.abs(np.asarray(result["C2_slice_k"]))))
    if "mu2_profile_phase_span_rad" in result:
        summary["mu2_profile_phase_span_rad"] = float(result["mu2_profile_phase_span_rad"])
    if "mu2_profile_real_imag_ratio" in result:
        summary["mu2_profile_real_imag_ratio"] = float(result["mu2_profile_real_imag_ratio"])
    payload = json.dumps(to_json_compatible(summary), indent=2)
    if args.output_json:
        Path(args.output_json).write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
