from __future__ import annotations

import re
from pathlib import Path


VAULT_ROOT = Path(
    r"C:\Users\1\OneDrive - fzu.edu.cn (1)\Attachments\OCT_Research_System\oct-research-assist\vault"
)
PAPERS_DIR = VAULT_ROOT / "02_Literature" / "Papers"
UPDATED_AT = "2026-03-23 16:25:00"


PAPER_UPDATES = {
    "[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography.md": {
        "title_zh": "光学相干断层扫描中的反卷积技术：研究进展",
        "translation_keywords": [
            "deconvolution: 反卷积 / 去卷积",
            "optical coherence tomography: 光学相干断层扫描",
            "advancements: 进展、推进、近期发展",
        ],
        "translation_direct": "光学相干断层扫描中的反卷积技术：进展",
        "translation_free": "OCT 反卷积技术研究进展",
        "translation_rationale": "保留技术对象与综述性质，方便在综述类文献中统一索引。",
        "q2_short": (
            "这篇综述的核心主张不是“某一种反卷积已经解决 OCT 成像问题”，而是指出 "
            "OCT 反卷积已经形成多条技术路线，但 PSF 获取不准、噪声放大、计算负担和验证不足"
            "仍是跨路线反复出现的共性瓶颈。"
        ),
        "q2_deep": (
            "文章真正强调的是：评价 OCT 反卷积工作时，不能只看图像是否更锐利，而要同时追问 "
            "PSF 是如何得到的、噪声是否被放大、算法是否可承受、结论是否经得起统一验证。"
            "它把文献分成 non-blind、adaptive、blind、advanced 与 AI-assisted 等几条路径，"
            "但并没有把任何一条路径写成“已经收敛的最终答案”。对你的课题来说，这篇文章更像"
            "问题地图与论证框架：它支撑你说明为什么 measured-PSF、phantom-led validation"
            " 与 artifact-aware evaluation 仍然值得单独做，而不是被一篇“清晰图像展示”轻易替代。"
        ),
        "support_points": [
            "旧笔记将文章定位为 field map，而不是单一算法论文。",
            "文中按 non-blind、adaptive、blind、advanced、AI-assisted 几条路线组织讨论。",
            "旧资料反复强调 PSF 准确性、噪声放大、计算成本和验证不足是共性瓶颈。",
        ],
        "concepts": [
            "PSF 建模与误差传播",
            "噪声放大与正则化",
            "无真值条件下的评价可信度",
        ],
        "counterargument": (
            "作为综述，它能清楚划出问题边界，却不能替代统一 benchmark。不同方法并未在同一"
            "数据、同一 artifact 标准和同一代价约束下直接对比，因此它更适合做研究框架，"
            "不适合直接替你下最终算法结论。"
        ),
        "judgment": (
            "把它定位为“相关工作与研究动机骨架文献”最合适。写论文时可借它论证："
            "现有反卷积路线不少，但真正缺的是可解释、可验证、可迁移的评估链。"
        ),
    },
    "[2022] Dong - Spatially adaptive blind deconvolution methods for.md": {
        "title_zh": "用于光学相干断层扫描的空间自适应盲反卷积方法",
        "translation_keywords": [
            "spatially adaptive: 空间自适应",
            "blind deconvolution: 盲反卷积 / 半盲反卷积",
            "optical coherence tomography: 光学相干断层扫描",
        ],
        "translation_direct": "面向 OCT 的空间自适应盲反卷积方法",
        "translation_free": "用于光学相干断层扫描的空间自适应盲反卷积方法",
        "translation_rationale": "突出方法属性与应用对象，适合与非盲 PSF 路线并列比较。",
        "q2_short": (
            "这篇文章的核心主张是：OCT 中随深度变化的横向 PSF 不能再被固定核近似，"
            "应把成像对象和空间变化 PSF 放进同一优化框架，用具有物理含义的 blind / semi-blind"
            " 反卷积去联合估计。"
        ),
        "q2_deep": (
            "作者并不是简单主张“盲反卷积更清晰”，而是进一步提出：如果 OCT 横向模糊确实具有"
            "明显的空间变化，那么非盲、固定核的做法会系统性丢失信息，应该把 depth-related PSF"
            " 参数与潜在清晰图像一起迭代求解。文章用 Gaussian beam 近似连接物理成像模型与"
            " blind deconvolution，并配合 TV、Tikhonov 或 l1 正则以及 Fourier 加速版本，"
            "试图在可解释性和可计算性之间取平衡。对你的项目而言，它最重要的价值是提供了一条"
            "与 measured-PSF 非盲路线正面可比的经典基线：如果你要证明真实测得 PSF 更可靠，"
            "这篇文章就是需要认真对照的近邻方法。"
        ),
        "support_points": [
            "旧笔记明确写到作者把 depth-related lateral PSF 参数与潜在图像交替求解。",
            "方法建立在 Gaussian beam 模型之上，并结合多种正则项约束解。",
            "文章还给出 Fourier 加速版本，说明作者同时关心可实现性而非纯概念展示。",
        ],
        "concepts": [
            "空间变化 PSF",
            "盲 / 半盲反卷积",
            "正则化与模型可解释性",
        ],
        "counterargument": (
            "方法链条高度依赖 Gaussian beam 对真实横向 PSF 的拟合能力。若系统存在离轴畸变、"
            "非高斯旁瓣或复杂像差，这一路线的解释力会明显下降，图像更清晰也不自动等于模型更真。"
        ),
        "judgment": (
            "把它当成 classical-but-strong baseline 最合适。后续若 measured-PSF 方法要成立，"
            "至少需要在评价设计上说明它为何比 Gaussian-model blind deconvolution 更可信。"
        ),
    },
    "[2014] Unknown - Variations in optical coherence tomography resolution.md": {
        "title_zh": "光学相干断层扫描分辨率与均匀性的变化：多系统性能比较",
        "translation_keywords": [
            "variations: 变化 / 波动",
            "resolution and uniformity: 分辨率与均匀性",
            "multi-system performance comparison: 多系统性能比较",
        ],
        "translation_direct": "光学相干断层扫描分辨率与均匀性的变化：多系统性能比较",
        "translation_free": "OCT 分辨率与均匀性变化的多系统性能比较",
        "translation_rationale": "完整保留 benchmarking 语义，方便后续作为评价地基文献引用。",
        "q2_short": (
            "这篇文章的核心主张是：讨论 OCT 分辨率提升之前，必须先把不同系统在不同位置上的"
            "分辨率与均匀性测清楚；否则任何“变清晰”的结论都缺少可靠的测量基线。"
        ),
        "q2_deep": (
            "文章把论证重点放在 measurement 与 benchmark，而不是具体算法。它真正要说的是："
            "OCT 的横向、轴向性能以及场均匀性本身会随系统和位置变化，如果这些基础差异都没有被"
            "标准化测量，那么后续任何关于“分辨率提升”的主张都可能只是局部现象或展示偏差。"
            "对你的课题而言，这一主张尤其关键，因为你不仅要证明图像变好看，更要证明改善具有"
            "位置鲁棒性、评价一致性和物理可解释性。换句话说，这篇文献不是直接教你怎么做反卷积，"
            "而是在替你回答一个更底层的问题：什么样的证据才足以支撑分辨率改进的论文结论。"
        ),
        "support_points": [
            "旧笔记强调文章基于体模或标准化目标比较不同系统的分辨率和均匀性。",
            "作者关注横向、轴向性能随位置变化，而不是只展示单张最优图像。",
            "旧资料将其定位为 phantom-led validation 与 field dependence 评估的地基文献。",
        ],
        "concepts": [
            "体模与标准化测量",
            "uniformity / field dependence",
            "无真值条件下的评价设计",
        ],
        "counterargument": (
            "它不是反卷积论文，因此不能直接替你决定算法路线。它给出的更多是评价框架与"
            "测量哲学，而不是一个可直接复现的恢复算子。"
        ),
        "judgment": (
            "把这篇文章放进“评价可信度”主线非常值得。后续只要你声称横向分辨率提升，"
            "就需要用这类 benchmark 视角约束自己的实验设计。"
        ),
    },
    "[2022] Unknown - Superresolving artifact-free optical coherence tomography with.md": {
        "title_zh": "基于反卷积-随机相位调制的无伪影超分辨光学相干断层扫描",
        "translation_keywords": [
            "superresolving: 超分辨",
            "artifact-free: 无伪影 / 伪影受控",
            "deconvolution-random phase modulation: 反卷积-随机相位调制",
        ],
        "translation_direct": "基于反卷积-随机相位调制的超分辨、无伪影光学相干断层扫描",
        "translation_free": "基于反卷积-随机相位调制的无伪影超分辨光学相干断层扫描",
        "translation_rationale": "把 artifact-free 放进主标题，强调该文不是只追求更窄主瓣。",
        "q2_short": (
            "这篇文章的核心主张是：OCT 的分辨率增强不能只看“更尖锐”，还必须同步控制"
            "反卷积带来的振铃与伪影；因此作者把随机相位调制与反卷积联立设计，以追求"
            "superresolving 且 artifact-free 的成像结果。"
        ),
        "q2_deep": (
            "作者真正想证明的是，分辨率提升与伪影控制应该被视为同一个问题，而不是先锐化、"
            "再事后解释副作用。文章把 deconvolution 与 random phase modulation 结合起来，"
            "试图让频谱信息的利用方式更有利于细节恢复，同时抑制传统直接反卷积常见的 ringing"
            " 与旁瓣问题。对你的研究最有启发的地方不一定是它的整套实现，而是它把“artifact-free”"
            "写成了主张本身：如果后续论文只报告 FWHM 缩小，却不报告伪影代价，那就并没有真正"
            "回答图像是否更可信。"
        ),
        "support_points": [
            "旧笔记直接指出作者讨论的是“超分辨效果”与“伪影可控性”的并行问题。",
            "方法路线不是单纯后端锐化，而是把成像调制与反卷积合并考虑。",
            "旧资料把这篇文献定位为 artifact-aware evaluation 的参照，而非首要复现目标。",
        ],
        "concepts": [
            "artifact-aware superresolution",
            "随机相位调制",
            "振铃 / 旁瓣控制",
        ],
        "counterargument": (
            "收益到底来自更好的信息恢复还是来自特定调制策略本身，还需要更细的拆解。"
            "若调制环节在你的平台上难以稳定实现，它对当前 MATLAB 主线的直接工程价值会下降。"
        ),
        "judgment": (
            "把它作为“不能只看清晰度，还要看伪影代价”的关键旁证非常合适。它更像评估准则的"
            "提醒器，而不一定是第一优先级的复现对象。"
        ),
    },
    "[2025] Unknown - Enhanced A-scan spatial resolution in spectral.md": {
        "title_zh": "利用 Wigner-Ville 技术增强频域 OCT 的 A-scan 空间分辨率",
        "translation_keywords": [
            "A-scan spatial resolution: A-scan 空间分辨率 / 轴向解析能力",
            "spectral domain OCT: 频域 OCT",
            "Wigner-Ville technique: Wigner-Ville 时频分析方法",
        ],
        "translation_direct": "利用 Wigner-Ville 技术增强频域 OCT 的 A-scan 空间分辨率",
        "translation_free": "基于 Wigner-Ville 时频分析的频域 OCT A-scan 分辨率增强",
        "translation_rationale": "保留 A-scan 与 SD-OCT 场景，突出它是时频分析路线而非反卷积路线。",
        "q2_short": (
            "这篇文章的核心主张是：传统 FFT 重建低估了 SD-OCT 干涉信号中的局部时频信息，"
            "因此可用 smoothed pseudo Wigner-Ville distribution 做局部谱分析，以获得比"
            "常规 FFT 更高的 A-scan 分辨率与更好的对比噪声表现。"
        ),
        "q2_deep": (
            "作者要证明的并不是“再做一种反卷积”，而是指出 OCT 计算增强还存在另一条路线："
            "把干涉信号视为局部非平稳信号，再通过时频分析提取被全局 Fourier 变换平均掉的结构信息。"
            "文章因此把 smoothed pseudo Wigner-Ville distribution 作为核心工具，主张其能"
            "提升 A-scan 或轴向分辨表达，并改善与 FFT 相比的局部解析能力。对你的项目而言，"
            "这篇文献的重要性更多体现在边界说明：它证明“分辨率增强”不必然等于“横向 PSF 反卷积”，"
            "也正因此能反衬你当前 measured-PSF 横向路线的独立研究空间。"
        ),
        "support_points": [
            "旧笔记明确把文章定位为局部时频分析增强，而非横向 PSF 反卷积。",
            "作者声称可比常规 FFT 获得更高的 A-scan 分辨率和更好的 CNR 表现。",
            "旧资料已把它标为 comparator 与 scope boundary 文献。",
        ],
        "concepts": [
            "局部时频分析",
            "A-scan / 轴向分辨率",
            "scope boundary 与相关工作定位",
        ],
        "counterargument": (
            "它与当前横向分辨率主线存在明显 scope mismatch，且时频方法的计算代价与样本依赖性"
            "仍需回原文精确抽取。即便图像更可分，也不代表它解决了 lateral PSF 问题。"
        ),
        "judgment": (
            "把它放进 introduction 或 related work 里作为“非反卷积增强路线”的代表最合适。"
            "它强化的是研究边界，而不是直接替代你的主基线。"
        ),
    },
    "[2025] Unknown - Enhanced A-scan spatial resolution in spectral -- enhanced-a-scan-spatial-resolution-in-spectral-domain-oct-exploiting-the-wigner-ville-technique.md": {
        "title_zh": "利用 Wigner-Ville 技术增强频域 OCT 的 A-scan 空间分辨率",
        "translation_keywords": [
            "A-scan spatial resolution: A-scan 空间分辨率 / 轴向解析能力",
            "spectral domain OCT: 频域 OCT",
            "Wigner-Ville technique: Wigner-Ville 时频分析方法",
        ],
        "translation_direct": "利用 Wigner-Ville 技术增强频域 OCT 的 A-scan 空间分辨率",
        "translation_free": "基于 Wigner-Ville 时频分析的频域 OCT A-scan 分辨率增强",
        "translation_rationale": "沿用迁移后的英文主标题，保持与导出模板和索引的一致性。",
        "q2_short": (
            "这篇文章的核心主张是：SD-OCT 的 FFT 重建没有充分利用干涉信号中的局部频率结构，"
            "因此用 Wigner-Ville 类时频分析可以增强 A-scan 的细节解析，并作为常规 FFT 的"
            "计算增强替代路线。"
        ),
        "q2_deep": (
            "从论证结构看，作者并不把问题定义成“如何估计横向 PSF”，而是定义成“如何从干涉信号中"
            "挖出被全局 Fourier 处理弱化掉的局部结构信息”。这使得文章的主张非常清楚：若信号具有"
            "局部非平稳性，那么基于 Wigner-Ville 的时频表示就可能比传统 FFT 更适合恢复 A-scan"
            " 细节。对你的课题来说，这篇文章的关键价值不是直接复现，而是作为 scope boundary："
            "你可以借它说明 OCT 分辨率增强还有时频分析这一支，但这并不等于横向去模糊、体模验证和"
            " artifact-aware lateral evaluation 已经被解决。"
        ),
        "support_points": [
            "旧笔记把它归为时频分析增强路线，而非横向反卷积路线。",
            "文章核心关注 A-scan 解析能力，而不是离焦横向 PSF 的联合估计。",
            "它适合作为“为什么别的增强路线不能直接替代当前主线”的回应材料。",
        ],
        "concepts": [
            "Wigner-Ville 时频表示",
            "FFT 重建边界",
            "横向与轴向增强的任务区分",
        ],
        "counterargument": (
            "最大的限制仍然是主题错位：它解决的是 A-scan / 轴向局部解析，不是横向 PSF 恢复。"
            "如果计算代价较高且增益依赖特定信号结构，它在工程链中的优先级会更低。"
        ),
        "judgment": (
            "把它定位为边界文献和答辩时的补充回应很合适。真正需要继续深挖的，仍是你自己的"
            "横向 PSF 建模、反卷积比较和评价链。"
        ),
    },
}


def replace_yaml_value(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf'^{re.escape(key)}:.*$', re.MULTILINE)
    replacement = f'{key}: "{value}"'
    if not pattern.search(text):
        raise ValueError(f"Missing YAML key: {key}")
    return pattern.sub(replacement, text, count=1)


def build_translation_block(payload: dict[str, object], title_en: str, short_title: str, citation_title: str) -> str:
    keyword_lines = "\n".join(f"> - {item}" for item in payload["translation_keywords"])
    return (
        "> [!translation]\n"
        f"> 原始标题：{title_en}\n"
        f"> 英文标题：{title_en}\n"
        f"> 中文标题：{payload['title_zh']}\n"
        f"> short title：{short_title}\n"
        f"> citation title：{citation_title}\n"
        ">\n"
        "> 关键词拆解：\n"
        f"{keyword_lines}\n"
        ">\n"
        "> 标题翻译说明：\n"
        f"> - 直译：{payload['translation_direct']}\n"
        f"> - 意译：{payload['translation_free']}\n"
        f"> - 采用当前译名的原因：{payload['translation_rationale']}"
    )


def build_q2_focus(payload: dict[str, object]) -> str:
    support_lines = "\n".join(f"> - {item}" for item in payload["support_points"])
    concept_lines = "\n".join(f"> - {item}" for item in payload["concepts"])
    return (
        "# Q2 深答区\n\n"
        "> [!q2-focus]\n"
        "> Q2: 这篇文章的核心论点 / 主张是什么？\n"
        ">\n"
        "> q2_status:: draft\n"
        "> q2_confidence:: medium\n"
        "> q2_source_paragraphs:: legacy-note\n"
        ">\n"
        "> 精炼回答：\n"
        f"> {payload['q2_short']}\n"
        ">\n"
        "> 分析回答：\n"
        f"> {payload['q2_deep']}\n"
        ">\n"
        "> 支持摘录：\n"
        f"{support_lines}\n"
        ">\n"
        "> 原文出处：\n"
        "> - [[#Legacy Source Snapshot]]\n"
        "> - legacy-note（待回原文补段号与精确引文）\n"
        ">\n"
        "> 依赖概念：\n"
        f"{concept_lines}\n"
        ">\n"
        "> 潜在反驳：\n"
        f"> {payload['counterargument']}\n"
        ">\n"
        "> 我的最终判断：\n"
        f"> {payload['judgment']}\n"
        ">\n"
        "> 可信度：\n"
        "> medium"
    )


def build_q2_question(payload: dict[str, object]) -> str:
    return (
        "> [!question|q2] Q2 这篇文章的核心论点 / 主张是什么？\n"
        "> question_title: 核心主张\n"
        "> question_note: 首版批量补全，待回原文加段号与精确引文。\n"
        "> linked_quotes: [[#Q2 深答区]]\n"
        ">\n"
        f"> short_answer: {payload['q2_short']}\n"
        f"> deep_answer: {payload['q2_deep']}\n"
        f"> limitation_or_counterargument: {payload['counterargument']}"
    )


def fill_note(note_path: Path, payload: dict[str, object]) -> None:
    raw = note_path.read_text(encoding="utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")

    title_en_match = re.search(r'^title_en: "(.*)"$', text, re.MULTILINE)
    short_title_match = re.search(r'^short_title: "(.*)"$', text, re.MULTILINE)
    citation_title_match = re.search(r'^citation_title: "(.*)"$', text, re.MULTILINE)
    if not (title_en_match and short_title_match and citation_title_match):
        raise ValueError(f"Missing title metadata in {note_path}")

    title_en = title_en_match.group(1)
    short_title = short_title_match.group(1)
    citation_title = citation_title_match.group(1)

    text = replace_yaml_value(text, "title_zh", payload["title_zh"])
    text = replace_yaml_value(text, "updated", UPDATED_AT)

    text = re.sub(
        r"(?s)\A(---\n.*?\n---\n\n)# .*?\n\n## ",
        lambda m: f"{m.group(1)}# {payload['title_zh']}\n\n## ",
        text,
        count=1,
    )

    translation_block = build_translation_block(payload, title_en, short_title, citation_title)
    text = re.sub(
        r"(?s)> \[!translation\]\n.*?(?=\n\n> \[!info\])",
        translation_block,
        text,
        count=1,
    )

    q2_focus = build_q2_focus(payload)
    text = re.sub(
        r"(?s)# Q2 深答区\n\n> \[!q2-focus\]\n.*?(?=\n# 用户提出的问题)",
        q2_focus,
        text,
        count=1,
    )

    q2_question = build_q2_question(payload)
    text = re.sub(
        r"(?s)> \[!question\|q2\] Q2 这篇文章的核心论点 / 主张是什么？\n.*?(?=\n> \[!question\|q3\])",
        q2_question,
        text,
        count=1,
    )

    note_path.write_text(text.replace("\n", newline), encoding="utf-8")


def main() -> None:
    for filename, payload in PAPER_UPDATES.items():
        note_path = PAPERS_DIR / filename
        if not note_path.exists():
            raise FileNotFoundError(note_path)
        fill_note(note_path, payload)
        print(f"Updated: {note_path}")


if __name__ == "__main__":
    main()
