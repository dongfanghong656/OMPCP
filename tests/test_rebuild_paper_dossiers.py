import importlib.util
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "paper_dossiers.py"
SPEC = importlib.util.spec_from_file_location("paper_dossiers", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_note(root: Path, rel_path: str, text: str) -> Path:
    path = root / Path(rel_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class RebuildPaperDossiersTests(unittest.TestCase):
    def test_frontmatter_payload_merges_bom_prefixed_duplicate_blocks(self):
        text = (
            "---\n"
            "venue: Example Journal\n"
            "authors:\n"
            "  - Alice\n"
            "  - Bob\n"
            "---\n"
            "\ufeff---\n"
            'title: "Merged Note"\n'
            "authors:\n"
            "  - Alice\n"
            'year: "2024"\n'
            "---\n\n"
            "# Body\n"
        )

        frontmatter, body = MODULE.split_frontmatter(text)

        self.assertEqual(frontmatter["title"], "Merged Note")
        self.assertEqual(frontmatter["venue"], "Example Journal")
        self.assertEqual(frontmatter["year"], "2024")
        self.assertEqual(frontmatter["authors"], ["Alice", "Bob"])
        self.assertTrue(body.lstrip().startswith("# Body"))

    def test_generate_bundle_builds_paper_dossier_and_root_index(self):
        test_root = ROOT / "tmp" / f"test-rebuild-paper-dossiers-{uuid.uuid4().hex}"
        try:
            vault_root = test_root / "vault"
            output_root = test_root / "output"

            legacy_note = write_note(
                vault_root,
                "02_Papers/example-paper-analysis.md",
                "# Example Legacy Analysis\n",
            )
            extract_note = write_note(
                vault_root,
                "08_Attachments/extracted/example-paper/pypdf-extract.md",
                "# Extract\n",
            )
            copied_pdf = write_note(
                vault_root,
                "08_Attachments/papers/example-paper.pdf",
                "pdf\n",
            )
            write_note(
                vault_root,
                "06_Writing/translated-papers/example-paper-translation.md",
                "\n".join(
                    [
                        "---",
                        'title: "Example Paper"',
                        f'source_paper_note: "{legacy_note}"',
                        f'source_pdf: "{copied_pdf}"',
                        "---",
                        "",
                        "# Example Translation",
                        "",
                    ]
                ),
            )
            write_note(
                vault_root,
                "12_Zotero/04_Item-Backfills/[2024] ABC123 - Example Paper.md",
                "\n".join(
                    [
                        "---",
                        'type: "zotero-item"',
                        'title: "Example Paper"',
                        'zotero_key: "ABC123"',
                        'year: "2024"',
                        'doi: "10.1000/example"',
                        "---",
                        "",
                        "# Example Paper",
                        "",
                    ]
                ),
            )
            paper_note = write_note(
                vault_root,
                "02_Literature/Papers/[2024] Example - Example Paper.md",
                "\n".join(
                    [
                        "---",
                        'type: "paper"',
                        'title: "Example Paper"',
                        'title_display: "Example Paper"',
                        "year: 2024",
                        'doi: "10.1000/example"',
                        'zotero_key: "ABC123"',
                        'status: "annotated"',
                        'reading_stage: "synthesis"',
                        'source_tag: "test-source"',
                        "authors:",
                        "  - Jane Example",
                        "tags:",
                        "  - oct-paper",
                        f'extract_path: "{extract_note}"',
                        f'copied_pdf: "{copied_pdf}"',
                        'translated_note_path: ""',
                        f'legacy_source_note: "[[{legacy_note.relative_to(vault_root).as_posix()}]]"',
                        "---",
                        "",
                        "# Example Paper",
                        "",
                    ]
                ),
            )
            write_note(
                vault_root,
                "02_Literature/Papers/[2024] Example - Example Paper Duplicate.md",
                "\n".join(
                    [
                        "---",
                        'type: "paper"',
                        'title: "Example Paper"',
                        'title_display: "Example Paper"',
                        "year: 2024",
                        'doi: "10.1000/example"',
                        'zotero_key: "ABC123"',
                        'status: "to-read"',
                        'source_tag: "test-source"',
                        "---",
                        "",
                        "# Example Paper Duplicate",
                        "",
                    ]
                ),
            )
            write_note(
                vault_root,
                "02_Literature/Papers/[2024] Example - Synthetic.md",
                "\n".join(
                    [
                        "---",
                        'type: "paper"',
                        'title: "Synthetic Example Paper"',
                        'year: "2024"',
                        'doi: "10.0000/example-doi"',
                        'url: "https://example.org/paper"',
                        'venue: "Journal of Optical Imaging Methods"',
                        'library_status: "synthetic-example"',
                        "---",
                        "",
                        "# Synthetic Example Paper",
                        "",
                    ]
                ),
            )

            config = {
                "vault_root": str(vault_root),
                "obsidian": {
                    "paper_folder": "02_Papers",
                    "zotero_folder": "12_Zotero",
                    "attachment_folder": "08_Attachments",
                    "writing_folder": "06_Writing",
                },
                "translation": {"render": {"translated_folder_name": "translated-papers"}},
            }

            run_dir = MODULE.generate_bundle(vault_root, output_root, "test-paper-dossiers", config)

            dossier_index = (
                run_dir
                / "bundle"
                / "02_Literature"
                / "Paper-Dossiers"
                / paper_note.stem
                / "_Index.md"
            )
            self.assertTrue(dossier_index.exists())
            dossier_text = dossier_index.read_text(encoding="utf-8")
            self.assertIn("[[02_Literature/Papers/[2024] Example - Example Paper|主笔记]]", dossier_text)
            self.assertIn("[[12_Zotero/04_Item-Backfills/[2024] ABC123 - Example Paper|Zotero 回填]]", dossier_text)
            self.assertIn("[[02_Papers/example-paper-analysis|精炼解析]]", dossier_text)
            self.assertIn("[[06_Writing/translated-papers/example-paper-translation|中文翻译]]", dossier_text)
            self.assertIn("[[08_Attachments/extracted/example-paper/pypdf-extract|原文提取]]", dossier_text)
            self.assertIn("[[08_Attachments/papers/example-paper.pdf|PDF]]", dossier_text)
            self.assertIn("[[02_Literature/Papers/[2024] Example - Example Paper Duplicate]]", dossier_text)

            root_index = run_dir / "bundle" / "02_Literature" / "Paper-Dossiers" / "_Index.md"
            self.assertTrue(root_index.exists())
            root_text = root_index.read_text(encoding="utf-8")
            self.assertIn("论文档案索引", root_text)
            self.assertIn("Zotero", root_text)
            self.assertIn("翻译", root_text)
            self.assertIn(f"[[02_Literature/Paper-Dossiers/{paper_note.stem}/_Index|Example Paper]]", root_text)
            self.assertNotIn("Example Paper Duplicate/_Index", root_text)
            self.assertNotIn("Synthetic Example Paper", root_text)
        finally:
            if test_root.exists():
                for path in sorted(test_root.rglob("*"), reverse=True):
                    if path.is_file():
                        path.unlink()
                    else:
                        path.rmdir()


if __name__ == "__main__":
    unittest.main()
