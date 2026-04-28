from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_solver_module():
    module = sys.modules.get("oct_nonspherical_psf_solver")
    if module is not None:
        return module
    try:
        import oct_nonspherical_psf_solver as imported

        return imported
    except ModuleNotFoundError:
        scripts_dir = PROJECT_ROOT / "scripts"
        for candidate_path in (
            scripts_dir / "oct_nonspherical_psf_solver.py",
            scripts_dir / "01_oct_nonspherical_psf_solver.py",
            PROJECT_ROOT / "oct_nonspherical_psf_solver.py",
            PROJECT_ROOT / "01_oct_nonspherical_psf_solver.py",
        ):
            if not candidate_path.exists():
                continue
            spec = importlib.util.spec_from_file_location("oct_nonspherical_psf_solver", candidate_path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules["oct_nonspherical_psf_solver"] = module
            spec.loader.exec_module(module)
            return module
        raise


def reset_tmatrix_backend_state() -> None:
    _load_solver_module().reset_tmatrix_backend_state()


def ensure_tmatrix_loaded(library_path=None):
    return _load_solver_module().ensure_tmatrix_loaded(library_path)


def probe_tmatrix_backend(library_path=None) -> dict:
    return _load_solver_module().probe_tmatrix_backend(library_path)
