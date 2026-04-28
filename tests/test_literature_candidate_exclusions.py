import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


DISCOVER = load_module(
    "discover_additional_literature_candidates",
    SCRIPTS / "discover_additional_literature_candidates.py",
)
FILTER = load_module(
    "filter_literature_candidates",
    SCRIPTS / "filter_literature_candidates.py",
)


class LiteratureCandidateExclusionsTests(unittest.TestCase):
    def test_build_exclude_roots_adds_default_old_onedrive_root_when_present(self):
        old_root = Path(r"C:\Users\1\OneDrive - fzu.edu.cn")

        def fake_exists(self: Path) -> bool:
            return str(self) == str(old_root)

        with mock.patch.object(Path, "exists", fake_exists):
            roots = DISCOVER.build_exclude_roots([])

        self.assertIn(old_root, roots)

    def test_filter_excludes_old_onedrive_root_by_default(self):
        tokens = FILTER.build_exclude_tokens([])
        normalized = FILTER.normalize(r"C:\Users\1\OneDrive - fzu.edu.cn\专业课\新建文件夹\example.pdf")
        self.assertTrue(any(token in normalized for token in tokens))


if __name__ == "__main__":
    unittest.main()
