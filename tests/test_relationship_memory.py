import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
RELATIONSHIP_SCRIPT = SCRIPTS / "relationship_memory.py"
CONVERSATION_SCRIPT = SCRIPTS / "append_conversation_note.py"
DIGEST_SCRIPT = SCRIPTS / "daily_digest.py"


class RelationshipMemoryCliTests(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tmp" / "test-runs"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.config_path = self.workspace / "config.json"
        config = {
            "profile_path": str(self.workspace / "profile.json").replace("\\", "/"),
            "vault_root": str(self.vault_root).replace("\\", "/"),
            "output_root": str(self.output_root).replace("\\", "/"),
            "obsidian": {
                "daily_folder": "01_Daily",
                "paper_folder": "02_Papers",
                "concept_folder": "03_Concepts",
                "progress_folder": "04_Progress",
                "experiment_folder": "05_Experiments",
                "writing_folder": "06_Writing",
                "profile_folder": "07_Profiles",
                "attachment_folder": "08_Attachments",
                "conversation_folder": "09_Conversations",
                "task_folder": "10_Tasks",
                "retrieval_folder": "11_Retrieval",
                "zotero_folder": "12_Zotero",
                "people_folder": "13_People",
                "relationship_folder": "14_Relationships",
            },
        }
        self.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def run_cli(self, script: Path, *args: str) -> str:
        completed = subprocess.run(
            [sys.executable, str(script), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    def write_payload(self, payload: dict) -> Path:
        payload_path = self.workspace / "payload.json"
        payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload_path

    def test_bootstrap_upsert_and_query(self):
        self.run_cli(RELATIONSHIP_SCRIPT, "bootstrap", "--config", str(self.config_path))
        payload_path = self.write_payload(
            {
                "people": [
                    {
                        "name": "王老师",
                        "aliases": ["导师"],
                        "relationship_to_user": "advisor",
                        "relationship_stage": "active",
                        "summary": "Direct supervisor who wants stronger evidence before writing.",
                        "traits": ["严谨"],
                        "preferences": ["先补实验再写作"],
                        "notes": ["近期更看重实验闭环"],
                        "confidence": "high",
                    },
                    {
                        "name": "李敏",
                        "aliases": ["小李"],
                        "relationship_to_user": "friend",
                        "relationship_stage": "active",
                        "summary": "Friend dealing with a stressful job transition.",
                        "topics": ["求职"],
                        "confidence": "medium",
                    },
                ],
                "events": [
                    {
                        "date": "2026-03-20",
                        "title": "王老师要求先补实验",
                        "people": ["王老师"],
                        "type": "request",
                        "summary": "导师强调本周先补关键实验。",
                        "follow_up": "整理实验缺口并汇报。",
                        "confidence": "high",
                    },
                    {
                        "date": "2026-03-20",
                        "title": "李敏提到换工作压力很大",
                        "people": ["李敏"],
                        "type": "life-update",
                        "summary": "她最近因为换工作很疲惫。",
                        "follow_up": "下周主动问候一次。",
                        "confidence": "medium",
                    },
                ],
            }
        )

        self.run_cli(
            RELATIONSHIP_SCRIPT,
            "upsert",
            "--config",
            str(self.config_path),
            "--payload",
            str(payload_path),
            "--source-note",
            "2026-03-20-demo-note",
        )

        people_registry = json.loads(
            (self.vault_root / "13_People" / "_registry.json").read_text(encoding="utf-8")
        )
        relationship_registry = json.loads(
            (self.vault_root / "14_Relationships" / "_registry.json").read_text(encoding="utf-8")
        )

        self.assertEqual(len(people_registry["people"]), 2)
        self.assertEqual(len(relationship_registry["events"]), 2)
        self.assertTrue((self.vault_root / "13_People" / "_Index.md").exists())
        self.assertTrue((self.vault_root / "14_Relationships" / "_Index.md").exists())

        query_output = self.run_cli(
            RELATIONSHIP_SCRIPT,
            "query",
            "--config",
            str(self.config_path),
            "--person",
            "导师",
        )
        self.assertIn("王老师", query_output)
        self.assertIn("先补实验", query_output)

        keyword_output = self.run_cli(
            RELATIONSHIP_SCRIPT,
            "query",
            "--config",
            str(self.config_path),
            "--keyword",
            "求职",
        )
        self.assertIn("李敏", keyword_output)

    def test_append_conversation_note_can_sync_relationship_memory(self):
        payload_path = self.write_payload(
            {
                "people": [
                    {
                        "name": "陈哲",
                        "aliases": ["阿哲"],
                        "relationship_to_user": "classmate",
                        "relationship_stage": "active",
                        "summary": "Classmate who is considering a new collaboration.",
                        "topics": ["合作", "实验"],
                        "confidence": "medium",
                    }
                ],
                "events": [
                    {
                        "date": "2026-03-20",
                        "title": "陈哲提出想一起补实验",
                        "people": ["陈哲"],
                        "type": "collaboration",
                        "summary": "他希望下周一起做一轮补实验。",
                        "follow_up": "确认时间并整理实验清单。",
                        "confidence": "medium",
                    }
                ],
            }
        )

        conversation_path = Path(
            self.run_cli(
                CONVERSATION_SCRIPT,
                "--config",
                str(self.config_path),
                "--title",
                "Relationship memory sync",
                "--summary",
                "Captured a new collaboration update about 陈哲.",
                "--memory-payload",
                str(payload_path),
            )
        )

        self.assertTrue(conversation_path.exists())
        query_output = self.run_cli(
            RELATIONSHIP_SCRIPT,
            "query",
            "--config",
            str(self.config_path),
            "--person",
            "阿哲",
        )
        self.assertIn("陈哲", query_output)
        self.assertIn("补实验", query_output)

        digest_path = Path(
            self.run_cli(DIGEST_SCRIPT, "--config", str(self.config_path), "--lookback-days", "3")
        )
        digest_text = digest_path.read_text(encoding="utf-8")
        self.assertIn("People Notes", digest_text)
        self.assertIn("Relationship Event Notes", digest_text)


if __name__ == "__main__":
    unittest.main()
