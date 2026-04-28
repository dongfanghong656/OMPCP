import importlib.util
import sys
import unittest
import uuid
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "repair_paper_notes.py"
SPEC = importlib.util.spec_from_file_location("repair_paper_notes", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_file(root: Path, rel_path: str, content: bytes | str) -> Path:
    path = root / Path(rel_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    body = text.split("\n---\n", 1)[0].split("\n", 1)[1]
    return yaml.safe_load(body) or {}


class RepairPaperNotesTests(unittest.TestCase):
    def test_repairs_bom_and_duplicate_frontmatter(self):
        test_root = ROOT / "tmp" / f"test-repair-paper-notes-{uuid.uuid4().hex}"
        try:
            vault_root = test_root / "vault"
            note_path = write_file(
                vault_root,
                "02_Literature/Papers/[2003] Broken.md",
                (
                    b"---\nvenue: Journal\n---\n\xef\xbb\xbf---\n"
                    b'title: "Broken Note"\n'
                    b"authors:\n- Alice\n"
                    b'source_pdf: "C:/tmp/example.pdf"\n'
                    b'copied_pdf: "C:/tmp/example.pdf"\n'
                    b'year: "2003"\n'
                    b"---\n\n# Broken Note\n"
                ),
            )
            config = {"vault_root": str(vault_root), "obsidian": {"paper_folder": "02_Papers"}}

            records = MODULE.repair_paper_notes(config, write=True)

            self.assertEqual(records[0].status, "repaired")
            data = frontmatter(note_path)
            self.assertEqual(data["title"], "Broken Note")
            self.assertEqual(data["venue"], "Journal")
            self.assertEqual(data["year"], "2003")
            self.assertEqual(data["authors"], ["Alice"])
        finally:
            if test_root.exists():
                for path in sorted(test_root.rglob("*"), reverse=True):
                    if path.is_file():
                        path.unlink()
                    else:
                        path.rmdir()

    def test_marks_synthetic_example_notes(self):
        test_root = ROOT / "tmp" / f"test-repair-paper-notes-{uuid.uuid4().hex}"
        try:
            vault_root = test_root / "vault"
            note_path = write_file(
                vault_root,
                "02_Literature/Papers/[2024] Example.md",
                "\n".join(
                    [
                        "---",
                        'title: "Example Paper"',
                        'doi: "10.0000/example-doi"',
                        'url: "https://example.org/paper"',
                        'venue: "Journal of Optical Imaging Methods"',
                        "---",
                        "",
                        "# Example Paper",
                        "",
                    ]
                ),
            )
            config = {"vault_root": str(vault_root), "obsidian": {"paper_folder": "02_Papers"}}

            records = MODULE.repair_paper_notes(config, write=True)

            self.assertEqual(records[0].status, "repaired")
            self.assertEqual(frontmatter(note_path)["library_status"], "synthetic-example")
        finally:
            if test_root.exists():
                for path in sorted(test_root.rglob("*"), reverse=True):
                    if path.is_file():
                        path.unlink()
                    else:
                        path.rmdir()


if __name__ == "__main__":
    unittest.main()
