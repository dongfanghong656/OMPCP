from __future__ import annotations

from pathlib import Path


VAULT = Path(
    r"C:\Users\1\OneDrive - fzu.edu.cn (1)\Attachments\OCT_Research_System\oct-research-assist\vault"
)
DOCS_DIR = VAULT / "00_System" / "05_Docs"
VIEWS_DIR = VAULT / "00_System" / "02_Views"
HOME_PATH = VAULT / "00_System" / "00_Dashboard" / "Academic Reading Home.md"
QUESTIONS_DASHBOARD_PATH = VIEWS_DIR / "Questions Dashboard.md"
RESEARCH_QUESTION_TEMPLATE = VAULT / "00_System" / "01_Templates" / "Research Question.md"
METHOD_REGISTRY_PATH = DOCS_DIR / "Method Type Registry.md"
METHOD_NAVIGATION_PATH = VIEWS_DIR / "Method Navigation.md"


METHOD_REGISTRY = """---
cssclasses:
  - dashboard-view
---

# Method Type Registry

> [!info]
> 这页是 `research-question` frontmatter 里 `method_type` 的唯一命名基准。
> 新问题页优先复用这里的值，不要临时发明近义词。

## 使用规则

1. 一个问题页只填一个 `method_type`，写主方法，不写并列长串。
2. 次级差异放进 `tags`、`related_concepts` 或正文，不要挤进 `method_type`。
3. 只有当同一新类型连续出现至少 2 个高价值问题时，再考虑新增枚举。
4. 如果必须新增，先更新这页，再回填旧问题页和 Dashboard。
5. 方法类型尽量写成“方法族 / 工程环节”，不要写临时口号式名称。

## 当前统一枚举

| method_type | 适用范围 | 常见关键词 | 典型问题页 | 边界提醒 |
| --- | --- | --- | --- | --- |
| 超分辨与伪影控制 | 关注“能否增强而不引入伪影” | superresolution, artifact-free, ringing | [[Question - Artifact-Free Superresolution Criteria]] | 如果重点转到具体反卷积稳定性，改用 `盲反卷积` 或 `反卷积验证` |
| 盲反卷积 | 关注 blind / semi-blind 路线的稳定性与可解释性 | blind deconvolution, identifiability, stability | [[Question - Blind Deconvolution Stability in OCT]] | 如果重点是局部核迁移或 PSF 参数化，优先用 `PSF 建模` |
| 综述综合 | 用于 field map、瓶颈盘点与路线综述 | review, bottleneck, roadmap | [[Question - Deconvolution Bottlenecks in OCT]] | 不要把具体算法问题也塞进这一类 |
| 色散与延迟线 | 关注延迟线、色散、相位误差和深度性能 | dispersion, delay line, phase error | [[Question - Dispersion and Delay-Line Penalties in OCT]] | 如果重点转到扫描执行机构本身，改用 `扫描机构` |
| 扫描机构 | 关注高速扫描、偏转、执行器迟滞与线性 | scanner, actuator, hysteresis, linearity | [[Question - Fast Scanning Mechanism Limits in OCT]] | 不含频域采样架构本身，后者用 `频域架构` |
| 频域架构 | 关注 Fourier / spectral-domain 路线的系统收益与代价 | Fourier-domain, spectral-domain, SNR, system cost | [[Question - Fourier Domain Gains vs System Cost]] | 如果问题转成采样速度与显示负担，改用 `高速采集` |
| 反卷积验证 | 关注“提升是否真的成立”的评价、对照和证据标准 | validation, lateral resolution, task-based evaluation | [[Question - Lateral Resolution Gain Limits]] | 如果重点是无伪影超分辨标准，可用 `超分辨与伪影控制` |
| PSF 建模 | 关注局部 PSF、空间变异和核迁移问题 | PSF, local kernel, transferability | [[Question - Local PSF Transferability]] | 如果已经进入 blind 估计本身的稳定性，改用 `盲反卷积` |
| 系统工程 | 关注实用化、集成、成本和部署瓶颈 | practicalization, integration, cost-performance | [[Question - OCT Practicalization Bottlenecks]] | 不要拿它替代具体系统子模块分析 |
| 基线评估 | 关注 baseline、benchmark、均匀性和系统对照 | benchmark, uniformity, baseline | [[Question - Resolution Uniformity as Baseline]] | 如果重点是单一增强方法是否成立，改用相应方法类 |
| 高速采集 | 关注 A-line rate、实时显示、灵敏度和数据负担权衡 | high-speed OCT, A-line rate, real-time display | [[Question - Speed Sensitivity Tradeoff in High-Speed OCT]] | 不等同于频域架构本身，它更偏运行条件与系统负载 |
| 时频处理 | 关注 Wigner-Ville、重分配和时频锐化解释 | Wigner-Ville, reassignment, time-frequency | [[Question - Wigner-Ville Gain Interpretation]] | 不要和反卷积路线混写成同一类结论 |

## 当前使用情况

```dataview
TABLE file.link AS "问题页", method_type AS "方法类型", status AS "状态", related_concepts AS "概念"
FROM "04_Research/Questions"
WHERE type = "research-question" AND method_type
SORT method_type ASC, file.name ASC
```
"""


METHOD_NAVIGATION = """---
cssclasses:
  - dashboard-view
---

# Method Navigation

> [!info]
> 这页把 `方法类型 -> 问题 -> 概念 -> 论文` 串起来，方便从研究母题往下钻到具体资料。
> `method_type` 的命名请以 [[00_System/05_Docs/Method Type Registry|Method Type Registry]] 为准。

## 方法类型 -> 问题 -> 概念 -> 论文

```dataview
TABLE WITHOUT ID
  method_type AS "方法类型",
  file.link AS "问题页",
  related_concepts AS "概念",
  related_papers AS "论文",
  status AS "状态"
FROM "04_Research/Questions"
WHERE type = "research-question" AND method_type
SORT method_type ASC, importance DESC, file.name ASC
```

## 按方法类型折叠浏览

```dataview
TABLE rows.file.link AS "问题页", rows.related_concepts AS "概念", rows.related_papers AS "论文"
FROM "04_Research/Questions"
WHERE type = "research-question" AND method_type
GROUP BY method_type
SORT key ASC
```

## 概念 -> 问题 -> 方法类型 -> 论文

> [!concept]
> 这一栏是从 Concepts 反查到 Questions 的入口，适合你先从概念卡出发，再回到具体研究问题。

```dataview
TABLE rows.method_type AS "方法类型", rows.file.link AS "问题页", rows.related_papers AS "论文"
FROM "04_Research/Questions"
FLATTEN related_concepts AS concept
WHERE type = "research-question" AND concept
GROUP BY concept
SORT key ASC
```
"""


QUESTIONS_DASHBOARD_TIP = """
> [!tip]
> `method_type` 命名请统一参考 [[00_System/05_Docs/Method Type Registry|Method Type Registry]]；
> 跨层导航请使用 [[00_System/02_Views/Method Navigation|Method Navigation]]。
"""


TEMPLATE_TIP = """
> [!info]
> `method_type` 请直接复用 [[00_System/05_Docs/Method Type Registry|Method Type Registry]] 里的枚举值。
> 如果一个问题跨多个方法，`method_type` 写主方法，其余差异放进 `tags`、`related_concepts` 或正文。

"""


def write_file(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def ensure_question_dashboard_tip() -> None:
    text = QUESTIONS_DASHBOARD_PATH.read_text(encoding="utf-8")
    if "Method Type Registry" in text and "Method Navigation" in text:
        return
    anchor = "## Bases 视图"
    if anchor not in text:
        raise ValueError("Questions Dashboard.md missing Bases section")
    text = text.replace(anchor, QUESTIONS_DASHBOARD_TIP + "\n" + anchor, 1)
    QUESTIONS_DASHBOARD_PATH.write_text(text, encoding="utf-8")


def ensure_home_links() -> None:
    text = HOME_PATH.read_text(encoding="utf-8")
    links = [
        "- [[00_System/02_Views/Method Navigation|方法导航面板]]",
        "- [[00_System/05_Docs/Method Type Registry|method_type 枚举说明]]",
    ]
    if all(link in text for link in links):
        return
    anchor = "- [[00_System/02_Views/Questions Dashboard|问题面板]]"
    replacement = (
        anchor
        + "\n- [[00_System/02_Views/Method Navigation|方法导航面板]]"
        + "\n- [[00_System/05_Docs/Method Type Registry|method_type 枚举说明]]"
    )
    if anchor not in text:
        raise ValueError("Academic Reading Home.md missing Questions Dashboard quick link")
    text = text.replace(anchor, replacement, 1)
    HOME_PATH.write_text(text, encoding="utf-8")


def ensure_template_tip() -> None:
    text = RESEARCH_QUESTION_TEMPLATE.read_text(encoding="utf-8")
    if "Method Type Registry" in text:
        return
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Research Question template missing frontmatter")
    rebuilt = "---".join(parts[:2]) + "---\n\n" + TEMPLATE_TIP + parts[2].lstrip("\n")
    RESEARCH_QUESTION_TEMPLATE.write_text(rebuilt, encoding="utf-8")


def main() -> None:
    write_file(METHOD_REGISTRY_PATH, METHOD_REGISTRY)
    write_file(METHOD_NAVIGATION_PATH, METHOD_NAVIGATION)
    ensure_question_dashboard_tip()
    ensure_home_links()
    ensure_template_tip()


if __name__ == "__main__":
    main()
