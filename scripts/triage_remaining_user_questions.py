from __future__ import annotations

from pathlib import Path
from textwrap import dedent


VAULT_ROOT = Path(
    r"C:\Users\1\OneDrive - fzu.edu.cn (1)\Attachments\OCT_Research_System\oct-research-assist\vault"
)
PAPERS_DIR = VAULT_ROOT / "02_Literature/Papers"
QUESTIONS_DIR = VAULT_ROOT / "04_Research/Questions"


NEW_QUESTION_NOTES: dict[str, str] = {
    "Question - Fast Scanning Mechanism Limits in OCT.md": dedent(
        """\
        ---
        type: research-question
        question: "高速光程扫描与偏转机构的非理想性会怎样限制 OCT 系统性能？"
        related_papers:
          - "[[1997] Su - Achieving variation of the optical path]"
          - "[[1997] Unknown - Rapid and scalable scans at 21]"
          - "[[1998] Szydlo - Air-turbine driven optical low-coherence reflectometry]"
          - "[[2013] Wang - Precision control of piezo-actuated optical deflector]"
        related_concepts:
          - "optical delay line"
          - "scan linearity"
          - "actuator hysteresis"
        status: open
        importance: medium
        tags:
          - research-question
          - system-design
          - scanning
        cssclasses:
          - research-question-note
        ---

        # 问题定义

        这里的核心不是“能不能扫得更快”，而是高速扫描、快速光程调制和压电偏转这些机构在真实系统里会以什么形式引入非线性、漂移和重复性问题，并最终限制 OCT 的可用性能。

        # 为什么重要

        对当前研究主线来说，系统机构误差是算法增强的上游边界。如果扫描本身不稳，后续的分辨率提升和定量分析都会被污染。

        # 谁回答过

        - [[1997] Su - Achieving variation of the optical path]]
        - [[1997] Unknown - Rapid and scalable scans at 21]]
        - [[1998] Szydlo - Air-turbine driven optical low-coherence reflectometry]]
        - [[2013] Wang - Precision control of piezo-actuated optical deflector]]

        # 文献之间的分歧

        - 早期工作强调“能更快地扫”
        - 后续系统工作越来越强调线性、迟滞、控制误差和重复性
        - 对成像系统来说，机构极限和控制精度往往比名义速度更关键

        # 目前我的判断

        扫描机构不是外围配角，而是系统上限的一部分。很多看似后处理能解决的问题，本质上可能来自扫描链路的非理想性。

        # 还缺什么证据

        - 扫描非线性对成像质量和定量测量的直接误差传播分析
        - 机构控制改进与成像收益之间的定量对照
        - 扫描稳定性与后续算法鲁棒性的联动评价
        """
    ),
    "Question - Dispersion and Delay-Line Penalties in OCT.md": dedent(
        """\
        ---
        type: research-question
        question: "色散与延迟线非理想性会在多大程度上侵蚀 OCT 系统分辨率与成像深度？"
        related_papers:
          - "[[2003] Unknown - Delay and dispersion characteristics of a]"
          - "[[2009] 邹恒 - 基于时域和频域的光学相干层析成像系统的研究]"
          - "[[2023] 吴开杰 - OCT系统实用化的研究进展]"
        related_concepts:
          - "dispersion compensation"
          - "optical delay line"
          - "system calibration"
        status: open
        importance: high
        tags:
          - research-question
          - dispersion
          - system-baseline
        cssclasses:
          - research-question-note
        ---

        # 问题定义

        我关心的不是“系统里有没有色散”，而是它在多大程度上会直接吞掉可恢复分辨率、有效深度和相位一致性，并让后续增强算法的收益被高估。

        # 为什么重要

        如果色散和延迟线误差没有先被控制好，那么很多算法层面的“增强”其实是在为系统基线问题买单。

        # 谁回答过

        - [[2003] Unknown - Delay and dispersion characteristics of a]]
        - [[2009] 邹恒 - 基于时域和频域的光学相干层析成像系统的研究]]
        - [[2023] 吴开杰 - OCT系统实用化的研究进展]]

        # 文献之间的分歧

        - 一些工作把它当成工程细节
        - 另一些工作则把它视为决定成像质量上限的关键因素

        # 目前我的判断

        色散和延迟线问题不只是校准步骤，而是算法评价的前提条件。若不先稳住这一层，后续很多分辨率讨论都会失真。

        # 还缺什么证据

        - 色散失配对横向/轴向恢复的定量影响
        - 延迟线非理想性在不同系统架构里的误差预算
        - 系统补偿与算法补偿的成本收益对比
        """
    ),
    "Question - Fourier Domain Gains vs System Cost.md": dedent(
        """\
        ---
        type: research-question
        question: "频域 OCT 的理论速度与 SNR 优势，在真实系统里需要付出哪些系统代价？"
        related_papers:
          - "[[2003] de Boer - Improved signal-to-noise ratio in spectral-domain compared]"
          - "[[2008] Unknown - Fourier domain optical coherence tomography using]"
          - "[[2009] 邹恒 - 基于时域和频域的光学相干层析成像系统的研究]"
        related_concepts:
          - "Fourier domain OCT"
          - "SNR advantage"
          - "system complexity"
        status: open
        importance: high
        tags:
          - research-question
          - fourier-domain
          - snr
        cssclasses:
          - research-question-note
        ---

        # 问题定义

        频域 OCT 的速度和灵敏度优势是经典结论，但我更关心的是：这些理论收益在真实系统中是通过什么代价换来的，例如色散、系统复杂度、器件要求和数据负担。

        # 为什么重要

        这会影响我对“系统升级”和“后处理增强”之间投入优先级的判断。

        # 谁回答过

        - [[2003] de Boer - Improved signal-to-noise ratio in spectral-domain compared]]
        - [[2008] Unknown - Fourier domain optical coherence tomography using]]
        - [[2009] 邹恒 - 基于时域和频域的光学相干层析成像系统的研究]]

        # 文献之间的分歧

        - 经典论述强调频域优势非常明显
        - 真正落地到系统时，又会出现色散、器件复杂度和实现成本上的反推力

        # 目前我的判断

        频域优势当然成立，但它不是“白拿”的。系统设计成本、校准复杂度和数据链路压力，都是必须算在一起的真实代价。

        # 还缺什么证据

        - 不同频域实现路径的统一成本收益比较
        - 系统复杂度提升与最终成像收益之间的量化关系
        - 与算法增强路线的横向对照
        """
    ),
    "Question - Speed Sensitivity Tradeoff in High-Speed OCT.md": dedent(
        """\
        ---
        type: research-question
        question: "把 A-line rate 推到超高速后，灵敏度、实时显示和数据负担之间应如何平衡？"
        related_papers:
          - "[[2011] An - High speed spectral domain optical coherence]"
          - "[[2012] Choi - Spectral domain optical coherence tomography of]"
          - "[[2008] Unknown - Fourier domain optical coherence tomography using]"
        related_concepts:
          - "A-line rate"
          - "sensitivity roll-off"
          - "real-time display"
        status: open
        importance: high
        tags:
          - research-question
          - high-speed-oct
          - sensitivity
        cssclasses:
          - research-question-note
        ---

        # 问题定义

        我关心的不是单纯把扫描速度做高，而是在超高速条件下，灵敏度、滚降、显示延迟、计算负担和系统稳定性该如何一起评估。

        # 为什么重要

        这直接关系到以后系统路线该偏向更快采集，还是偏向更稳、更可解释的高质量成像。

        # 谁回答过

        - [[2011] An - High speed spectral domain optical coherence]]
        - [[2012] Choi - Spectral domain optical coherence tomography of]]
        - [[2008] Unknown - Fourier domain optical coherence tomography using]]

        # 文献之间的分歧

        - 有的工作把更高 A-line rate 当成主目标
        - 有的工作会更关注速度带来的灵敏度、数据链路和实时显示压力

        # 目前我的判断

        超高速本身不是终点。若没有把灵敏度和可处理性一起纳入评价，更高速度未必等价于更高研究价值。

        # 还缺什么证据

        - 速度收益与灵敏度损失的统一曲线
        - 实时显示与后处理延迟的系统级预算
        - 在真实任务下，超高速是否带来可验证的下游收益
        """
    ),
    "Question - OCT Practicalization Bottlenecks.md": dedent(
        """\
        ---
        type: research-question
        question: "OCT 实用化的真正瓶颈更偏系统工程、成本，还是算法处理？"
        related_papers:
          - "[[2023] 吴开杰 - OCT系统实用化的研究进展]"
          - "[[2009] 邹恒 - 基于时域和频域的光学相干层析成像系统的研究]"
          - "[[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography]"
        related_concepts:
          - "practicalization"
          - "system integration"
          - "cost-performance tradeoff"
        status: pending
        importance: high
        tags:
          - research-question
          - practicalization
          - roadmap
        cssclasses:
          - research-question-note
        ---

        # 问题定义

        我想知道的是，OCT 从实验系统走向可用产品和稳定平台时，真正卡住它的更像是系统工程与成本，还是算法与后处理。

        # 为什么重要

        这会直接影响后续研究的资源配置。如果主瓶颈不在算法，就不该把过多精力误投到局部后处理优化上。

        # 谁回答过

        - [[2023] 吴开杰 - OCT系统实用化的研究进展]]
        - [[2009] 邹恒 - 基于时域和频域的光学相干层析成像系统的研究]]
        - [[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography]]

        # 文献之间的分歧

        - 有的综述更强调系统集成、成本与稳定性
        - 有的研究则持续把重点放在算法恢复与图像增强上

        # 目前我的判断

        对真正的实用化路线来说，系统工程、稳定性和成本往往比单点算法改进更具决定性；算法更像是锦上添花，而不是单独破局点。

        # 还缺什么证据

        - 实际部署场景里的成本收益比较
        - 系统稳定性与算法收益之间的耦合分析
        - 产业化指标与学术指标的对照表
        """
    ),
}


PROMOTED_UPDATES = [
    {
        "match": "Achieving variation of the optical path",
        "question_id": "UQ-01",
        "question_text": "高速光程扫描与偏转机构的非理想性会怎样限制 OCT 系统性能？",
        "question_note": "Question - Fast Scanning Mechanism Limits in OCT",
        "status": "open",
        "linked_paragraphs": "",
        "linked_quotes": "",
        "tentative_answer": "这类工作说明速度潜力很重要，但真正决定系统可用性的往往是线性、重复性和控制误差。",
        "final_answer": "",
        "note": "已升级为独立问题页；后续结论在 [[Question - Fast Scanning Mechanism Limits in OCT]] 中累计。",
    },
    {
        "match": "Rapid and scalable scans at 21",
        "question_id": "UQ-01",
        "question_text": "高速光程扫描与偏转机构的非理想性会怎样限制 OCT 系统性能？",
        "question_note": "Question - Fast Scanning Mechanism Limits in OCT",
        "status": "open",
        "linked_paragraphs": "",
        "linked_quotes": "",
        "tentative_answer": "速度扩展本身有价值，但如果缺少稳定控制和误差分析，系统收益容易被高估。",
        "final_answer": "",
        "note": "已升级为独立问题页；后续结论在 [[Question - Fast Scanning Mechanism Limits in OCT]] 中累计。",
    },
    {
        "match": "Air-turbine driven optical low-coherence reflectometry",
        "question_id": "UQ-01",
        "question_text": "高速光程扫描与偏转机构的非理想性会怎样限制 OCT 系统性能？",
        "question_note": "Question - Fast Scanning Mechanism Limits in OCT",
        "status": "open",
        "linked_paragraphs": "",
        "linked_quotes": "",
        "tentative_answer": "这篇更像早期硬件路线样本，提醒我扫描机构的工程边界不能被后处理思维忽略。",
        "final_answer": "",
        "note": "已升级为独立问题页；后续结论在 [[Question - Fast Scanning Mechanism Limits in OCT]] 中累计。",
    },
    {
        "match": "Precision control of piezo-actuated optical deflector",
        "question_id": "UQ-01",
        "question_text": "高速光程扫描与偏转机构的非理想性会怎样限制 OCT 系统性能？",
        "question_note": "Question - Fast Scanning Mechanism Limits in OCT",
        "status": "open",
        "linked_paragraphs": "",
        "linked_quotes": "",
        "tentative_answer": "它把问题从“能扫”推进到“能否精确控制”，这一步对系统级成像质量非常关键。",
        "final_answer": "",
        "note": "已升级为独立问题页；后续结论在 [[Question - Fast Scanning Mechanism Limits in OCT]] 中累计。",
    },
    {
        "match": "Delay and dispersion characteristics of a",
        "question_id": "UQ-01",
        "question_text": "色散与延迟线非理想性会在多大程度上侵蚀 OCT 系统分辨率与成像深度？",
        "question_note": "Question - Dispersion and Delay-Line Penalties in OCT",
        "status": "open",
        "linked_paragraphs": "",
        "linked_quotes": "",
        "tentative_answer": "色散与延迟线误差不是小修小补问题，而是会直接改变系统基线质量的上游约束。",
        "final_answer": "",
        "note": "已升级为独立问题页；后续结论在 [[Question - Dispersion and Delay-Line Penalties in OCT]] 中累计。",
    },
    {
        "match": "Fourier domain optical coherence tomography using",
        "question_id": "UQ-01",
        "question_text": "频域 OCT 的理论速度与 SNR 优势，在真实系统里需要付出哪些系统代价？",
        "question_note": "Question - Fourier Domain Gains vs System Cost",
        "status": "open",
        "linked_paragraphs": "",
        "linked_quotes": "",
        "tentative_answer": "极高速度很吸引人，但它也在器件、数据链路和系统复杂度上提出了更高代价。",
        "final_answer": "",
        "note": "已升级为独立问题页；后续结论在 [[Question - Fourier Domain Gains vs System Cost]] 中累计。",
    },
    {
        "match": "基于时域和频域的光学相干层析成像系统的研究",
        "question_id": "UQ-01",
        "question_text": "频域 OCT 的理论速度与 SNR 优势，在真实系统里需要付出哪些系统代价？",
        "question_note": "Question - Fourier Domain Gains vs System Cost",
        "status": "open",
        "linked_paragraphs": "",
        "linked_quotes": "",
        "tentative_answer": "这类系统对比最适合拿来提醒自己：架构优势成立，但它总是和工程代价一起出现。",
        "final_answer": "",
        "note": "已升级为独立问题页；后续结论在 [[Question - Fourier Domain Gains vs System Cost]] 中累计。",
    },
    {
        "match": "High speed spectral domain optical coherence",
        "question_id": "UQ-01",
        "question_text": "把 A-line rate 推到超高速后，灵敏度、实时显示和数据负担之间应如何平衡？",
        "question_note": "Question - Speed Sensitivity Tradeoff in High-Speed OCT",
        "status": "open",
        "linked_paragraphs": "",
        "linked_quotes": "",
        "tentative_answer": "更高速度本身不是终点，关键是速度收益有没有换来可接受的灵敏度和处理成本。",
        "final_answer": "",
        "note": "已升级为独立问题页；后续结论在 [[Question - Speed Sensitivity Tradeoff in High-Speed OCT]] 中累计。",
    },
    {
        "match": "Spectral domain optical coherence tomography of",
        "question_id": "UQ-01",
        "question_text": "把 A-line rate 推到超高速后，灵敏度、实时显示和数据负担之间应如何平衡？",
        "question_note": "Question - Speed Sensitivity Tradeoff in High-Speed OCT",
        "status": "open",
        "linked_paragraphs": "",
        "linked_quotes": "",
        "tentative_answer": "实时 4D 和 multi-MHz 很强，但研究上更重要的是它们是否带来稳定可验证的收益。",
        "final_answer": "",
        "note": "已升级为独立问题页；后续结论在 [[Question - Speed Sensitivity Tradeoff in High-Speed OCT]] 中累计。",
    },
    {
        "match": "OCT系统实用化的研究进展",
        "question_id": "UQ-01",
        "question_text": "OCT 实用化的真正瓶颈更偏系统工程、成本，还是算法处理？",
        "question_note": "Question - OCT Practicalization Bottlenecks",
        "status": "pending",
        "linked_paragraphs": "",
        "linked_quotes": "",
        "tentative_answer": "从目前材料看，系统工程和稳定性可能比单点算法改进更接近实用化瓶颈。",
        "final_answer": "",
        "note": "已升级为独立问题页；后续结论在 [[Question - OCT Practicalization Bottlenecks]] 中累计。",
    },
]


DEFERRED_UPDATES = [
    {
        "match": "In Vivo Endoscopic Optical Biopsy with",
        "question_id": "UQ-01",
        "question_text": "这篇早期内镜 OCT 应用文献对当前分辨率增强主线的直接方法价值是什么？",
        "status": "pending",
        "linked_paragraphs": "",
        "linked_quotes": "",
        "tentative_answer": "当前更像应用展示参考，而不是直接的方法主线文献。",
        "final_answer": "",
        "note": "模板占位，暂不升格为独立问题；原因：更偏应用展示。见 [[Question Triage - Placeholder Backlog]]。",
    },
    {
        "match": "In Vivo Three-Dimensional Imaging of Neovascular",
        "question_id": "UQ-01",
        "question_text": "这篇三维新生血管成像工作对当前系统/算法主线有无直接可迁移价值？",
        "status": "pending",
        "linked_paragraphs": "",
        "linked_quotes": "",
        "tentative_answer": "目前更适合作为应用场景参考，还不是直接的方法路线支撑。",
        "final_answer": "",
        "note": "模板占位，暂不升格为独立问题；原因：更偏应用展示。见 [[Question Triage - Placeholder Backlog]]。",
    },
    {
        "match": "Real-time monitoring of structural vibration using",
        "question_id": "UQ-01",
        "question_text": "这篇跨领域 OCT 监测工作与当前成像分辨率主线的直接交集是什么？",
        "status": "pending",
        "linked_paragraphs": "",
        "linked_quotes": "",
        "tentative_answer": "目前交集有限，更适合作为跨领域使用案例，而不是当前方法主线依据。",
        "final_answer": "",
        "note": "模板占位，暂不升格为独立问题；原因：更偏跨领域应用。见 [[Question Triage - Placeholder Backlog]]。",
    },
    {
        "match": "Repetitive optical coherence elastography measurements with",
        "question_id": "UQ-01",
        "question_text": "这篇弹性成像重复性研究对当前 OCT 分辨率增强路线的直接启发是什么？",
        "status": "pending",
        "linked_paragraphs": "",
        "linked_quotes": "",
        "tentative_answer": "它对重复性和稳定性有提醒价值，但与当前分辨率增强主线不是直接一跳相连。",
        "final_answer": "",
        "note": "模板占位，暂不升格为独立问题；原因：更偏相关应用。见 [[Question Triage - Placeholder Backlog]]。",
    },
    {
        "match": "光学相干断层扫描",
        "question_id": "UQ-01",
        "question_text": "这篇泛综述/教材型文献里，哪些基础概念值得单独沉淀为概念卡？",
        "status": "pending",
        "linked_paragraphs": "",
        "linked_quotes": "",
        "tentative_answer": "更适合作为基础概念提炼入口，而不是直接升格成单个研究问题。",
        "final_answer": "",
        "note": "模板占位，暂不升格为独立问题；原因：更偏概览性材料。见 [[Question Triage - Placeholder Backlog]]。",
    },
]


TRIAGE_NOTE = dedent(
    """\
    ---
    cssclasses:
      - dashboard-view
    ---

    # Question Triage - Placeholder Backlog

    > [!info]
    > 这份笔记记录两类内容：一类是这轮已经从论文正文升级出来的独立问题；另一类是目前先保留为“待补占位”的用户问题。

    ## 本轮已升格为独立问题的母题

    - [[Question - Fast Scanning Mechanism Limits in OCT]]
    - [[Question - Dispersion and Delay-Line Penalties in OCT]]
    - [[Question - Fourier Domain Gains vs System Cost]]
    - [[Question - Speed Sensitivity Tradeoff in High-Speed OCT]]
    - [[Question - OCT Practicalization Bottlenecks]]

    ## 当前暂缓升格的占位问题

    - `应用展示类`
      [1997] Unknown - In Vivo Endoscopic Optical Biopsy with
      [2008] Unknown - In Vivo Three-Dimensional Imaging of Neovascular
    - `跨领域参考类`
      [2010] Zhong - Real-time monitoring of structural vibration using
      [2020] Unknown - Repetitive optical coherence elastography measurements with
    - `概览/教材类`
      [2005] Unknown - 光学相干断层扫描

    ## 当前处理规则

    1. 能稳定挂到长期研究母题上的，升级成独立 `Question - ...` 笔记
    2. 还只是“可能有用”，但暂时不值得独立维护的，保留在论文页里并标记为 `pending`
    3. 真正值得继续追踪时，再从 backlog 中升格出来
    """
)


def resolve_paper(match: str) -> Path:
    for path in PAPERS_DIR.glob("*.md"):
        if match in path.name:
            return path
    raise FileNotFoundError(match)


def replace_question_block(text: str, update: dict[str, str]) -> str:
    block_lines = [
        f"- question_id:: {update['question_id']}",
        f"  question_text:: {update['question_text']}",
    ]
    if update.get("question_note"):
        block_lines.append(f"  question_note:: [[{update['question_note']}]]")
    block_lines.extend(
        [
            "  asked_by:: user",
            f"  status:: {update['status']}",
            f"  linked_paragraphs:: {update['linked_paragraphs']}",
            f"  linked_quotes:: {update['linked_quotes']}",
            f"  tentative_answer:: {update['tentative_answer']}",
            f"  final_answer:: {update['final_answer']}",
            f"  note:: {update['note']}",
        ]
    )
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip() == f"- question_id:: {update['question_id']}":
            start = idx
            break
    if start is None:
        raise ValueError(f"Question block not found for {update['question_id']}")

    end = start + 1
    while end < len(lines) and lines[end].startswith("  "):
        end += 1
    if end < len(lines) and lines[end].strip() == "":
        end += 1

    new_lines = lines[:start] + block_lines + [""] + lines[end:]
    return "\n".join(new_lines) + "\n"


def write_index() -> None:
    research_notes = sorted(
        p.stem for p in QUESTIONS_DIR.glob("Question - *.md") if p.name != "_Index.md"
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
        "## Independent Questions",
        "",
    ]
    lines.extend(f"- [[{name}]]" for name in research_notes)
    lines.extend(
        [
            "",
            "## Support Notes",
            "",
            "- [[Question Triage - Placeholder Backlog]]",
            "",
        ]
    )
    (QUESTIONS_DIR / "_Index.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n"
    )


def main() -> None:
    QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)

    for name, content in NEW_QUESTION_NOTES.items():
        (QUESTIONS_DIR / name).write_text(content, encoding="utf-8", newline="\n")
        print(f"Wrote question note: {QUESTIONS_DIR / name}")

    (QUESTIONS_DIR / "Question Triage - Placeholder Backlog.md").write_text(
        TRIAGE_NOTE, encoding="utf-8", newline="\n"
    )
    print(f"Wrote triage note: {QUESTIONS_DIR / 'Question Triage - Placeholder Backlog.md'}")

    for update in PROMOTED_UPDATES + DEFERRED_UPDATES:
        paper_path = resolve_paper(update["match"])
        text = paper_path.read_text(encoding="utf-8")
        new_text = replace_question_block(text, update)
        paper_path.write_text(new_text, encoding="utf-8", newline="\n")
        print(f"Updated paper: {paper_path}")

    write_index()
    print(f"Wrote question index: {QUESTIONS_DIR / '_Index.md'}")


if __name__ == "__main__":
    main()
