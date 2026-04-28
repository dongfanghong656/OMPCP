from __future__ import annotations

import re
from pathlib import Path

import yaml


VAULT_ROOT = Path(
    r"C:\Users\1\OneDrive - fzu.edu.cn (1)\Attachments\OCT_Research_System\oct-research-assist\vault"
)
PAPERS_DIR = VAULT_ROOT / "02_Literature" / "Papers"
UPDATED_AT = "2026-03-23 17:20:00"


PAPER_UPDATES = {
    "[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography.md": {
        "title": "Deconvolution Techniques in Optical Coherence Tomography: Advancements, Challenges, and Future Prospects",
        "title_en": "Deconvolution Techniques in Optical Coherence Tomography: Advancements, Challenges, and Future Prospects",
        "title_original": "Deconvolution Techniques in Optical Coherence Tomography: Advancements, Challenges, and Future Prospects",
        "title_display": "Deconvolution Techniques in Optical Coherence Tomography: Advancements, Challenges, and Future Prospects",
        "title_zh": "光学相干断层扫描中的反卷积技术：进展、挑战与未来展望",
        "short_title": "Deconvolution Techniques in OCT Review",
        "citation_title": "Syeda Aimen Abbasi et al., 2025",
        "citation_key": "syeda-aimen-abbasi-2025-deconvolution-techniques-in-optical-coherence-tomography-advancements-challenges-and-future-prospects",
        "authors": [
            "Syeda Aimen Abbasi",
            "Di Mei",
            "Yuanyuan Wei",
            "Chao Xu",
            "Syed Muhammad Tariq Abbasi",
            "Sadia Shakil",
            "Wu Yuan",
        ],
        "year": 2025,
        "venue": "Laser and Photonics Reviews",
        "doi": "10.1002/lpor.202401394",
        "url": "https://doi.org/10.1002/lpor.202401394",
        "translation_keywords": [
            "deconvolution: 反卷积 / 去卷积",
            "advancements: 进展",
            "challenges: 挑战、瓶颈",
            "future prospects: 未来展望",
        ],
        "translation_direct": "光学相干断层扫描中的反卷积技术：进展、挑战与未来展望",
        "translation_free": "OCT 反卷积技术的进展、挑战与未来方向",
        "translation_rationale": "完整保留综述的三层结构，方便作为 related-work 总纲引用。",
        "q2_short": "这篇综述的核心主张是：OCT 反卷积已经形成多条技术路线，但该领域仍缺少统一综述与统一评价框架，而鲁棒性、计算复杂度和临床验证仍是关键瓶颈。",
        "q2_deep": "作者并不是在为某一种反卷积方法站台，而是在重新定义这条研究线的成熟度标准。文章一方面指出，OCT 反卷积已经积累了足够多的方法工作，值得系统梳理；另一方面又明确强调，真正阻碍临床落地的并不是“有没有更锐利的图”，而是鲁棒优化、计算代价、验证规范与多方法协同仍未被解决。对你的项目来说，这篇文献最重要的作用是给研究动机和讨论部分提供总框架：它支持你把 measured-PSF、artifact-aware evaluation 和 phantom-led validation 写成必要补位，而不是重复已有方法展示。",
        "quotes": [
            {
                "id": "p01",
                "location": "Abstract ¶1",
                "quote": "Despite progress, a comprehensive review of these techniques in the OCT field is lacking.",
                "why": "说明文章首先把自己定位成“综述缺口”的回应。",
            },
            {
                "id": "p02",
                "location": "Abstract ¶2",
                "quote": "This review examines the current state of deconvolution strategies to overcome the PSF-induced blurring.",
                "why": "直接界定了文章的核心任务是梳理 PSF-induced blurring 的应对路线。",
            },
            {
                "id": "p03",
                "location": "Abstract ¶3",
                "quote": "challenges remain in real-time clinical imaging, including optimization robustness and balancing accuracy with computational complexity.",
                "why": "明确把未解决问题落在鲁棒性与复杂度权衡上。",
            },
        ],
        "counterargument": "作为综述，它能搭建问题地图，却不能替代统一 benchmark。不同路线并未在相同数据、相同 artifact 标准和相同计算预算下直接对比。",
        "judgment": "这篇文献最适合作为总论和讨论骨架。后续凡是你要强调“为什么还要做 measured-PSF 与验证链”，都可以把它当成总纲依据。",
    },
    "[2022] Dong - Spatially adaptive blind deconvolution methods for.md": {
        "title": "Spatially adaptive blind deconvolution methods for optical coherence tomography",
        "title_en": "Spatially adaptive blind deconvolution methods for optical coherence tomography",
        "title_original": "Spatially adaptive blind deconvolution methods for optical coherence tomography",
        "title_display": "Spatially adaptive blind deconvolution methods for optical coherence tomography",
        "title_zh": "用于光学相干断层扫描的空间自适应盲反卷积方法",
        "short_title": "Spatially adaptive blind deconvolution",
        "citation_title": "Wenxue Dong et al., 2022",
        "citation_key": "wenxue-dong-2022-spatially-adaptive-blind-deconvolution-methods-for-optical-coherence-tomography",
        "authors": [
            "Wenxue Dong",
            "Yina Du",
            "Jingjiang Xu",
            "Feng Dong",
            "Shangjie Ren",
        ],
        "year": 2022,
        "venue": "Computers in Biology and Medicine",
        "doi": "10.1016/j.compbiomed.2022.105650",
        "url": "https://doi.org/10.1016/j.compbiomed.2022.105650",
        "translation_keywords": [
            "spatially adaptive: 空间自适应",
            "blind deconvolution: 盲反卷积 / 半盲反卷积",
            "depth-dependent PSF: 深度相关 PSF",
        ],
        "translation_direct": "用于光学相干断层扫描的空间自适应盲反卷积方法",
        "translation_free": "面向 OCT 的空间变化 PSF 盲反卷积方法",
        "translation_rationale": "突出空间变化 PSF 与 blind deconvolution 的联合建模含义。",
        "q2_short": "这篇文章的核心主张是：OCT 的模糊核随成像深度变化，不能再假定已知固定 PSF，而应把深度相关 PSF 与清晰图像放进同一 blind deconvolution 框架联合估计。",
        "q2_deep": "这篇文章真正推进的不是“再做一次 Richardson-Lucy”，而是把 OCT 去模糊问题重新定义成 space-variant PSF 的联合恢复问题。作者明确指出，传统数字反卷积依赖已知 PSF，但在 OCT 里 PSF 会随成像深度变化而且很难精确测得，因此合理路线不是继续假装核已知，而是通过 Gaussian beam 建模、正则化能量函数和交替优化把 PSF 与图像一起估计出来。对你的项目而言，这篇文献的重要性在于它提供了 measured-PSF 非盲路线的直接对照项：如果你要说明真实测得 PSF 更可靠，就必须回答它所代表的 blind / semi-blind 路线为什么不够好。",
        "quotes": [
            {
                "id": "p01",
                "location": "Abstract ¶2",
                "quote": "the point spread function (PSF), which varies with the imaging depth and is difficult to determine.",
                "why": "点明作者为何拒绝固定核假设。",
            },
            {
                "id": "p02",
                "location": "Abstract ¶2",
                "quote": "a spatially adaptive blind deconvolution framework is proposed for recovering clear OCT images from blurred images without a known PSF.",
                "why": "这是文章最直接的主张句。",
            },
            {
                "id": "p03",
                "location": "Abstract ¶3",
                "quote": "an accelerated alternating optimization method is proposed based on the convolution theorem and Fourier transform.",
                "why": "说明作者同时把可计算性纳入主张，而非只谈概念正确。",
            },
        ],
        "counterargument": "该框架仍高度依赖 Gaussian beam 对真实 PSF 的拟合能力。若系统存在明显离轴像差、旁瓣或复杂畸变，图像更清晰也不等于模型更真。",
        "judgment": "它是 classical blind-deconvolution baseline 里的强对照。后续 measured-PSF 路线若要成立，必须在评价与解释层面赢过它。",
    },
    "[2014] Unknown - Variations in optical coherence tomography resolution.md": {
        "title": "Variations in optical coherence tomography resolution and uniformity: a multi-system performance comparison",
        "title_en": "Variations in optical coherence tomography resolution and uniformity: a multi-system performance comparison",
        "title_original": "Variations in optical coherence tomography resolution and uniformity: a multi-system performance comparison",
        "title_display": "Variations in optical coherence tomography resolution and uniformity: a multi-system performance comparison",
        "title_zh": "光学相干断层扫描分辨率与均匀性的变化：多系统性能比较",
        "short_title": "OCT resolution and uniformity comparison",
        "citation_title": "Anthony Fouad et al., 2014",
        "citation_key": "anthony-fouad-2014-variations-in-optical-coherence-tomography-resolution-and-uniformity-a-multi-system-performance-comparison",
        "authors": [
            "Anthony Fouad",
            "T. Joshua Pfefer",
            "Chao-Wei Chen",
            "Wei Gong",
            "Anant Agrawal",
            "Peter H. Tomlins",
            "Peter D. Woolliams",
            "Rebekah A. Drezek",
            "Yu Chen",
        ],
        "year": 2014,
        "venue": "Biomedical Optics Express",
        "doi": "10.1364/BOE.5.002066",
        "url": "https://doi.org/10.1364/BOE.5.002066",
        "translation_keywords": [
            "resolution and uniformity: 分辨率与均匀性",
            "multi-system comparison: 多系统比较",
            "PSF phantom: PSF 体模",
        ],
        "translation_direct": "光学相干断层扫描分辨率与均匀性的变化：多系统性能比较",
        "translation_free": "OCT 分辨率与均匀性变化的多系统性能比较",
        "translation_rationale": "完整保留 benchmarking 语义，方便纳入评价链文献。",
        "q2_short": "这篇文章的核心主张是：要讨论 OCT 分辨率提升，必须先用 PSF 体模建立客观、可量化、可跨系统比较的测试方法，否则任何“提升”都缺少可靠基线。",
        "q2_deep": "文章的主张不在于提出一种新算法，而在于重建“什么叫可信的 OCT 分辨率评价”。作者把 PSF phantom 明确写成标准化测试方法的候选方案，强调只有当不同系统在不同空间位置上的分辨率和信号均匀性被一致测量之后，关于系统性能的讨论才有可比性。对你的项目来说，这篇文献极其关键，因为它直接支持你把 phantom-based validation、field dependence 和 signal uniformity 写进主评价链，而不是只展示少数代表性图像。",
        "quotes": [
            {
                "id": "p01",
                "location": "Abstract ¶1",
                "quote": "Measurements based on PSF phantoms have the potential to become a standard test method.",
                "why": "这是文章最核心的 benchmark 主张。",
            },
            {
                "id": "p02",
                "location": "Abstract ¶1",
                "quote": "Significant system-to-system differences in resolution and signal intensity and their spatial variation were readily quantified.",
                "why": "说明作者关心的是跨系统、跨位置可量化比较。",
            },
            {
                "id": "p03",
                "location": "Abstract ¶1",
                "quote": "Our multi-system results provide evidence of the practical utility of PSF-phantom-based test methods.",
                "why": "直接给出作者的结论性判断。",
            },
        ],
        "counterargument": "它不能替你选择最优反卷积算法；它给的是评价地基，而不是恢复算子本身。",
        "judgment": "这篇文献非常适合放进“为什么必须做体模和统一评价”的核心论证段落里。",
    },
    "[2022] Unknown - Superresolving artifact-free optical coherence tomography with.md": {
        "title": "Deblurring, artifact-free optical coherence tomography with deconvolution-random phase modulation",
        "title_en": "Deblurring, artifact-free optical coherence tomography with deconvolution-random phase modulation",
        "title_original": "Deblurring, artifact-free optical coherence tomography with deconvolution-random phase modulation",
        "title_display": "Deblurring, artifact-free optical coherence tomography with deconvolution-random phase modulation",
        "title_zh": "基于反卷积-随机相位调制的无伪影去模糊光学相干断层扫描",
        "short_title": "Deblurring artifact-free OCT with Deconv-RPM",
        "citation_title": "Xin Ge et al., 2024",
        "citation_key": "xin-ge-2024-deblurring-artifact-free-optical-coherence-tomography-with-deconvolution-random-phase-modulation",
        "authors": [
            "Xin Ge",
            "Si Chen",
            "Kan Lin",
            "Guangming Ni",
            "En Bo",
            "Lulu Wang",
            "Linbo Liu",
        ],
        "year": 2024,
        "venue": "Opto-Electronic Science",
        "doi": "10.29026/oes.2024.230020",
        "url": "https://doi.org/10.29026/oes.2024.230020",
        "translation_keywords": [
            "deblurring: 去模糊",
            "artifact-free: 无伪影 / 伪影受控",
            "random phase modulation: 随机相位调制",
        ],
        "translation_direct": "基于反卷积-随机相位调制的去模糊、无伪影光学相干断层扫描",
        "translation_free": "基于反卷积-随机相位调制的无伪影去模糊光学相干断层扫描",
        "translation_rationale": "期刊版题名已从旧预印本的 superresolving 表述收敛到 deblurring，更准确地反映主张重点。",
        "version_note": "本地 legacy source 更接近预印本题名“Superresolving...”，当前元数据已对齐 2024 期刊版，文件名暂保留旧名。",
        "q2_short": "这篇文章的核心主张是：OCT 去模糊若只做反卷积，往往会被噪声诱发的振铃伪影破坏，因此必须把随机相位调制与反卷积联立，才能同时获得更清晰且更可信的结果。",
        "q2_deep": "这篇文章真正强调的不是单纯“分辨率更高”，而是把 artifact suppression 写成主张本身。作者先指出，OCT 中常规反卷积会因为噪声敏感性而引入 ringing artifacts，随后提出把 numerical random phase masks 融入 deconvolution 流程，通过联合操作实现去模糊与伪影控制。这样一来，文章的贡献就不只是图像更锐利，而是把“清晰度收益”和“伪影代价”绑定到同一个恢复框架里。对你的项目而言，它最重要的启发是：后续实验若只汇报 FWHM 缩小，而不汇报 artifact 代价，就还不够构成高质量论证。",
        "quotes": [
            {
                "id": "p01",
                "location": "Abstract ¶1",
                "quote": "its application in optical coherence tomography (OCT) is often hindered by sensitivity to noise, which leads to additive ringing artifacts.",
                "why": "先明确传统反卷积的失败模式。",
            },
            {
                "id": "p02",
                "location": "Abstract ¶1",
                "quote": "integrates numerical random phase masks into the deconvolution process, effectively eliminating these artifacts.",
                "why": "这是文章提出的新操作核心。",
            },
            {
                "id": "p03",
                "location": "Abstract ¶1",
                "quote": "enables a 2.5-fold reduction in full width at half-maximum (FWHM).",
                "why": "给出量化收益，但收益与 artifact-free 主张是绑定的。",
            },
        ],
        "counterargument": "收益到底来自更强的恢复，还是来自特定调制策略及其数据条件，仍需更细的拆解；而且这一流程的计算代价和平台可迁移性未必低。",
        "judgment": "它很适合作为“不能只看清晰度，还要看 artifact 代价”的关键旁证。对当前主线而言，更像评价准则的提醒器，而非第一优先级复现目标。",
    },
    "[2025] Unknown - Enhanced A-scan spatial resolution in spectral.md": {
        "title": "Enhanced A-scan spatial resolution in spectral domain OCT exploiting the Wigner-Ville technique",
        "title_en": "Enhanced A-scan spatial resolution in spectral domain OCT exploiting the Wigner-Ville technique",
        "title_original": "Enhanced A-scan spatial resolution in spectral domain OCT exploiting the Wigner-Ville technique",
        "title_display": "Enhanced A-scan spatial resolution in spectral domain OCT exploiting the Wigner-Ville technique",
        "title_zh": "利用 Wigner-Ville 技术增强频域 OCT 的 A-scan 空间分辨率",
        "short_title": "Wigner-Ville A-scan enhancement",
        "citation_title": "Naveen Kumar P et al., 2025",
        "citation_key": "naveen-kumar-p-2025-enhanced-a-scan-spatial-resolution-in-spectral-domain-oct-exploiting-the-wigner-ville-technique",
        "authors": [
            "Naveen Kumar P",
            "R. David Koilpillai",
            "Shanti Bhattacharya",
        ],
        "year": 2025,
        "venue": "Optics and Lasers in Engineering",
        "doi": "10.1016/j.optlaseng.2024.108736",
        "url": "https://doi.org/10.1016/j.optlaseng.2024.108736",
        "translation_keywords": [
            "A-scan spatial resolution: A-scan 空间分辨率",
            "spectral domain OCT: 频域 OCT",
            "Wigner-Ville technique: Wigner-Ville 时频分析方法",
        ],
        "translation_direct": "利用 Wigner-Ville 技术增强频域 OCT 的 A-scan 空间分辨率",
        "translation_free": "基于 Wigner-Ville 时频分析的频域 OCT A-scan 分辨率增强",
        "translation_rationale": "保留 A-scan 与 SD-OCT 场景，突出它属于时频分析增强路线。",
        "version_note": "旧资料 slug 含 wigner-distribution，当前元数据按期刊题名 Wigner-Ville technique 统一。",
        "q2_short": "这篇文章的核心主张是：FFT 对 SD-OCT 干涉信号的全局处理会漏掉局部频率结构，因此应使用 SPWVD 做局部时频分析，以获得更高的 A-scan 分辨率和更好的对比噪声表现。",
        "q2_deep": "作者不是在做横向去模糊，而是在重新定义 SD-OCT 轴向解析的计算上限。文章指出，传统 FFT 只能抽取全局频率内容，容易漏掉 closely spaced frequencies，并且在 A-scan 生成上只充分利用了 N/2 级别的信息表达。SPWVD 的作用就在于把 interferometric signal 当作局部非平稳信号来分析，从而把细粒度频率结构重新带回重建结果。对你的项目而言，这篇文章的价值主要体现在边界说明：它证明 OCT 的分辨率增强还有时频分析路线，但这并不自动等于横向 PSF 恢复问题已经被解决。",
        "quotes": [
            {
                "id": "p01",
                "location": "Abstract ¶2",
                "quote": "The process can potentially miss closely spaced frequencies.",
                "why": "直接指出 FFT 全局分析的不足。",
            },
            {
                "id": "p02",
                "location": "Abstract ¶3",
                "quote": "generates high resolution A-scans over N samples rather than N/2",
                "why": "这是作者最核心的机制性主张。",
            },
            {
                "id": "p03",
                "location": "Abstract ¶4",
                "quote": "The experimental results demonstrate a twofold increase in A-scan resolution.",
                "why": "给出最关键的实验收益结论。",
            },
        ],
        "counterargument": "这一路线解决的是 A-scan / 轴向局部解析，不是横向 PSF 恢复；而且计算代价与样本依赖性仍需进一步核验。",
        "judgment": "把它放在 related work 里作为“非反卷积增强路线”的代表最合适，用来衬托你当前横向主线的独立性。",
    },
    "[2025] Unknown - Enhanced A-scan spatial resolution in spectral -- enhanced-a-scan-spatial-resolution-in-spectral-domain-oct-exploiting-the-wigner-ville-technique.md": {
        "title": "Enhanced A-scan spatial resolution in spectral domain OCT exploiting the Wigner-Ville technique",
        "title_en": "Enhanced A-scan spatial resolution in spectral domain OCT exploiting the Wigner-Ville technique",
        "title_original": "Enhanced A-scan spatial resolution in spectral domain OCT exploiting the Wigner-Ville technique",
        "title_display": "Enhanced A-scan spatial resolution in spectral domain OCT exploiting the Wigner-Ville technique",
        "title_zh": "利用 Wigner-Ville 技术增强频域 OCT 的 A-scan 空间分辨率",
        "short_title": "Wigner-Ville A-scan enhancement",
        "citation_title": "Naveen Kumar P et al., 2025",
        "citation_key": "naveen-kumar-p-2025-enhanced-a-scan-spatial-resolution-in-spectral-domain-oct-exploiting-the-wigner-ville-technique",
        "authors": [
            "Naveen Kumar P",
            "R. David Koilpillai",
            "Shanti Bhattacharya",
        ],
        "year": 2025,
        "venue": "Optics and Lasers in Engineering",
        "doi": "10.1016/j.optlaseng.2024.108736",
        "url": "https://doi.org/10.1016/j.optlaseng.2024.108736",
        "translation_keywords": [
            "A-scan spatial resolution: A-scan 空间分辨率",
            "spectral domain OCT: 频域 OCT",
            "Wigner-Ville technique: Wigner-Ville 时频分析方法",
        ],
        "translation_direct": "利用 Wigner-Ville 技术增强频域 OCT 的 A-scan 空间分辨率",
        "translation_free": "基于 Wigner-Ville 时频分析的频域 OCT A-scan 分辨率增强",
        "translation_rationale": "维持与期刊题名一致，便于后续去重与统一索引。",
        "q2_short": "这篇文章的核心主张是：SD-OCT 不应只依赖 FFT 这一种全局频率提取方式，而应利用 Wigner-Ville 类时频分析捕捉局部结构信息，从而增强 A-scan 解析能力。",
        "q2_deep": "从论证结构看，作者并不是在讨论横向 PSF 的恢复，而是在论证 FFT 为什么不足以榨干 SD-OCT 干涉信号中的局部频率信息。文章把 SPWVD 作为关键工具，主张其能在 N 个样本上生成更高分辨率的 A-scan 表达，并在实验上得到比 FFT 更好的分层解析和对比噪声表现。对你的研究而言，这篇文献的主要意义是当作 scope boundary：它能帮助你回答“为什么别的增强路线不能直接替代当前横向主线”，但不应被误读成你当前问题已经被别人解决。",
        "quotes": [
            {
                "id": "p01",
                "location": "Abstract ¶2",
                "quote": "The process can potentially miss closely spaced frequencies.",
                "why": "点明作者为什么不满足于 FFT。",
            },
            {
                "id": "p02",
                "location": "Abstract ¶3",
                "quote": "generates high resolution A-scans over N samples rather than N/2",
                "why": "这是方法核心机制句。",
            },
            {
                "id": "p03",
                "location": "Abstract ¶4",
                "quote": "The B-scan images processed with the proposed method also show improved contrast to noise ratio.",
                "why": "补充说明收益不仅是分辨率，还有成像对比表现。",
            },
        ],
        "counterargument": "它与当前横向分辨率主线仍然主题错位，且时频方法的计算代价与信号依赖性可能限制实际优先级。",
        "judgment": "把它作为边界文献和答辩回应材料很合适，但真正需要继续深挖的仍是横向 PSF 建模、反卷积比较和验证链。",
    },
}


def parse_note(note_path: Path) -> tuple[dict, str, str]:
    raw = note_path.read_text(encoding="utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        raise ValueError(f"Missing frontmatter: {note_path}")
    _, fm_text, body = text.split("---", 2)
    metadata = yaml.safe_load(fm_text) or {}
    return metadata, body.lstrip("\n"), newline


def dump_note(metadata: dict, body: str, newline: str) -> str:
    fm = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False, default_flow_style=False).strip()
    return f"---\n{fm}\n---\n\n{body}".replace("\n", newline)


def replace_block(body: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(pattern, replacement, body, count=1, flags=re.S)
    if count != 1:
        raise ValueError(f"Pattern not found: {pattern}")
    return updated


def build_translation_block(data: dict) -> str:
    keyword_lines = "\n".join(f"> - {item}" for item in data["translation_keywords"])
    version_line = ""
    if data.get("version_note"):
        version_line = f"\n> - 版本说明：{data['version_note']}"
    return (
        "> [!translation]\n"
        f"> 原始标题：{data['title_original']}\n"
        f"> 英文标题：{data['title_en']}\n"
        f"> 中文标题：{data['title_zh']}\n"
        f"> short title：{data['short_title']}\n"
        f"> citation title：{data['citation_title']}\n"
        ">\n"
        "> 关键词拆解：\n"
        f"{keyword_lines}\n"
        ">\n"
        "> 标题翻译说明：\n"
        f"> - 直译：{data['translation_direct']}\n"
        f"> - 意译：{data['translation_free']}\n"
        f"> - 采用当前译名的原因：{data['translation_rationale']}{version_line}"
    )


def build_info_block(metadata: dict) -> str:
    authors = ", ".join(metadata.get("authors", [])) or "TBD"
    tags = ", ".join(metadata.get("tags", []))
    return (
        "> [!info]\n"
        f"> 作者：{authors}\n"
        f"> 年份：{metadata.get('year', '')}\n"
        f"> 期刊 / 会议：{metadata.get('venue', '')}\n"
        f"> DOI：{metadata.get('doi', '')}\n"
        f"> URL：{metadata.get('url', '')}\n"
        f"> 课程：{metadata.get('course', '')}\n"
        f"> Week：{metadata.get('week', '')}\n"
        f"> 状态：{metadata.get('status', '')}\n"
        f"> 阅读阶段：{metadata.get('reading_stage', '')}\n"
        f"> 模式：{metadata.get('question_mode', '')} / sourced\n"
        f"> 标签：{tags}"
    )


def build_citation_block(metadata: dict) -> str:
    return (
        "> [!citation]\n"
        f"> Citation Key：{metadata.get('citation_key', '')}\n"
        f"> Legacy Source Note：{metadata.get('legacy_source_note', '')}\n"
        f"> Source Tag：{metadata.get('source_tag', '')}\n"
        f"> Source PDF：{metadata.get('source_pdf', '')}"
    )


def build_q2_block(data: dict) -> str:
    quote_lines = "\n".join(
        f'> - [{item["id"].upper()}] "{item["quote"]}"' for item in data["quotes"]
    )
    source_lines = "\n".join(
        f'> - {item["id"].upper()} -> {item["location"]}' for item in data["quotes"]
    )
    concept_lines = "\n".join(
        f"> - {item}"
        for item in {
            "PSF / 成像模型",
            "评价可信度",
            "方法边界与适用范围",
        }
    )
    q2_ids = ", ".join(item["id"] for item in data["quotes"])
    return (
        "# Q2 深答区\n\n"
        "> [!q2-focus]\n"
        "> Q2: 这篇文章的核心论点 / 主张是什么？\n"
        ">\n"
        "> q2_status:: sourced\n"
        "> q2_confidence:: medium\n"
        f"> q2_source_paragraphs:: {q2_ids}\n"
        ">\n"
        "> 精炼回答：\n"
        f"> {data['q2_short']}\n"
        ">\n"
        "> 分析回答：\n"
        f"> {data['q2_deep']}\n"
        ">\n"
        "> 支持摘录：\n"
        f"{quote_lines}\n"
        ">\n"
        "> 原文出处：\n"
        f"{source_lines}\n"
        ">\n"
        "> 依赖概念：\n"
        f"{concept_lines}\n"
        ">\n"
        "> 潜在反驳：\n"
        f"> {data['counterargument']}\n"
        ">\n"
        "> 我的最终判断：\n"
        f"> {data['judgment']}\n"
        ">\n"
        "> 可信度：\n"
        "> medium"
    )


def build_q2_question_block(data: dict) -> str:
    return (
        "> [!question|q2] Q2 这篇文章的核心论点 / 主张是什么？\n"
        "> question_title: 核心主张\n"
        "> question_note: 已升级为带精确引句与段号的正式版。\n"
        "> linked_quotes: [[#Q2 深答区]]\n"
        ">\n"
        f"> short_answer: {data['q2_short']}\n"
        f"> deep_answer: {data['q2_deep']}\n"
        f"> limitation_or_counterargument: {data['counterargument']}"
    )


def build_quote_table(data: dict) -> str:
    rows = [
        '| paragraph_id | Original Quote | Highlight | Linked Question | Why it matters |',
        '| --- | --- | --- | --- | --- |',
    ]
    for item in data["quotes"]:
        quote = item["quote"].replace("|", "\\|")
        why = item["why"].replace("|", "\\|")
        rows.append(
            f'| {item["id"]} | "{quote}" | `q2-focus` | Q2 | {why} |'
        )
    rows.append(
        '| legacy-note | Legacy content retained below | `legacy` | Q1, Q2, Q5, Q8, Q10 | 保留旧分析快照，便于回溯 |'
    )
    return "# 原文摘录与高亮索引\n\n" + "\n".join(rows)


def update_body(body: str, data: dict, metadata: dict) -> str:
    body = re.sub(
        r"^# .*\n\n## .*$",
        f"# {data['title_zh']}\n\n## {data['title_en']}",
        body,
        count=1,
        flags=re.M,
    )
    body = replace_block(body, r"> \[!translation\]\n.*?(?=\n\n> \[!info\])", build_translation_block(data))
    body = replace_block(body, r"> \[!info\]\n.*?(?=\n\n> \[!citation\])", build_info_block(metadata))
    body = replace_block(body, r"> \[!citation\]\n.*?(?=\n\n# 一句话总结)", build_citation_block(metadata))
    body = replace_block(body, r"# Q2 深答区\n\n> \[!q2-focus\]\n.*?(?=\n# 用户提出的问题)", build_q2_block(data))
    body = replace_block(
        body,
        r"> \[!question\|q2\] Q2 这篇文章的核心论点 / 主张是什么？\n.*?(?=\n> \[!question\|q3\])",
        build_q2_question_block(data),
    )
    body = replace_block(body, r"# 原文摘录与高亮索引\n\n.*?(?=\n# Related Notes)", build_quote_table(data))
    return body


def update_metadata(metadata: dict, data: dict) -> dict:
    metadata["type"] = "paper"
    metadata["title"] = data["title"]
    metadata["title_en"] = data["title_en"]
    metadata["title_zh"] = data["title_zh"]
    metadata["title_original"] = data["title_original"]
    metadata["title_display"] = data["title_display"]
    metadata["short_title"] = data["short_title"]
    metadata["citation_title"] = data["citation_title"]
    metadata["citation_key"] = data["citation_key"]
    metadata["authors"] = data["authors"]
    metadata["year"] = data["year"]
    metadata["venue"] = data["venue"]
    metadata["doi"] = data["doi"]
    metadata["url"] = data["url"]
    metadata["related_authors"] = data["authors"]
    metadata["q2_status"] = "sourced"
    metadata["q2_confidence"] = "medium"
    metadata["updated"] = UPDATED_AT
    return metadata


def main() -> None:
    for filename, data in PAPER_UPDATES.items():
        note_path = PAPERS_DIR / filename
        metadata, body, newline = parse_note(note_path)
        metadata = update_metadata(metadata, data)
        body = update_body(body, data, metadata)
        note_path.write_text(dump_note(metadata, body, newline), encoding="utf-8")
        print(f"Updated: {note_path}")


if __name__ == "__main__":
    main()
