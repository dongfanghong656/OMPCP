import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "local_pdf_to_zotero.py"
SPEC = importlib.util.spec_from_file_location("local_pdf_to_zotero", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class LocalPdfToZoteroTests(unittest.TestCase):
    def test_build_candidate_uses_aliases_and_path_defaults(self):
        input_pdf = MODULE.InputPdf(
            path=ROOT / "tmp" / "incoming" / "psf" / "paper.pdf",
            root=ROOT / "tmp" / "incoming",
        )
        override = {
            "english_title": "Resolved OCT Paper",
            "author_string": "Alice Example; Bob Example",
            "published_year": "2024",
            "doi": "10.1234/example.paper",
            "journal_name": "Biomedical Optics Express",
            "volume": "12",
            "issue": "3",
            "pages": "101-110",
            "platform": "xmol",
            "relevance_note": "Useful for PSF validation.",
        }
        settings = {
            "root_collection": "Local PDF Imports",
            "path_collection_depth": 2,
            "tag_from_path": True,
            "path_tag_prefix": "folder:",
            "default_tags": ["local-pdf-import"],
            "classification_rules": [],
        }
        with mock.patch.object(MODULE, "read_pdf_probe", return_value=({}, [""])):
            candidate = MODULE.build_candidate(input_pdf, override, {}, settings, 3)

        self.assertEqual(candidate.title, "Resolved OCT Paper")
        self.assertEqual(candidate.authors, ["Alice Example", "Bob Example"])
        self.assertEqual(candidate.year, "2024")
        self.assertEqual(candidate.doi, "10.1234/example.paper")
        self.assertEqual(candidate.venue, "Biomedical Optics Express")
        self.assertEqual(candidate.volume, "12")
        self.assertEqual(candidate.issue, "3")
        self.assertEqual(candidate.pages, "101-110")
        self.assertEqual(candidate.source, "xmol")
        self.assertIn("local-pdf-import", candidate.tags)
        self.assertIn("folder:psf", candidate.tags)
        self.assertIn("Local PDF Imports/psf", candidate.collection_paths)
        self.assertEqual(candidate.verification_status, "verified_doi")

    def test_apply_classification_rules_adds_tags_and_collections(self):
        candidate = MODULE.LocalPdfImportCandidate(
            pdf_path="C:/tmp/paper.pdf",
            relative_path="psf/review/paper.pdf",
            title="Point spread function phantom for OCT",
            abstract="A phantom-based point spread function validation paper.",
        )
        MODULE.apply_classification_rules(
            candidate,
            [
                {
                    "name": "psf-rule",
                    "match_any": ["point spread function", "psf"],
                    "tags": ["psf", "phantom"],
                    "collections": ["OCT/PSF"],
                }
            ],
        )

        self.assertIn("psf", candidate.tags)
        self.assertIn("phantom", candidate.tags)
        self.assertIn("OCT/PSF", candidate.collection_paths)
        self.assertIn("psf-rule", candidate.classification_reasons)

    def test_mark_existing_items_detects_existing_attachment_by_hash(self):
        pdf_path = ROOT / "tmp" / "existing-paper.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"dummy pdf bytes")
        file_hash = MODULE.compute_md5(pdf_path)

        existing = MODULE.ExistingItem(
            item_id=101,
            item_key="ABCD1234",
            title="Example Paper",
            doi="10.1234/example.paper",
            attachment_hashes={file_hash},
        )
        index = MODULE.ZoteroLocalIndex(
            doi_to_item={"10.1234/example.paper": existing},
            title_to_item={},
        )
        candidate = MODULE.LocalPdfImportCandidate(
            pdf_path=str(pdf_path),
            file_name=pdf_path.name,
            title="Example Paper",
            doi="10.1234/example.paper",
        )

        MODULE.mark_existing_items([candidate], index)

        self.assertTrue(candidate.already_in_zotero)
        self.assertEqual(candidate.zotero_parent_key, "ABCD1234")
        self.assertTrue(candidate.attachment_exists)
        self.assertTrue(candidate.attachment_complete)
        self.assertEqual(candidate.attachment_match_reason, "md5")

    def test_build_parent_payload_merges_default_tags_and_collections(self):
        candidate = MODULE.LocalPdfImportCandidate(
            pdf_path="C:/tmp/paper.pdf",
            relative_path="paper.pdf",
            title="Example Paper",
            authors=["Alice Example"],
            year="2025",
            doi="10.1234/example.paper",
            venue="Optics Letters",
            tags=["local-pdf-import", "psf"],
            collection_keys=["COLL1234"],
            verification_status="verified_doi",
            verification_source="local_pdf_doi",
        )
        payload = MODULE.build_parent_payload(
            candidate,
            {
                "zotero": {
                    "default_tags": ["oct-research-assist"],
                    "scope_collection": "SCOPE999",
                }
            },
        )

        self.assertEqual(payload["itemType"], "journalArticle")
        self.assertEqual(payload["DOI"], "10.1234/example.paper")
        self.assertEqual(payload["publicationTitle"], "Optics Letters")
        self.assertEqual(payload["collections"], ["SCOPE999", "COLL1234"])
        self.assertEqual(
            [tag["tag"] for tag in payload["tags"]],
            ["oct-research-assist", "local-pdf-import", "psf"],
        )

    def test_apply_authoritative_openalex_metadata_replaces_bad_title(self):
        candidate = MODULE.LocalPdfImportCandidate(
            pdf_path="C:/tmp/paper.pdf",
            relative_path="paper.pdf",
            title="License: bad extracted text",
            doi="10.1234/example.paper",
            verification_status="verified_doi",
        )
        authoritative = MODULE.discovery.Candidate(
            title="Correct Paper Title",
            authors=["Alice Example"],
            venue="Biomedical Optics Express",
            verification_source="openalex",
            openalex_id="https://openalex.org/W123",
        )
        with mock.patch.object(MODULE.discovery, "openalex_lookup_by_doi", return_value={"id": "fake"}), mock.patch.object(
            MODULE.discovery, "openalex_work_to_candidate", return_value=authoritative
        ):
            MODULE.apply_authoritative_openalex_metadata(candidate, "")

        self.assertEqual(candidate.title, "Correct Paper Title")
        self.assertEqual(candidate.authors, ["Alice Example"])
        self.assertEqual(candidate.venue, "Biomedical Optics Express")
        self.assertEqual(candidate.openalex_id, "https://openalex.org/W123")

    def test_refresh_remote_attachment_status_reuses_incomplete_pdf_child(self):
        candidate = MODULE.LocalPdfImportCandidate(
            pdf_path="C:/tmp/paper.pdf",
            relative_path="paper.pdf",
            zotero_parent_key="PARENT123",
        )
        with mock.patch.object(
            MODULE,
            "http_json",
            return_value=(
                [
                    {
                        "data": {
                            "key": "ATTACH123",
                            "contentType": "application/pdf",
                            "filename": "other-name.pdf",
                            "md5": None,
                            "mtime": None,
                        }
                    }
                ],
                {},
            ),
        ):
            MODULE.refresh_remote_attachment_status(candidate, {"zotero": {"api_key": "x", "library_id": "1", "library_type": "user"}})

        self.assertFalse(candidate.attachment_complete)
        self.assertEqual(candidate.attachment_item_key, "ATTACH123")
        self.assertEqual(candidate.attachment_match_reason, "remote-incomplete")

    def test_load_paper_note_overrides_uses_existing_vault_note_metadata(self):
        vault_root = ROOT / "tmp" / "paper-note-override-vault"
        note_dir = vault_root / "02_Literature" / "Papers"
        note_dir.mkdir(parents=True, exist_ok=True)
        note_path = note_dir / "[1998] Szydlo - Air-turbine driven optical low-coherence reflectometry.md"
        note_path.write_text(
            "\n".join(
                [
                    "---",
                    'title: "Air-turbine driven optical low-coherence reflectometry"',
                    "authors:",
                    '  - "J. Szydlo"',
                    '  - "N. Delachenal"',
                    "year: 1998",
                    'doi: ""',
                    'source_pdf: "C:/vault/08_Attachments/papers/1998-air-turbine-driven-optical-low-coherence-reflectometry.pdf"',
                    "---",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        overrides = MODULE.load_paper_note_overrides(
            {
                "vault_root": str(vault_root),
                "obsidian": {"paper_folder": "02_Papers"},
            }
        )

        override = overrides["c:/vault/08_attachments/papers/1998-air-turbine-driven-optical-low-coherence-reflectometry.pdf"]
        candidate = MODULE.LocalPdfImportCandidate(
            pdf_path="C:/vault/08_Attachments/papers/1998-air-turbine-driven-optical-low-coherence-reflectometry.pdf",
            title="PACS: 42.81.Pa",
        )
        MODULE.apply_paper_note_override(candidate, override)

        self.assertEqual(candidate.title, "Air-turbine driven optical low-coherence reflectometry")
        self.assertEqual(candidate.authors, ["J. Szydlo", "N. Delachenal"])
        self.assertEqual(candidate.year, "1998")

    def test_apply_known_zotero_key_override_marks_existing(self):
        candidate = MODULE.LocalPdfImportCandidate(pdf_path="C:/vault/paper.pdf")

        MODULE.apply_known_zotero_key_override(candidate, {"zotero_parent_key": "CS8S7KV2"})

        self.assertTrue(candidate.already_in_zotero)
        self.assertEqual(candidate.zotero_parent_key, "CS8S7KV2")
        self.assertEqual(candidate.zotero_match_reason, "override-key")


if __name__ == "__main__":
    unittest.main()
