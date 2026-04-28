import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
TMP_ROOT = Path("C:/codex-data/.codex-test-tmp")
TMP_ROOT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(SCRIPTS_DIR))

import retrieve_recent_papers


class RetrieveRecentPapersTests(unittest.TestCase):
    def setUp(self):
        self.base = TMP_ROOT / f"retrieve-{uuid.uuid4().hex}"
        self.base.mkdir(parents=True)
        self.vault_root = self.base / "vault"
        self.retrieval_root = self.vault_root / "11_Retrieval"
        self.retrieval_root.mkdir(parents=True)
        self.profile_path = self.base / "profile.json"
        self.profile_path.write_text(
            json.dumps(
                {
                    "interests": [
                        {
                            "name": "Test Interest",
                            "keywords": ["oct", "deconvolution"],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.config_path = self.base / "config.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "profile_path": str(self.profile_path),
                    "vault_root": str(self.vault_root),
                    "retrieval": {
                        "sources": ["openalex", "arxiv"],
                        "max_results_per_interest": 3,
                        "openalex_mailto": "",
                    },
                    "obsidian": {"retrieval_folder": "11_Retrieval"},
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_network_failures_still_write_snapshot(self):
        with patch.object(retrieve_recent_papers, "query_openalex", side_effect=PermissionError("WinError 10013")), patch.object(
            retrieve_recent_papers, "query_arxiv", return_value=[]
        ), patch.object(
            sys,
            "argv",
            ["retrieve_recent_papers.py", "--config", str(self.config_path)],
        ):
            retrieve_recent_papers.main()

        md_path = self.retrieval_root / f"{retrieve_recent_papers.date.today().isoformat()}-retrieval.md"
        json_path = self.retrieval_root / f"{retrieve_recent_papers.date.today().isoformat()}-retrieval.json"
        self.assertTrue(md_path.exists())
        self.assertTrue(json_path.exists())
        self.assertIn("## Retrieval Failures", md_path.read_text(encoding="utf-8"))
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["results"]["Test Interest"], [])
        self.assertEqual(payload["failures"][0]["source"], "openalex")


if __name__ == "__main__":
    unittest.main()
