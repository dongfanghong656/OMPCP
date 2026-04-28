from __future__ import annotations

from pathlib import Path
from textwrap import dedent
import re


VAULT_ROOT = Path(
    r"C:\Users\1\OneDrive - fzu.edu.cn (1)\Attachments\OCT_Research_System\oct-research-assist\vault"
)


QUESTION_NOTES: dict[str, str] = {
    "Question - Lateral Resolution Gain Limits.md": dedent(
        """\
        ---
        type: research-question
        question: "横向分辨率增强在多大程度上能通过反卷积稳定实现？"
        related_papers:
          - "[[2024] Chen - Adaptive OCT Deconvolution]"
          - "[[2022] Dong - Spatially adaptive blind deconvolution methods for]"
          - "[[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography]"
        related_concepts:
          - "[[Concept - Point Spread Function]]"
          - "artifact control"
          - "task-based evaluation"
        status: open
        importance: high
        tags:
          - research-question
          - deconvolution
          - lateral-resolution
        cssclasses:
          - research-question-note
        ---

        # 问题定义

        我真正关心的不是“图像看起来是否更锐”，而是反卷积是否真的恢复了可分辨信息，并且这种收益在不同样本、不同深度和不同系统条件下能否稳定成立。

        # 为什么重要

        这会直接决定我的研究路线是继续深挖反卷积增强，还是转向更强的系统级补偿与成像链路优化。

        # 谁回答过

        - [[2024] Chen - Adaptive OCT Deconvolution]]
        - [[2022] Dong - Spatially adaptive blind deconvolution methods for]]
        - [[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography]]

        # 文献之间的分歧

        - 有些工作把视觉清晰度提升当成成功
        - 有些工作要求同时证明 artifact 受控、结构真实性保留和定量指标改善
        - 评估标准是否足够接近真实任务，仍然是争议中心

        # 目前我的判断

        反卷积确实能带来一部分有效恢复，但稳定上限往往由 PSF 失配、噪声放大和验证标准不足共同决定。真正可信的结论必须超越“更清楚”的主观印象。

        # 还缺什么证据

        - 更严格的 task-based evaluation
        - blind reader 或下游任务表现
        - 跨系统、跨深度、跨样本的重复性验证
        """
    ),
    "Question - Local PSF Transferability.md": dedent(
        """\
        ---
        type: research-question
        question: "局部 PSF 估计与自适应反卷积方案能否迁移到我的横向分辨率增强课题？"
        related_papers:
          - "[[2024] Chen - Adaptive OCT Deconvolution]"
          - "[[2022] Dong - Spatially adaptive blind deconvolution methods for]"
        related_concepts:
          - "[[Concept - Point Spread Function]]"
          - "local PSF"
          - "blind deconvolution"
        status: pending
        importance: high
        tags:
          - research-question
          - psf
          - transferability
        cssclasses:
          - research-question-note
        ---

        # 问题定义

        我关心的不是“局部 PSF”这个词本身，而是它背后的方法路线是否能迁移到我自己的横向分辨率增强课题，并在真实系统条件下保留可解释性。

        # 为什么重要

        如果这条路线能迁移，我的研究可以建立在局部建模与自适应正则化上；如果不能，就需要优先解决成像系统校准和 forward model 的可靠性。

        # 谁回答过

        - [[2024] Chen - Adaptive OCT Deconvolution]]
        - [[2022] Dong - Spatially adaptive blind deconvolution methods for]]

        # 文献之间的分歧

        - 一类工作强调局部 PSF 可以明显减少全局固定核的失真
        - 另一类担心局部估计本身会放大不稳定性和参数敏感性

        # 目前我的判断

        这条思路有迁移价值，但前提是我的系统能够给出足够可信的局部 PSF 先验，或者至少能稳定估计局部模糊核的变化趋势。

        # 还缺什么证据

        - 本地系统的局部 PSF 是否可估
        - 参数对不同深度和不同组织区域的敏感性
        - 与固定核方案相比的真实增益
        """
    ),
    "Question - Deconvolution Bottlenecks in OCT.md": dedent(
        """\
        ---
        type: research-question
        question: "OCT 反卷积路线当前最硬的瓶颈究竟是什么？"
        related_papers:
          - "[[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography]"
          - "[[2022] Dong - Spatially adaptive blind deconvolution methods for]"
          - "[[2024] Chen - Adaptive OCT Deconvolution]"
        related_concepts:
          - "[[Concept - Point Spread Function]]"
          - "noise amplification"
          - "artifact control"
        status: open
        importance: high
        tags:
          - research-question
          - review
          - bottleneck
        cssclasses:
          - research-question-note
        ---

        # 问题定义

        我想厘清的不是“反卷积有没有用”，而是它在 OCT 里到底卡在哪里，以及这些瓶颈里哪些是暂时工程问题，哪些已经接近方法上限。

        # 为什么重要

        只有先看清瓶颈分布，才知道下一步应该投在核估计、正则化、评价标准还是系统级补偿。

        # 谁回答过

        - [[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography]]
        - [[2022] Dong - Spatially adaptive blind deconvolution methods for]]
        - [[2024] Chen - Adaptive OCT Deconvolution]]

        # 文献之间的分歧

        - 有的工作把问题归因于 PSF 不准确
        - 有的工作把重点放在噪声放大与 artifact
        - 还有工作指出真正缺的是可信验证而不是更复杂算法

        # 目前我的判断

        当前最硬的瓶颈并不是单一算法，而是“模型失配 + 噪声放大 + 验证不足”三件事叠加。只补其中一个环节，很难得到稳定可信的收益。

        # 还缺什么证据

        - 更系统的 benchmark
        - 不同模糊场景下的统一比较
        - 与系统级补偿方法的成本收益对照
        """
    ),
    "Question - Blind Deconvolution Stability in OCT.md": dedent(
        """\
        ---
        type: research-question
        question: "空间自适应盲反卷积是否足够稳定，可作为 OCT 分辨率增强主线方法？"
        related_papers:
          - "[[2022] Dong - Spatially adaptive blind deconvolution methods for]"
          - "[[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography]"
        related_concepts:
          - "blind deconvolution"
          - "[[Concept - Point Spread Function]]"
          - "regularization"
        status: open
        importance: high
        tags:
          - research-question
          - blind-deconvolution
          - stability
        cssclasses:
          - research-question-note
        ---

        # 问题定义

        这里的核心不是 blind deconvolution 能不能算出来，而是它在 OCT 场景里是否足够稳定、可解释，并能承受真实数据中的漂移、噪声和局部差异。

        # 为什么重要

        如果这条路线稳定，它会是横向分辨率增强的重要主线；如果不稳定，就更适合作为局部实验工具，而不是长期系统方案。

        # 谁回答过

        - [[2022] Dong - Spatially adaptive blind deconvolution methods for]]
        - [[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography]]

        # 文献之间的分歧

        - 一类工作强调局部自适应盲反卷积比固定核更贴近真实成像
        - 另一类工作担心辨识不适定性和参数初始化会让结果过度依赖设定

        # 目前我的判断

        它是非常值得跟进的方法方向，但目前更像“有前景的研究主线”而不是“已经证明足够稳定的成熟工具”。

        # 还缺什么证据

        - 对初始化与正则化的敏感性分析
        - 更复杂样本上的鲁棒性
        - 与非盲或半盲方案的系统比较
        """
    ),
    "Question - Resolution Uniformity as Baseline.md": dedent(
        """\
        ---
        type: research-question
        question: "系统分辨率与均匀性波动会不会抵消后续算法增强收益？"
        related_papers:
          - "[[2014] Unknown - Variations in optical coherence tomography resolution]"
          - "[[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography]"
        related_concepts:
          - "resolution uniformity"
          - "[[Concept - Point Spread Function]]"
          - "system baseline"
        status: open
        importance: medium
        tags:
          - research-question
          - baseline
          - evaluation
        cssclasses:
          - research-question-note
        ---

        # 问题定义

        如果不同系统、不同视场和不同深度的分辨率本身就波动明显，那么后续算法得到的“增强”很可能只是特定条件下的局部收益，而不是真正稳健的方法优势。

        # 为什么重要

        这会影响我如何设计实验基线，以及我是否应该把更多精力放在系统校准和一致性控制上。

        # 谁回答过

        - [[2014] Unknown - Variations in optical coherence tomography resolution]]
        - [[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography]]

        # 文献之间的分歧

        - 有些工作默认系统基线已经足够稳定
        - 但多系统比较显示，分辨率和均匀性并没有那么理想一致

        # 目前我的判断

        这不是外围问题，而是算法评价的前置条件。如果基线不稳，很多算法收益都可能被高估。

        # 还缺什么证据

        - 与算法增强实验同条件的 baseline 测量
        - 深度、视场和系统漂移共同作用下的误差预算
        - 算法收益与系统偏差的分离分析
        """
    ),
    "Question - Artifact-Free Superresolution Criteria.md": dedent(
        """\
        ---
        type: research-question
        question: "所谓“无伪影超分辨”需要满足哪些证据标准？"
        related_papers:
          - "[[2022] Unknown - Superresolving artifact-free optical coherence tomography with]"
          - "[[2024] Chen - Adaptive OCT Deconvolution]"
          - "[[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography]"
        related_concepts:
          - "superresolution"
          - "artifact control"
          - "random phase modulation"
        status: open
        importance: high
        tags:
          - research-question
          - superresolution
          - artifact
        cssclasses:
          - research-question-note
        ---

        # 问题定义

        “无伪影超分辨”很容易成为宣传性说法。我真正需要明确的是，一篇 OCT 文章要做到什么程度，才有资格声称自己既提升了分辨率，又没有引入不可接受的伪影。

        # 为什么重要

        这会直接影响我以后如何判断一条增强路线是否真的可信，而不是被视觉效果带偏。

        # 谁回答过

        - [[2022] Unknown - Superresolving artifact-free optical coherence tomography with]]
        - [[2024] Chen - Adaptive OCT Deconvolution]]
        - [[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography]]

        # 文献之间的分歧

        - 有些工作更强调视觉去模糊效果
        - 有些工作开始加入 artifact 指标和对照
        - 对“无伪影”究竟如何定义，还没有形成统一标准

        # 目前我的判断

        至少要同时满足结构真实性、artifact 可控、定量指标提升和对照充分这几项，才有资格接近“无伪影超分辨”的表述。

        # 还缺什么证据

        - 更接近真实任务的评价
        - 与传统锐化方法的严格对照
        - 对失效案例和边界条件的公开报告
        """
    ),
    "Question - Wigner-Ville Gain Interpretation.md": dedent(
        """\
        ---
        type: research-question
        question: "Wigner-Ville 带来的 A-scan 分辨率增强，是真实信息恢复还是时频重分配造成的表观锐化？"
        related_papers:
          - "[[2025] Unknown - Enhanced A-scan spatial resolution in spectral]"
          - "[[2025] Unknown - Enhanced A-scan spatial resolution in spectral -- enhanced-a-scan-spatial-resolution-in-spectral-domain-oct-exploiting-the-wigner-ville-technique]"
        related_concepts:
          - "Wigner-Ville distribution"
          - "A-scan resolution"
          - "time-frequency reassignment"
        status: open
        importance: medium
        tags:
          - research-question
          - wigner-ville
          - axial-resolution
        cssclasses:
          - research-question-note
        ---

        # 问题定义

        我想区分的是：Wigner-Ville 带来的峰值变尖、结构变窄，到底意味着真实可分辨信息增加了，还是主要来自时频表示层面的重新分配与表观锐化。

        # 为什么重要

        如果它主要是表示优化，那我在自己的研究里就不能把它和真正的信息恢复混为一谈。

        # 谁回答过

        - [[2025] Unknown - Enhanced A-scan spatial resolution in spectral]]
        - [[2025] Unknown - Enhanced A-scan spatial resolution in spectral -- enhanced-a-scan-spatial-resolution-in-spectral-domain-oct-exploiting-the-wigner-ville-technique]]

        # 文献之间的分歧

        - 一类解读会把峰值收缩直接视为分辨率提升
        - 更谨慎的解读会追问是否真的提高了可分辨结构数和物理信息量

        # 目前我的判断

        这类方法很可能更接近表示层面的锐化与重分配，除非有更直接的可分辨性验证，否则不宜直接等同于真实信息恢复。

        # 还缺什么证据

        - 双点或细结构可分辨性实验
        - 与传统重建或反卷积方法的统一比较
        - 对交叉项和伪影的系统分析
        """
    ),
}


PAPER_UPDATES = [
    {
        "paper": "[2024] Chen - Adaptive OCT Deconvolution.md",
        "question_id": "UQ-01",
        "question_text": "这篇文章能否真正证明横向分辨率提升来自信息恢复，而不是视觉锐化？",
        "question_note": "Question - Lateral Resolution Gain Limits",
        "status": "open",
        "linked_paragraphs": "p05, p07",
        "linked_quotes": "[[#p05]], [[#p07]]",
        "tentative_answer": "目前部分能，因为作者有 artifact score 和对照实验，但 task-based evaluation 还不够。",
        "final_answer": "",
        "note": "已升级为独立问题页；后续结论在 [[Question - Lateral Resolution Gain Limits]] 中累计。",
    },
    {
        "paper": "[2024] Chen - Adaptive OCT Deconvolution.md",
        "question_id": "UQ-02",
        "question_text": "这种局部 PSF 方案能否迁移到我的横向分辨率增强课题？",
        "question_note": "Question - Local PSF Transferability",
        "status": "pending",
        "linked_paragraphs": "p04",
        "linked_quotes": "[[#p04]]",
        "tentative_answer": "能迁移方法思想，但参数和局部区域划分需要重做。",
        "final_answer": "",
        "note": "已升级为独立问题页；后续结论在 [[Question - Local PSF Transferability]] 中累计。",
    },
    {
        "paper": "[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography.md",
        "question_id": "UQ-01",
        "question_text": "OCT 反卷积路线当前最硬的瓶颈究竟是什么？",
        "question_note": "Question - Deconvolution Bottlenecks in OCT",
        "status": "open",
        "linked_paragraphs": "legacy-note",
        "linked_quotes": "[[#Legacy Source Snapshot]]",
        "tentative_answer": "当前更像是 PSF 失配、噪声放大和验证不足叠加，而不是单一算法短板。",
        "final_answer": "",
        "note": "由旧资料问题升级而来；后续结论在 [[Question - Deconvolution Bottlenecks in OCT]] 中累计。",
    },
    {
        "paper": "[2022] Dong - Spatially adaptive blind deconvolution methods for.md",
        "question_id": "UQ-01",
        "question_text": "空间自适应盲反卷积是否足够稳定，可作为 OCT 分辨率增强主线方法？",
        "question_note": "Question - Blind Deconvolution Stability in OCT",
        "status": "open",
        "linked_paragraphs": "legacy-note",
        "linked_quotes": "[[#Legacy Source Snapshot]]",
        "tentative_answer": "方法很有前景，但还不能直接视为足够稳定的成熟主线。",
        "final_answer": "",
        "note": "由旧资料问题升级而来；后续结论在 [[Question - Blind Deconvolution Stability in OCT]] 中累计。",
    },
    {
        "paper": "[2014] Unknown - Variations in optical coherence tomography resolution.md",
        "question_id": "UQ-01",
        "question_text": "系统分辨率与均匀性波动会不会抵消后续算法增强收益？",
        "question_note": "Question - Resolution Uniformity as Baseline",
        "status": "open",
        "linked_paragraphs": "legacy-note",
        "linked_quotes": "[[#Legacy Source Snapshot]]",
        "tentative_answer": "很可能会，因此基线均匀性不能被当成理所当然的固定背景。",
        "final_answer": "",
        "note": "由旧资料问题升级而来；后续结论在 [[Question - Resolution Uniformity as Baseline]] 中累计。",
    },
    {
        "paper": "[2022] Unknown - Superresolving artifact-free optical coherence tomography with.md",
        "question_id": "UQ-01",
        "question_text": "所谓“无伪影超分辨”需要满足哪些证据标准？",
        "question_note": "Question - Artifact-Free Superresolution Criteria",
        "status": "open",
        "linked_paragraphs": "legacy-note",
        "linked_quotes": "[[#Legacy Source Snapshot]]",
        "tentative_answer": "至少要同时证明 artifact 可控、结构真实性保留、定量指标改善以及对照充分。",
        "final_answer": "",
        "note": "由旧资料问题升级而来；后续结论在 [[Question - Artifact-Free Superresolution Criteria]] 中累计。",
    },
    {
        "paper": "[2025] Unknown - Enhanced A-scan spatial resolution in spectral.md",
        "question_id": "UQ-01",
        "question_text": "Wigner-Ville 带来的 A-scan 分辨率增强，是真实信息恢复还是时频重分配造成的表观锐化？",
        "question_note": "Question - Wigner-Ville Gain Interpretation",
        "status": "open",
        "linked_paragraphs": "legacy-note",
        "linked_quotes": "[[#Legacy Source Snapshot]]",
        "tentative_answer": "目前更像表示层面的锐化与重分配，还需要更直接的可分辨性验证。",
        "final_answer": "",
        "note": "由旧资料问题升级而来；后续结论在 [[Question - Wigner-Ville Gain Interpretation]] 中累计。",
    },
    {
        "paper": "[2025] Unknown - Enhanced A-scan spatial resolution in spectral -- enhanced-a-scan-spatial-resolution-in-spectral-domain-oct-exploiting-the-wigner-ville-technique.md",
        "question_id": "UQ-01",
        "question_text": "Wigner-Ville 带来的 A-scan 分辨率增强，是真实信息恢复还是时频重分配造成的表观锐化？",
        "question_note": "Question - Wigner-Ville Gain Interpretation",
        "status": "open",
        "linked_paragraphs": "legacy-note",
        "linked_quotes": "[[#Legacy Source Snapshot]]",
        "tentative_answer": "目前更像表示层面的锐化与重分配，还需要更直接的可分辨性验证。",
        "final_answer": "",
        "note": "由旧资料问题升级而来；后续结论在 [[Question - Wigner-Ville Gain Interpretation]] 中累计。",
    },
]


def replace_question_block(text: str, update: dict[str, str]) -> str:
    block = dedent(
        f"""\
        - question_id:: {update["question_id"]}
          question_text:: {update["question_text"]}
          question_note:: [[{update["question_note"]}]]
          asked_by:: user
          status:: {update["status"]}
          linked_paragraphs:: {update["linked_paragraphs"]}
          linked_quotes:: {update["linked_quotes"]}
          tentative_answer:: {update["tentative_answer"]}
          final_answer:: {update["final_answer"]}
          note:: {update["note"]}
        """
    ).rstrip()
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip() == f"- question_id:: {update['question_id']}":
            start = idx
            break
    if start is None:
        raise ValueError(f"Question block not found: {update['paper']} {update['question_id']}")

    end = start + 1
    while end < len(lines) and lines[end].startswith("  "):
        end += 1
    if end < len(lines) and lines[end].strip() == "":
        end += 1

    new_lines = lines[:start] + block.splitlines() + [""] + lines[end:]
    return "\n".join(new_lines) + "\n"


def write_question_index(folder: Path) -> None:
    notes = sorted(
        p.stem for p in folder.glob("Question - *.md") if p.name != "_Index.md"
    )
    lines = [
        "---",
        "cssclasses:",
        "  - dashboard-view",
        "---",
        "",
        "# Questions Index",
        "",
        "> [!info]",
        "> 这里优先放已经从论文正文中升级出来、值得长期跟踪的独立研究问题。",
        "",
    ]
    for name in notes:
        lines.append(f"- [[{name}]]")
    index_path = folder / "_Index.md"
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    question_dir = VAULT_ROOT / "04_Research/Questions"
    question_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in QUESTION_NOTES.items():
        (question_dir / filename).write_text(content, encoding="utf-8", newline="\n")
        print(f"Wrote question note: {question_dir / filename}")

    for update in PAPER_UPDATES:
        paper_path = VAULT_ROOT / "02_Literature/Papers" / update["paper"]
        text = paper_path.read_text(encoding="utf-8")
        new_text = replace_question_block(text, update)
        paper_path.write_text(new_text, encoding="utf-8", newline="\n")
        print(f"Updated paper: {paper_path}")

    write_question_index(question_dir)
    print(f"Wrote question index: {question_dir / '_Index.md'}")


if __name__ == "__main__":
    main()
