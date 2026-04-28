import importlib.util
import json
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "build_annotated_paper_html.py"
SPEC = importlib.util.spec_from_file_location("build_annotated_paper_html", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BuildAnnotatedPaperHtmlTests(unittest.TestCase):
    def test_template_input_renders_dual_column_html(self):
        test_root = ROOT / "tmp" / f"test-build-annotated-paper-html-{uuid.uuid4().hex}"
        try:
            source_md = test_root / "extract.md"
            source_md.parent.mkdir(parents=True, exist_ok=True)
            source_md.write_text(
                "\n".join(
                    [
                        "# Beam Offset: Imaging Depth in OCT",
                        "",
                        "## Abstract",
                        "",
                        "We demonstrate a method that improves imaging depth by separating least scattered photons from noise.",
                        "",
                        "## Results",
                        "",
                        "The critical imaging depth increased from 200 um to 350 um in the phantom experiment.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            template_path = test_root / "translation-template.json"
            template_path.write_text(
                json.dumps(
                    {
                        "blocks": [
                            {"id": "title", "translation": "Beam Offset：OCT 成像深度"},
                            {"id": "b0002", "translation": "摘要"},
                            {"id": "b0003", "translation": "我们展示了一种方法，通过分离最少散射光子与噪声来改善成像深度。"},
                            {"id": "b0004", "translation": "结果"},
                            {"id": "b0005", "translation": "在体模实验中，critical imaging depth 从 200 um 提高到了 350 um。"},
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            document = MODULE.build_document_from_template(
                source_md=source_md,
                template_path=template_path,
                title="Beam Offset：OCT 成像深度",
                title_original="Beam Offset: Imaging Depth in OCT",
                course_info="测试课程",
            )
            rendered = MODULE.render_html(document)

            self.assertIn("Worksheet 答题索引", rendered)
            self.assertIn("Beam Offset：OCT 成像深度", rendered)
            self.assertIn("We demonstrate", rendered)
            self.assertIn("critical imaging depth", rendered)
            self.assertEqual(len(document.questions), 10)
            self.assertEqual(document.questions[1].title, "作者对“imaging depth”的核心主张是什么？")
            self.assertIn("作者对“imaging depth”的核心主张是什么？", rendered)
            self.assertNotIn("Q2 核心主张与中心结论", rendered)
            self.assertIn("中文对应", rendered)
        finally:
            if test_root.exists():
                for path in sorted(test_root.rglob("*"), reverse=True):
                    if path.is_file():
                        path.unlink()
                    else:
                        path.rmdir()

    def test_translated_markdown_pairs_original_callouts(self):
        test_root = ROOT / "tmp" / f"test-build-annotated-paper-paired-{uuid.uuid4().hex}"
        try:
            translated_md = test_root / "translated.md"
            translated_md.parent.mkdir(parents=True, exist_ok=True)
            translated_md.write_text(
                "\n".join(
                    [
                        "---",
                        'title: "测试论文"',
                        'paper_title_original: "Test Paper"',
                        "---",
                        "",
                        "# 测试论文",
                        "",
                        "## 引言",
                        "",
                        "本文展示了一种新的成像路径。",
                        "",
                        "> [!quote]- Original",
                        "> This paper demonstrates a new imaging route.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            document = MODULE.build_document_from_translated_markdown(
                translated_md=translated_md,
                course_info="测试课程",
            )

            paragraph_blocks = [block for block in document.blocks if block.kind == "paragraph"]
            self.assertEqual(len(paragraph_blocks), 1)
            self.assertEqual(paragraph_blocks[0].translated_text, "本文展示了一种新的成像路径。")
            self.assertEqual(paragraph_blocks[0].original_text, "This paper demonstrates a new imaging route.")
            self.assertEqual(document.title, "测试论文")
            self.assertEqual(document.title_original, "Test Paper")
        finally:
            if test_root.exists():
                for path in sorted(test_root.rglob("*"), reverse=True):
                    if path.is_file():
                        path.unlink()
                    else:
                        path.rmdir()


if __name__ == "__main__":
    unittest.main()
