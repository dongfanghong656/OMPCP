import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "discovery_to_zotero.py"
SPEC = importlib.util.spec_from_file_location("discovery_to_zotero", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class DiscoveryToZoteroTests(unittest.TestCase):
    def test_load_candidates_from_json_supports_defaults_and_results_alias(self):
        json_path = ROOT / "tmp" / "test-discovery-defaults.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            """
{
  "schema_version": "2026-03-24.discovery-leads.v1",
  "defaults": {
    "source": "google_scholar",
    "query": "oct deconvolution psf"
  },
  "results": [
    {
      "english_title": "Example OCT Paper",
      "author_string": "Alice Example; Bob Example",
      "published_year": "2024",
      "publisher_url": "https://doi.org/10.1234/example.paper",
      "journal_name": "Biomedical Optics Express",
      "cited_by": "17",
      "selection_reason": "Seed paper from scholar."
    }
  ]
}
""".strip(),
            encoding="utf-8",
        )

        candidates = MODULE.load_candidates_from_json(json_path, "manual")
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.title, "Example OCT Paper")
        self.assertEqual(candidate.authors, ["Alice Example", "Bob Example"])
        self.assertEqual(candidate.year, "2024")
        self.assertEqual(candidate.doi, "10.1234/example.paper")
        self.assertEqual(candidate.venue, "Biomedical Optics Express")
        self.assertEqual(candidate.discovery_sources, ["google_scholar"])
        self.assertEqual(candidate.discovery_queries, ["oct deconvolution psf"])
        self.assertEqual(candidate.cited_by_count, 17)
        self.assertIn("Seed paper from scholar.", candidate.notes)

    def test_normalize_lead_record_extracts_doi_from_url(self):
        candidate = MODULE.normalize_lead_record(
            {
                "title": "Example OCT Paper",
                "url": "https://doi.org/10.1234/example.paper",
            },
            "google_scholar",
            "oct query",
            ROOT / "references" / "leads.json",
        )

        self.assertEqual(candidate.doi, "10.1234/example.paper")
        self.assertEqual(candidate.verification_status, "verified_doi")
        self.assertEqual(candidate.verification_source, "lead_doi")

    def test_normalize_lead_record_supports_source_specific_aliases(self):
        candidate = MODULE.normalize_lead_record(
            {
                "platform": "xmol",
                "english_title": "Resolved OCT Paper Title",
                "author_names": "Alice Example | Bob Example",
                "pub_year": "2019",
                "doi_url": "https://doi.org/10.2000/alias.paper",
                "journal_title": "Optics Letters",
                "content_type": "article",
                "lang": "en",
                "snippet": "Short result summary from the discovery source.",
            },
            "manual",
            "oct alias query",
            ROOT / "references" / "leads.json",
        )

        self.assertEqual(candidate.discovery_sources, ["xmol"])
        self.assertEqual(candidate.title, "Resolved OCT Paper Title")
        self.assertEqual(candidate.authors, ["Alice Example", "Bob Example"])
        self.assertEqual(candidate.year, "2019")
        self.assertEqual(candidate.doi, "10.2000/alias.paper")
        self.assertEqual(candidate.venue, "Optics Letters")
        self.assertEqual(candidate.publication_type, "article")
        self.assertEqual(candidate.language, "en")
        self.assertEqual(candidate.abstract, "Short result summary from the discovery source.")

    def test_parse_ris_file_extracts_expected_fields(self):
        ris_path = ROOT / "tmp" / "test-discovery.ris"
        ris_path.parent.mkdir(parents=True, exist_ok=True)
        ris_path.write_text(
            "\n".join(
                [
                    "TY  - JOUR",
                    "TI  - Example OCT Paper",
                    "AU  - Alice Example",
                    "AU  - Bob Example",
                    "PY  - 2025",
                    "DO  - 10.1234/example",
                    "UR  - https://example.org/paper",
                    "ER  -",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        records = MODULE.parse_ris_file(ris_path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "Example OCT Paper")
        self.assertEqual(records[0]["authors"], ["Alice Example", "Bob Example"])
        self.assertEqual(records[0]["doi"], "10.1234/example")

    def test_deduplicate_candidates_prefers_combined_provenance(self):
        first = MODULE.Candidate(
            title="Example OCT Paper",
            doi="10.1234/example",
            discovery_sources=["consensus"],
            discovery_queries=["query a"],
        )
        second = MODULE.Candidate(
            title="Example OCT Paper",
            doi="10.1234/example",
            discovery_sources=["xmol"],
            discovery_queries=["query b"],
        )

        deduped = MODULE.deduplicate_candidates([first, second])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(set(deduped[0].discovery_sources), {"consensus", "xmol"})
        self.assertEqual(set(deduped[0].discovery_queries), {"query a", "query b"})

    def test_mark_existing_zotero_items_uses_doi_and_title(self):
        candidates = [
            MODULE.Candidate(title="Example OCT Paper", doi="10.1234/example"),
            MODULE.Candidate(title="Other Paper", doi=""),
        ]
        index = MODULE.ZoteroIndex(
            doi_to_item={"10.1234/example": 101},
            title_to_item={MODULE.canonicalize_title("Other Paper"): 202},
        )

        MODULE.mark_existing_zotero_items(candidates, index)
        self.assertTrue(candidates[0].already_in_zotero)
        self.assertEqual(candidates[0].zotero_item_id, 101)
        self.assertEqual(candidates[0].zotero_match_reason, "doi")
        self.assertTrue(candidates[1].already_in_zotero)
        self.assertEqual(candidates[1].zotero_item_id, 202)
        self.assertEqual(candidates[1].zotero_match_reason, "title")

    def test_openalex_work_to_candidate_normalizes_issue_and_pages(self):
        candidate = MODULE.openalex_work_to_candidate(
            {
                "display_name": "Spatially adaptive blind deconvolution methods for optical coherence tomography",
                "authorships": [],
                "publication_year": 2022,
                "doi": "https://doi.org/10.1016/j.compbiomed.2022.105650",
                "primary_location": {
                    "landing_page_url": "https://example.org/paper",
                    "source": {"display_name": "Computers in Biology and Medicine"},
                },
                "type_crossref": "article",
                "biblio": {
                    "volume": "147",
                    "issue": None,
                    "first_page": "105650",
                    "last_page": "105650",
                },
                "language": "en",
                "cited_by_count": 13,
                "id": "https://openalex.org/W4281758202",
            },
            "openalex",
            "oct query",
            "",
        )

        self.assertEqual(candidate.volume, "147")
        self.assertEqual(candidate.issue, "")
        self.assertEqual(candidate.pages, "105650")

    def test_render_ris_contains_discovery_and_verification_keywords(self):
        candidate = MODULE.Candidate(
            title="Example OCT Paper",
            authors=["Alice Example"],
            year="2025",
            doi="10.1234/example",
            discovery_sources=["consensus", "google_scholar"],
            verification_status="verified_doi",
        )

        ris = MODULE.render_ris([candidate])
        self.assertIn("TI  - Example OCT Paper", ris)
        self.assertIn("AU  - Alice Example", ris)
        self.assertIn("DO  - 10.1234/example", ris)
        self.assertIn("KW  - discovery:consensus", ris)
        self.assertIn("KW  - verification:verified_doi", ris)


if __name__ == "__main__":
    unittest.main()
