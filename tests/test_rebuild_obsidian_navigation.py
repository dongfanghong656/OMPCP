import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "rebuild_obsidian_navigation.py"
SPEC = importlib.util.spec_from_file_location("rebuild_obsidian_navigation", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def make_note(rel_path: str, title: str, frontmatter: dict[str, str] | None = None) -> MODULE.Note:
    rel = Path(rel_path).as_posix()
    parent = Path(rel).parent.as_posix()
    return MODULE.Note(
        rel_path=rel,
        title=title,
        frontmatter=frontmatter or {},
        top_folder=rel.split("/", 1)[0],
        parent_folder="" if parent == "." else parent,
        stem=Path(rel).stem,
        is_index=Path(rel).stem == "_Index",
    )


class RebuildObsidianNavigationTests(unittest.TestCase):
    def test_build_generated_files_creates_navigation_notes_attempt_conversation_progress_and_evidence_routes(self):
        notes = {
            note.rel_path: note
            for note in [
                make_note("00_Home/Home.md", "Home"),
                make_note("00_Home/Research-Dashboard.md", "Dashboard"),
                make_note("00_Home/Search-Guide.md", "Search Guide"),
                make_note("13_阅读区/00_从这里开始/阅读总览.md", "阅读总览"),
                make_note("13_阅读区/00_从这里开始/项目内容全景图.md", "项目内容全景图"),
                make_note("14_日常规范与办事/_Index.md", "日常规范索引"),
                make_note("13_阅读区/10_尝试归档与索引/尝试归档与关键词总览.md", "尝试归档与关键词总览"),
                make_note("13_阅读区/09_项目进展与管理/项目进展与决策总览.md", "项目进展与决策总览"),
                make_note("13_阅读区/09_项目进展与管理/验证与原型总览.md", "验证与原型总览"),
                make_note("13_阅读区/09_项目进展与管理/检索与文献管理总览.md", "检索与文献管理总览"),
                make_note("02_Literature/Concepts/Concept - 0.md", "Concept 0", {"type": "concept", "term": "Concept 0"}),
                make_note(
                    "02_Literature/Papers/[2024] Example Paper.md",
                    "Example Paper",
                    {"year": "2024", "source_tag": "test-source", "title": "Example Paper"},
                ),
                make_note(
                    "02_Literature/Papers/[2024] Synthetic Example.md",
                    "Synthetic Example",
                    {
                        "year": "2024",
                        "source_tag": "test-source",
                        "title": "Synthetic Example",
                        "library_status": "synthetic-example",
                    },
                ),
                make_note("02_Literature/Paper-Dossiers/_Index.md", "论文档案索引"),
                make_note("02_Literature/Paper-Dossiers/[2024] Example Paper/_Index.md", "论文档案"),
                make_note(
                    "12_Zotero/04_Item-Backfills/[2024] ABC123 - Example Paper.md",
                    "Example Paper",
                    {"year": "2024", "zotero_key": "ABC123", "title": "Example Paper"},
                ),
                make_note("05_Experiments/00_Verification-Plans/verification-plan.md", "Verification Plan"),
                make_note("05_Experiments/00_Verification-Plans/_Index.md", "验证计划索引"),
                make_note("05_Experiments/03_PSF-Measurement/_Index.md", "PSF 测量索引"),
                make_note("05_Experiments/04_Deconvolution-Baselines/_Index.md", "反卷积基线索引"),
                make_note("05_Experiments/05_No-Ground-Truth-Evaluation/_Index.md", "无真值评估索引"),
                make_note("05_Experiments/06_Statistical-Analysis/_Index.md", "统计分析索引"),
                make_note("05_Experiments/lateral-resolution-validation-matrix.md", "Lateral Resolution Validation Matrix"),
                make_note("06_Writing/03_Figures-and-Captions/figure-board.md", "Figure Board"),
                make_note("06_Writing/03_Figures-and-Captions/_Index.md", "图示与图注索引"),
                make_note("06_Writing/05_Claim-to-Evidence/_Index.md", "Claim to Evidence 索引"),
                make_note("06_Writing/translation-workbench/_Index.md", "翻译工作台索引"),
                make_note("06_Writing/translated-papers/_Index.md", "译文索引"),
                make_note("15_尝试归档与索引/00_总览/尝试归档总览.md", "尝试归档总览"),
                make_note(MODULE.ATTEMPT_VAULT_WORKFLOW_NOTES[0], "初始 vault 搭建与种子文献入库"),
                make_note(MODULE.ATTEMPT_VALIDATION_PROTOTYPE_NOTES[0], "Measured-PSF 对 Gaussian Baseline 验证页 v0.2"),
                make_note(MODULE.ATTEMPT_VALIDATION_PROTOTYPE_NOTES[1], "Measured-PSF 对 Gaussian Baseline 正式验证计划"),
                make_note(MODULE.ATTEMPT_CODEX_APP_NOTES[0], "官方 Codex App recent list 异常排查"),
                make_note(MODULE.CONVERSATION_SYSTEM_NOTES[0], "初始 vault 构建与第一批文献导入"),
                make_note(MODULE.CONVERSATION_LEARNING_NOTES[0], "OCT 理论主干与评估创新扩展"),
                make_note(MODULE.CONVERSATION_DECONV_NOTES[0], "反卷积与验证方法收敛"),
                make_note(MODULE.CONVERSATION_TOOLING_NOTES[0], "Codex 历史恢复优先级与同步规则"),
                make_note(MODULE.CONVERSATION_CAREER_NOTES[0], "OCT 就业与行业观察"),
                make_note("09_Conversations/Tri-Agent/_Index.md", "Tri-Agent 会话索引"),
                make_note("04_Progress/01_Project-Roadmap/roadmap-overview.md", "Roadmap Overview"),
                make_note("04_Progress/03_Risk-Register/risk-register.md", "Risk Register"),
                make_note("04_Progress/03_Risk-Register/controversy-and-debate-map.md", "Controversy and Debate Map"),
                make_note(
                    "04_Progress/03_Risk-Register/long-horizon-key-questions-for-oct-figure-analysis.md",
                    "Long Horizon Key Questions",
                ),
                make_note("04_Progress/04_Decision-Log/decision-log.md", "Decision Log"),
                make_note("04_Progress/05_Claim-Tracker/claim-tracker.md", "Claim Tracker"),
                make_note("04_Progress/2026-03-18-research-gap-matrix.md", "Research Gap Matrix"),
                make_note("04_Progress/three-month-manuscript-track.md", "Three-Month Manuscript Track"),
                make_note(
                    "04_Progress/oct-spectrometer-system-specific-template.md",
                    "OCT Spectrometer System-Specific Template",
                ),
                make_note(
                    "04_Progress/oct-spectrometer-system-specific-open-questions.md",
                    "OCT Spectrometer System-Specific Open Questions",
                ),
                make_note(
                    "04_Progress/oct-spectrometer-system-specific-decision-map.md",
                    "OCT Spectrometer System-Specific Decision Map",
                ),
                make_note("04_Progress/2026-03-18-vault-architecture-expansion.md", "Vault Architecture Expansion"),
                make_note(
                    "04_Progress/2026-03-18-translation-zotero-and-delivery-extension.md",
                    "Translation Zotero and Delivery Extension",
                ),
                make_note("04_Progress/2026-03-18-obsidian-bridge-and-gmail-switch.md", "Obsidian Bridge and Gmail Switch"),
                make_note("04_Progress/platform-integration-progress.md", "Platform Integration Progress"),
                make_note("04_Progress/tri-agent-control-plane-progress.md", "Tri-Agent Control Plane Progress"),
                make_note("10_Tasks/01_This-Week/this-week-focus.md", "This Week Focus"),
                make_note("10_Tasks/system-expansion-backlog.md", "System Expansion Backlog"),
                make_note("10_Tasks/Tri-Agent/_Index.md", "Tri-Agent Task Index"),
                make_note("10_Tasks/Tri-Agent/Tri-Agent Task Bus Board.md", "Tri-Agent Task Bus Board"),
                make_note("10_Tasks/Tri-Agent/Tri-Agent-Permission-Config.md", "Tri-Agent Permission Config"),
                make_note("10_Tasks/Tri-Agent/Tri-Agent-Experience-Summary-2026-04-02.md", "Tri-Agent Experience Summary"),
                make_note("10_Tasks/Tri-Agent/Antigravity-Integration-Protocol-2026-04-02.md", "Antigravity Integration Protocol"),
                make_note("10_Tasks/Tri-Agent/Antigravity-Vault-Auto-Sync-Rule.md", "Antigravity Vault Auto Sync Rule"),
                make_note("10_Tasks/Tri-Agent/Claude-Adoption-Record-2026-04-01.md", "Claude Adoption Record"),
                make_note("10_Tasks/Tri-Agent/Claude-Vault-Auto-Sync-Rule.md", "Claude Vault Auto Sync Rule"),
            ]
        }

        generated = MODULE.build_generated_files(notes)

        self.assertIn("00_Home/知识库导航中心.md", generated)
        self.assertIn("02_Literature/Concepts/_Index.md", generated)
        self.assertIn("05_Experiments/00_Verification-Plans/_Index.md", generated)
        self.assertIn("06_Writing/03_Figures-and-Captions/_Index.md", generated)
        self.assertIn(MODULE.ATTEMPT_READER_ENTRY_PATH, generated)
        self.assertIn(MODULE.ATTEMPT_THEME_NAV_PATH, generated)
        self.assertIn(MODULE.ATTEMPT_PROTOTYPE_OVERVIEW_PATH, generated)
        self.assertIn(MODULE.ATTEMPT_VAULT_PROTOTYPES_PATH, generated)
        self.assertIn(MODULE.ATTEMPT_CODEX_DIAGNOSTICS_PATH, generated)
        self.assertIn(MODULE.CONVERSATION_READER_ENTRY_PATH, generated)
        self.assertIn(MODULE.CONVERSATION_THEME_NAV_PATH, generated)
        self.assertIn(MODULE.CONVERSATION_SYSTEM_INDEX_PATH, generated)
        self.assertIn(MODULE.CONVERSATION_LEARNING_INDEX_PATH, generated)
        self.assertIn(MODULE.CONVERSATION_DECONV_INDEX_PATH, generated)
        self.assertIn(MODULE.CONVERSATION_TOOLING_INDEX_PATH, generated)
        self.assertIn(MODULE.CONVERSATION_CAREER_INDEX_PATH, generated)
        self.assertIn(MODULE.PROGRESS_READER_ENTRY_PATH, generated)
        self.assertIn(MODULE.PROGRESS_THEME_NAV_PATH, generated)
        self.assertIn(MODULE.PROGRESS_MANUSCRIPT_INDEX_PATH, generated)
        self.assertIn(MODULE.PROGRESS_SPECTROMETER_INDEX_PATH, generated)
        self.assertIn(MODULE.PROGRESS_PIPELINE_INDEX_PATH, generated)
        self.assertIn(MODULE.PROGRESS_TRI_AGENT_INDEX_PATH, generated)
        self.assertIn(MODULE.PROGRESS_EVIDENCE_NAV_PATH, generated)
        self.assertIn(MODULE.PROGRESS_EVIDENCE_READER_ENTRY_PATH, generated)
        self.assertIn(MODULE.PROGRESS_DECONV_EVIDENCE_PATH, generated)
        self.assertIn(MODULE.PROGRESS_SYSTEM_EVIDENCE_PATH, generated)
        self.assertIn(MODULE.PROGRESS_DELIVERY_EVIDENCE_PATH, generated)

        navigation_text = generated["00_Home/知识库导航中心.md"]
        self.assertIn("\u5206\u7c7b\u5e95\u5c42\u903b\u8f91", navigation_text)
        self.assertIn("\u9879\u76ee\u5185\u5bb9\u5168\u666f\u56fe", navigation_text)
        self.assertIn("\u8bba\u6587\u6863\u6848\u7d22\u5f15", navigation_text)
        self.assertIn("\u5386\u53f2\u5c1d\u8bd5\u4e3b\u9898\u5165\u53e3", navigation_text)
        self.assertIn("\u9ad8\u4ef7\u503c\u4f1a\u8bdd\u5165\u53e3", navigation_text)
        self.assertIn("\u7814\u7a76\u4e3b\u7ebf\u5165\u53e3", navigation_text)
        self.assertIn("\u7814\u7a76\u95ee\u9898\u8bc1\u636e\u5165\u53e3", navigation_text)

        papers_index = generated["02_Literature/Papers/_Index.md"]
        self.assertIn("[[02_Literature/Papers/[2024] Example Paper|Example Paper]]", papers_index)
        self.assertNotIn("Synthetic Example", papers_index)
        self.assertIn("\u6587\u732e\u8bba\u6587\u7d22\u5f15", papers_index)

        zotero_index = generated["12_Zotero/04_Item-Backfills/_Index.md"]
        self.assertIn("ABC123", zotero_index)
        self.assertIn("Zotero \u56de\u586b\u7d22\u5f15", zotero_index)

        prototype_index = generated["15_尝试归档与索引/02_工具与原型尝试/_Index.md"]
        self.assertIn("\u539f\u578b\u8def\u7ebf\u603b\u89c8", prototype_index)
        self.assertIn("Codex App \u7ebf\u7a0b\u6392\u67e5\u7d22\u5f15", prototype_index)

        conversations_index = generated["09_Conversations/_Index.md"]
        self.assertIn("\u9ad8\u4ef7\u503c\u4f1a\u8bdd\u4e3b\u9898\u5bfc\u822a", conversations_index)
        self.assertIn("\u7814\u7a76\u7cfb\u7edf\u4e0e\u77e5\u8bc6\u5e93\u6f14\u8fdb\u4f1a\u8bdd\u7d22\u5f15", conversations_index)

        conversation_nav = generated[MODULE.CONVERSATION_THEME_NAV_PATH]
        self.assertIn("\u53cd\u5377\u79ef\u4e0e\u9a8c\u8bc1\u4f1a\u8bdd\u7d22\u5f15", conversation_nav)
        self.assertIn("Tri-Agent", conversation_nav)

        conversation_reader = generated[MODULE.CONVERSATION_READER_ENTRY_PATH]
        self.assertIn("\u53cd\u5377\u79ef\u4e0e\u9a8c\u8bc1\u4f1a\u8bdd\u7d22\u5f15", conversation_reader)

        progress_nav = generated[MODULE.PROGRESS_THEME_NAV_PATH]
        self.assertIn("\u53cd\u5377\u79ef\u9a8c\u8bc1\u4e0e\u7a3f\u4ef6\u4e3b\u7ebf\u7d22\u5f15", progress_nav)
        self.assertIn("Tri-Agent", progress_nav)
        self.assertIn("\u7814\u7a76\u95ee\u9898\u8bc1\u636e\u5165\u53e3", progress_nav)

        progress_reader = generated[MODULE.PROGRESS_READER_ENTRY_PATH]
        self.assertIn("\u9ad8\u4ef7\u503c\u4f1a\u8bdd\u4e3b\u9898\u5bfc\u822a", progress_reader)
        self.assertIn("Zotero", progress_reader)
        self.assertIn("\u7814\u7a76\u95ee\u9898\u8bc1\u636e\u94fe\u5bfc\u822a", progress_reader)

        evidence_nav = generated[MODULE.PROGRESS_EVIDENCE_NAV_PATH]
        self.assertIn("\u53cd\u5377\u79ef\u771f\u5b9e\u589e\u76ca\u8bc1\u636e\u94fe", evidence_nav)
        self.assertIn("\u77e5\u8bc6\u5e93\u6301\u7eed\u4ea4\u4ed8\u8bc1\u636e\u94fe", evidence_nav)

        evidence_reader = generated[MODULE.PROGRESS_EVIDENCE_READER_ENTRY_PATH]
        self.assertIn("\u7814\u7a76\u95ee\u9898\u8bc1\u636e\u94fe\u5bfc\u822a", evidence_reader)
        self.assertIn("\u7814\u7a76\u4e3b\u7ebf\u5165\u53e3", evidence_reader)

        deconv_evidence = generated[MODULE.PROGRESS_DECONV_EVIDENCE_PATH]
        self.assertIn("\u5b9e\u9a8c\u4e0e\u9a8c\u8bc1", deconv_evidence)
        self.assertIn("\u53cd\u5377\u79ef\u4e0e\u9a8c\u8bc1\u4f1a\u8bdd\u7d22\u5f15", deconv_evidence)

        progress_index = generated["04_Progress/_Index.md"]
        self.assertIn("\u7814\u7a76\u63a8\u8fdb\u4e3b\u7ebf\u5bfc\u822a", progress_index)
        self.assertIn("\u5149\u8c31\u4eea", progress_index)
        self.assertIn("\u7814\u7a76\u95ee\u9898\u8bc1\u636e\u94fe\u5bfc\u822a", progress_index)

        tasks_index = generated["10_Tasks/_Index.md"]
        self.assertIn("This Week Focus", tasks_index)
        self.assertIn("Tri-Agent", tasks_index)

        reader_progress_index = generated["13_阅读区/09_项目进展与管理/_Index.md"]
        self.assertIn("\u7814\u7a76\u4e3b\u7ebf\u5165\u53e3", reader_progress_index)
        self.assertIn("\u7814\u7a76\u95ee\u9898\u8bc1\u636e\u5165\u53e3", reader_progress_index)
        self.assertIn("\u68c0\u7d22\u4e0e\u6587\u732e\u7ba1\u7406\u603b\u89c8", reader_progress_index)

    def test_wikilink_strips_markdown_suffix(self):
        self.assertEqual(
            MODULE.wikilink("02_Papers/example-note.md", "Example"),
            "[[02_Papers/example-note|Example]]",
        )


if __name__ == "__main__":
    unittest.main()
