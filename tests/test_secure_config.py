import importlib.util
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "secure_config.py"
SPEC = importlib.util.spec_from_file_location("secure_config", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SecureConfigTests(unittest.TestCase):
    def setUp(self):
        tmp_root = REPO_ROOT / "tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.workspace = tmp_root / ("test-secure-config-" + uuid.uuid4().hex)
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / "oct-research-assist").mkdir(parents=True, exist_ok=True)
        self.config_path = self.workspace / "oct-research-assist" / "config.json"

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def write_config(self, payload):
        self.config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_migrate_config_secrets_moves_plaintext_into_local_store(self):
        self.write_config(
            {
                "zotero": {"api_key": "zotero-test-value"},
                "translation": {"openai": {"api_key": "translation-test-value"}},
                "academic_qa": {"openai": {"api_key": ""}},
                "question_radar": {"openai": {"api_key": ""}},
                "continuous_research": {"openai": {"api_key": ""}},
                "delivery": {"email": {"smtp_user": "", "smtp_pass": ""}},
            }
        )

        result = MODULE.migrate_config_secrets(self.config_path)
        raw_config = MODULE.load_raw_json(self.config_path)
        resolved = MODULE.load_json(self.config_path)
        store_path = Path(result["store_path"])
        store_payload = json.loads(store_path.read_text(encoding="utf-8"))

        self.assertEqual(raw_config["zotero"]["api_key"], MODULE.make_secure_ref("zotero.web"))
        self.assertEqual(
            raw_config["translation"]["openai"]["api_key"],
            MODULE.make_secure_ref("openai.translate"),
        )
        self.assertEqual(resolved["zotero"]["api_key"], "zotero-test-value")
        self.assertEqual(resolved["translation"]["openai"]["api_key"], "translation-test-value")
        self.assertIn("zotero.web", store_payload["secrets"])
        self.assertIn("openai.translate", store_payload["secrets"])
        self.assertNotEqual(
            store_payload["secrets"]["zotero.web"]["ciphertext"],
            "zotero-test-value",
        )

    def test_status_reports_missing_secure_refs(self):
        self.write_config(
            {
                "zotero": {"api_key": MODULE.make_secure_ref("zotero.web")},
                "translation": {"openai": {"api_key": MODULE.make_secure_ref("openai.translate")}},
                "academic_qa": {"openai": {"api_key": MODULE.make_secure_ref("openai.academic-qa")}},
                "question_radar": {"openai": {"api_key": MODULE.make_secure_ref("openai.question-radar")}},
                "continuous_research": {"openai": {"api_key": MODULE.make_secure_ref("openai.continuous-research")}},
                "delivery": {"email": {"smtp_user": MODULE.make_secure_ref("mail.smtp-user"), "smtp_pass": ""}},
            }
        )

        status = MODULE.secret_status(self.config_path)

        self.assertIn("zotero.web", status["configured_refs"])
        self.assertIn("zotero.web", status["missing_values"])
        self.assertEqual(status["inline_plaintext"], [])

    def test_set_secret_binds_config_and_resolves_value(self):
        self.write_config(
            {
                "zotero": {"api_key": ""},
                "translation": {"openai": {"api_key": ""}},
                "academic_qa": {"openai": {"api_key": ""}},
                "question_radar": {"openai": {"api_key": ""}},
                "continuous_research": {"openai": {"api_key": ""}},
                "delivery": {"email": {"smtp_user": "", "smtp_pass": ""}},
            }
        )

        MODULE.set_secret(self.config_path, "mail.smtp-auth", "smtp-secret-value")
        resolved = MODULE.load_json(self.config_path)
        raw_config = MODULE.load_raw_json(self.config_path)

        self.assertEqual(
            raw_config["delivery"]["email"]["smtp_pass"],
            MODULE.make_secure_ref("mail.smtp-auth"),
        )
        self.assertEqual(resolved["delivery"]["email"]["smtp_pass"], "smtp-secret-value")


if __name__ == "__main__":
    unittest.main()
