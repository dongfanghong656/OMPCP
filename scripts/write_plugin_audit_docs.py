from __future__ import annotations

from pathlib import Path
from textwrap import dedent


VAULT_ROOT = Path(
    r"C:\Users\1\OneDrive - fzu.edu.cn (1)\Attachments\OCT_Research_System\oct-research-assist\vault"
)


AUDIT_DOC = dedent(
    """\
    ---
    cssclasses:
      - dashboard-view
    ---

    # Plugin Audit - 2026-03-23

    > [!info]
    > 这份文档记录的不是“理想配置”，而是当前真实 vault 的实际状态。

    ## 当前已启用的核心插件

    - `Properties`
    - `Templates`
    - `Bases`
    - `Canvas`
    - `Search`
    - `Backlinks`
    - `Page Preview`
    - `Outline`
    - `Bookmarks`
    - `Daily Notes`
    - `File Recovery`
    - `Sync`

    ## 当前未启用或未发现的内容

    - 没有检测到 `.obsidian/community-plugins.json`
    - 这意味着当前 vault 还没有正式启用任何社区插件
    - 目前这套阅读系统必须以核心插件工作为前提，不能把关键功能押在社区插件上

    ## 当前已经确认可用的视觉层

    - `vault-theme-academic`
    - `vault-callouts`
    - `vault-paper-layout`
    - `vault-dashboard`
    - `vault-mobile`

    ## 这份状态说明了什么

    > [!thesis]
    > 当前最稳的路线不是“继续补插件”，而是先把结构、模板、检索和样式都建立在核心能力上。

    - 文献模板、Q2 深答区、双语标题、段落批注和导出模板都已经不依赖社区插件
    - 仪表盘层已经补成 `Bases-first`
    - `Dataview` 和 `Templater` 现在适合做增强层，而不是前提条件

    ## 当前还存在的能力边界

    - `Bases` 很适合 frontmatter 列表检索，但不擅长跨笔记扁平化正文里的 inline fields
    - 所以“所有 open / pending 的用户问题”这类聚合，目前还是 `Dataview` 更强
    - 核心 `Templates` 可以插模板，但不会像 `Templater` 那样自动命名、自动填时间和执行逻辑

    ## 推荐的升级顺序

    1. 先继续使用现在这套核心插件方案写内容
    2. 如果你开始频繁看全局问题面板，再装 `Dataview`
    3. 如果你开始频繁批量新建论文或课程笔记，再装 `Templater`
    4. 不建议继续引入重型数据库类插件或会破坏 Markdown 可读性的插件
    """
)


COMMUNITY_DOC = dedent(
    """\
    ---
    cssclasses:
      - dashboard-view
    ---

    # Optional Community Plugins

    > [!question|q2]
    > 下面不是“现在必须装什么”，而是“什么时候值得装”。

    ## Dataview 什么时候值得装

    当你出现下面任意一种需求时，就值得装：

    - 想把文献正文中的 `question_id::`、`status::` 这类 inline fields 跨页汇总
    - 想做更复杂的 `Q2 未完成`、`用户问题 open/pending`、`跨课程过滤` 面板
    - 想把 `02_Literature/Papers`、`04_Research/Questions`、`05_Reading-Logs` 做联合查询

    Dataview 的优点：

    - 聚合强
    - 过滤强
    - 很适合研究型知识库

    Dataview 的代价：

    - 新设备上需要重新安装
    - 查询本身需要维护
    - 写坏查询时，页面容易看起来像“坏了”

    ## Templater 什么时候值得装

    当你出现下面任意一种需求时，就值得装：

    - 新建论文时想自动按 `[Year] FirstAuthor - Short Title` 命名
    - 想自动填 `created`、`updated`、`year`、`citation_key`
    - 想按目录自动套不同模板
    - 想用脚本把元数据写回 frontmatter

    Templater 的优点：

    - 自动化强
    - 非常适合频繁建新笔记
    - 可以把重复输入降到最低

    Templater 的代价：

    - 配置复杂度高于核心 `Templates`
    - 变量和脚本一多，长期维护成本会上升
    - 不如纯 Markdown 模板那样“看一眼就懂”

    ## 推荐接法

    > [!method]
    > 最稳的做法不是二选一，而是分层接入。

    - 默认写作层继续用 `Properties + Templates + Bases + Callouts + CSS snippets`
    - 装 `Dataview` 后，只把它用于聚合页，不让正文依赖它
    - 装 `Templater` 后，只把它用于“新建时自动化”，不让正文可读性依赖它

    ## 最小接入原则

    1. 先装 `Dataview`，只验证 `Questions Dashboard.md` 底部查询是否能跑
    2. 再装 `Templater`，只做新建命名和时间戳，不急着上复杂脚本
    3. 每加一个插件，都要保证“不装时主笔记仍然可读”
    """
)


def append_link_once(path: Path, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    if block.strip() in text:
        return
    text = text.rstrip() + "\n\n" + block.strip() + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    audit_path = VAULT_ROOT / "00_System/05_Docs/Plugin Audit - 2026-03-23.md"
    community_path = VAULT_ROOT / "00_System/05_Docs/Optional Community Plugins.md"

    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(AUDIT_DOC, encoding="utf-8", newline="\n")
    community_path.write_text(COMMUNITY_DOC, encoding="utf-8", newline="\n")

    home_path = VAULT_ROOT / "00_System/00_Dashboard/Academic Reading Home.md"
    readme_path = VAULT_ROOT / "00_System/05_Docs/README.md"

    append_link_once(
        home_path,
        dedent(
            """\
            ## 插件补充文档

            - [[00_System/05_Docs/Plugin Audit - 2026-03-23|真实插件审计]]
            - [[00_System/05_Docs/Optional Community Plugins|可选社区插件接入说明]]
            """
        ),
    )

    append_link_once(
        readme_path,
        dedent(
            """\
            ## 补充文档

            - [[00_System/05_Docs/Plugin Strategy Review|插件策略评估]]
            - [[00_System/05_Docs/Plugin Audit - 2026-03-23|真实插件审计]]
            - [[00_System/05_Docs/Optional Community Plugins|可选社区插件接入说明]]
            """
        ),
    )

    print(f"Wrote: {audit_path}")
    print(f"Wrote: {community_path}")
    print(f"Updated links in: {home_path}")
    print(f"Updated links in: {readme_path}")


if __name__ == "__main__":
    main()
