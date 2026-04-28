from __future__ import annotations

from pathlib import Path
from textwrap import dedent


VAULT_ROOT = Path(
    r"C:\Users\1\OneDrive - fzu.edu.cn (1)\Attachments\OCT_Research_System\oct-research-assist\vault"
)


FILES: dict[str, str] = {
    "00_System/02_Views/Bases/Literature Dashboard.base": dedent(
        """\
        filters:
          and:
            - 'file.ext == "md"'
            - 'file.inFolder("02_Literature/Papers")'
            - 'type == "paper"'
        properties:
          file.name:
            displayName: 文件
          title_zh:
            displayName: 中文标题
          title_en:
            displayName: English Title
          year:
            displayName: 年份
          publication_type:
            displayName: 文献类型
          venue:
            displayName: 期刊 / 会议
          doi:
            displayName: DOI
          tags:
            displayName: 标签
          authors:
            displayName: 作者
          status:
            displayName: 状态
          reading_stage:
            displayName: 阅读阶段
          priority:
            displayName: 优先级
          rating:
            displayName: 评分
          course:
            displayName: 课程
          week:
            displayName: Week
          topics:
            displayName: 主题
        views:
          - type: table
            name: Library
            order:
              - file.name
              - title_zh
              - year
              - publication_type
              - venue
              - doi
              - tags
              - authors
              - status
              - reading_stage
              - priority
              - rating
          - type: table
            name: By Year
            groupBy:
              property: year
              direction: DESC
            order:
              - file.name
              - title_zh
              - venue
              - doi
              - publication_type
              - tags
              - status
              - reading_stage
          - type: table
            name: By Publication Type
            filters:
              - 'publication_type != null && publication_type != ""'
            groupBy:
              property: publication_type
              direction: ASC
            order:
              - file.name
              - title_zh
              - year
              - venue
              - doi
              - tags
              - status
          - type: table
            name: By Venue
            filters:
              - 'venue != null && venue != ""'
            groupBy:
              property: venue
              direction: ASC
            order:
              - file.name
              - title_zh
              - year
              - doi
              - tags
              - status
              - reading_stage
          - type: table
            name: By Tag
            filters:
              - 'tags != null && tags.length > 0'
            groupBy:
              property: tags
              direction: ASC
            order:
              - file.name
              - title_zh
              - year
              - venue
              - doi
              - status
          - type: table
            name: By Author
            filters:
              - 'authors != null && authors.length > 0'
            groupBy:
              property: authors
              direction: ASC
            order:
              - file.name
              - title_zh
              - year
              - venue
              - doi
              - tags
              - status
          - type: table
            name: Missing DOI
            filters:
              - 'doi == null || doi == ""'
            order:
              - file.name
              - title_zh
              - year
              - venue
              - tags
              - status
        """
    ),
    "00_System/02_Views/Bases/Reading Queue.base": dedent(
        """\
        filters:
          and:
            - 'file.ext == "md"'
            - 'file.inFolder("02_Literature/Papers")'
            - 'type == "paper"'
            - 'status == "to-read" || status == "reading"'
        properties:
          file.name:
            displayName: 文件
          title_zh:
            displayName: 中文标题
          title_en:
            displayName: English Title
          year:
            displayName: 年份
          status:
            displayName: 状态
          reading_stage:
            displayName: 阅读阶段
          priority:
            displayName: 优先级
          course:
            displayName: 课程
          topics:
            displayName: 主题
          q2_status:
            displayName: Q2 状态
        views:
          - type: table
            name: Queue
            groupBy:
              property: status
              direction: ASC
            order:
              - file.name
              - title_zh
              - year
              - reading_stage
              - priority
              - q2_status
              - course
              - topics
        """
    ),
    "00_System/02_Views/Bases/Questions Dashboard.base": dedent(
        """\
        filters:
          - 'file.ext == "md"'
        properties:
          file.name:
            displayName: 文件
          title_zh:
            displayName: 中文标题
          year:
            displayName: 年份
          status:
            displayName: 状态
          q2_status:
            displayName: Q2 状态
          q2_confidence:
            displayName: Q2 可信度
          course:
            displayName: 课程
          question:
            displayName: 研究问题
          importance:
            displayName: 重要性
          related_papers:
            displayName: 相关文献
          related_concepts:
            displayName: 相关概念
        views:
          - type: table
            name: Q2 Tracker
            filters:
              and:
                - 'file.inFolder("02_Literature/Papers")'
                - 'type == "paper"'
                - 'q2_status == null || q2_status != "complete"'
            groupBy:
              property: q2_status
              direction: ASC
            order:
              - file.name
              - title_zh
              - year
              - status
              - q2_confidence
              - course
          - type: table
            name: Research Question Notes
            filters:
              and:
                - 'file.inFolder("04_Research/Questions")'
                - 'type == "research-question"'
            groupBy:
              property: status
              direction: ASC
            order:
              - file.name
              - question
              - importance
              - related_papers
              - related_concepts
        """
    ),
    "00_System/02_Views/Bases/Concepts Map.base": dedent(
        """\
        filters:
          and:
            - 'file.ext == "md"'
            - 'file.inFolder("02_Literature/Concepts")'
            - 'type == "concept"'
        properties:
          file.name:
            displayName: 文件
          term:
            displayName: 术语
          term_en:
            displayName: English Term
          term_zh:
            displayName: 中文术语
          definition:
            displayName: 定义
          related_papers:
            displayName: 相关文献
          related_authors:
            displayName: 相关作者
          debates:
            displayName: 争议点
        views:
          - type: table
            name: Concepts
            order:
              - file.name
              - term_zh
              - term_en
              - definition
              - related_papers
              - debates
        """
    ),
    "00_System/02_Views/Bases/Authors Index.base": dedent(
        """\
        filters:
          and:
            - 'file.ext == "md"'
            - 'file.inFolder("02_Literature/Authors")'
            - 'type == "author"'
        properties:
          file.name:
            displayName: 文件
          name:
            displayName: Author
          name_zh:
            displayName: 中文名
          affiliation:
            displayName: 机构
          fields:
            displayName: 领域
          key_works:
            displayName: 代表作品
          core_claims:
            displayName: 核心观点
        views:
          - type: table
            name: Authors
            groupBy:
              property: affiliation
              direction: ASC
            order:
              - file.name
              - name_zh
              - name
              - fields
              - key_works
        """
    ),
    "00_System/02_Views/Bases/Course Overview.base": dedent(
        """\
        filters:
          and:
            - 'file.ext == "md"'
            - 'file.inFolder("03_Courses/Weekly")'
            - 'type == "course-week"'
        properties:
          file.name:
            displayName: 文件
          course:
            displayName: 课程
          week:
            displayName: Week
          theme:
            displayName: 主题
          required_readings:
            displayName: 必读
          optional_readings:
            displayName: 选读
          assignment:
            displayName: 作业
          discussion_questions:
            displayName: 讨论问题
        views:
          - type: table
            name: Courses
            groupBy:
              property: course
              direction: ASC
            order:
              - file.name
              - week
              - theme
              - required_readings
              - optional_readings
              - assignment
        """
    ),
    "00_System/05_Docs/Plugin Strategy Review.md": dedent(
        """\
        ---
        cssclasses:
          - dashboard-view
        ---

        # Plugin Strategy Review

        ## 结论先看

        > [!thesis]
        > 当前这版最合适的方向不是继续堆社区插件，而是明确分层：
        > 核心使用层以 `Properties + Templates + Bases + Callouts + CSS snippets` 为主，
        > `Dataview + Templater` 作为可选增强层。

        ## 这一版的优点

        - 核心层已经足够强，真实 vault 里 `Properties`、`Templates`、`Bases`、`Canvas`、`Search`、`Sync` 都可用。
        - 文献模板、Q2 深答区、中文标题、段落批注、导出样式已经都落在 Markdown 和 frontmatter 上，不被单一插件绑死。
        - CSS snippets 已经启用，视觉层和数据层分离，后续换主题或换插件都不会伤到内容。
        - `Bases` 是 Obsidian 官方核心能力，适合接当前这套列表检索、阅读队列、课程总览等表格型视图。

        ## 这一版的缺点

        - 文档最初是按 `Dataview + Templater` 假定写的，但真实 vault 里并没有安装社区插件，所以存在“设计存在、实际不工作”的落差。
        - `Bases` 很适合 frontmatter 检索，但不擅长像 Dataview 那样跨笔记扁平化抓正文里的 inline fields。
        - “用户提出的问题”写在文献正文列表里，这种结构很适合写作，但天然更偏 Dataview，不是 Bases 最擅长的模型。
        - 核心 `Templates` 只能插入模板，不能像 `Templater` 那样做自动命名、自动日期和复杂逻辑。

        ## 原来版本的优点

        > [!info]
        > 这里的“原来版本”指最初设想的 `Dataview + Templater` 主导方案。

        - Dataview 很适合做 `Q2 未完成`、`open/pending 用户问题`、`inline fields flatten` 这类跨页汇总。
        - Templater 很适合做自动命名、自动创建日期、自动插入字段、按目录触发不同模板。
        - 如果研究库稳定在桌面端、且你愿意长期维护社区插件版本，那么它的自动化体验会更强。

        ## 原来版本的缺点

        - 插件未装好时，面板页会静默失效，看起来像坏掉，其实只是查询没有运行。
        - 社区插件更依赖版本兼容与人工维护，换设备、换系统、Restricted Mode、移动端同步时更容易出问题。
        - 新用户接手时门槛更高，必须先懂插件安装、启用和配置，才能开始真正写内容。

        ## 这次已经落地的改进

        - 把视图层改成了 `Bases-first, Dataview-second`。
        - 新增了 6 个 `.base` 文件，对应文献总览、阅读队列、Q2 跟踪、概念索引、作者索引、课程总览。
        - 保留原 Dataview 查询页，但把它们下沉为可选增强层，不再被误解成默认必需层。
        - 首页和 README 会按“核心插件优先、社区插件可选”来说明。

        ## 现在最合理的插件分层

        ### 必须启用

        - `Properties`
        - `Templates`
        - `Bases`
        - `Callouts`
        - `.obsidian/snippets/` 下的 CSS snippets

        ### 推荐但可选

        - `Dataview`
          适合做跨笔记聚合、inline fields 扁平化和复杂筛选。
        - `Templater`
          适合做自动命名、自动插入日期和更复杂的新建流程。

        ### 先不要再加的

        - 与当前阅读系统功能重叠的重型数据库类插件
        - 会改变笔记语法或破坏纯 Markdown 可读性的插件
        - 需要在线服务、会让 vault 脱离本地可维护性的插件

        ## 下一步改进建议

        1. 如果你想继续保持低依赖：
           把“用户提出的问题”从正文列表逐步迁到 `04_Research/Questions/` 的独立问题笔记，Bases 就能接管更多检索。
        2. 如果你想提高自动化：
           安装 `Templater`，把“新建文献 -> 自动命名 -> 自动填 created/updated”接上。
        3. 如果你想提高跨页分析：
           安装 `Dataview`，保留当前正文 inline fields 写法，同时把 `Questions Dashboard` 继续做成聚合面板。
        """
    ),
    "00_System/00_Dashboard/Academic Reading Home.md": dedent(
        """\
        ---
        cssclasses:
          - dashboard-view
        ---

        # Obsidian Academic Reading Home

        > [!thesis]
        > 这套系统采用 `Markdown-first, HTML-export-second`。
        > 日常写作以 `Markdown + Properties + Callouts + Bases` 为主，
        > `Dataview` 和 `Templater` 现在是增强层，不再是假定必装层。

        ## 快速入口

        - [[00_System/01_Templates/Literature Note|新建文献笔记模板]]
        - [[00_System/01_Templates/Concept Note|新建概念卡模板]]
        - [[00_System/01_Templates/Author Note|新建作者卡模板]]
        - [[00_System/01_Templates/Course Week|新建课程周模板]]
        - [[00_System/01_Templates/Research Question|新建研究问题模板]]
        - [[00_System/01_Templates/Reading Log|新建阅读日志模板]]
        - [[00_System/02_Views/Literature Dashboard|文献总览]]
        - [[00_System/02_Views/Reading Queue|阅读队列]]
        - [[00_System/02_Views/Questions Dashboard|问题面板]]
        - [[00_System/02_Views/Concepts Map|概念索引]]
        - [[00_System/02_Views/Authors Index|作者索引]]
        - [[00_System/02_Views/Course Overview|课程总览]]
        - [[00_System/05_Docs/Plugin Strategy Review|插件策略评估]]
        - [[00_System/05_Docs/README|系统使用说明]]

        ## 当前插件策略

        > [!info]
        > 默认层：
        > `Properties + Templates + Bases + Callouts + CSS snippets`
        >
        > 可选增强层：
        > `Dataview + Templater`

        这意味着：

        - 没装社区插件时，主要模板、文献结构、样式和核心表格视图依然可用。
        - 装了 `Dataview` 后，可以继续获得更强的跨页聚合能力。
        - 装了 `Templater` 后，可以把自动命名和自动时间戳补上。

        ## 推荐工作流

        1. 在 `02_Literature/Papers/` 新建一篇 [[00_System/01_Templates/Literature Note|Literature Note]]。
        2. 先填写 frontmatter，再补双语标题、摘要、研究问题与术语表。
        3. 阅读时优先完成 `Q2 深答区`，再补 `Q1-Q10`、段落级批注和原文摘录。
        4. 若更强调论证结构，将 `question_mode` 改为 `B` 并启用 `logic-mode-b`。
        5. 日常队列管理优先使用 [[00_System/02_Views/Bases/Reading Queue.base|Reading Queue.base]] 与 [[00_System/02_Views/Bases/Literature Dashboard.base|Literature Dashboard.base]]。
        6. 若已安装 `Dataview`，再使用各视图页底部的增强查询。
        7. 导出展示时，复制 `06_Exports/HTML/` 下对应模板并替换占位内容。

        ## 模式切换

        > [!question|q2]
        > `A / Question 模式`
        > 适合课程阅读、问题驱动阅读和综述准备。

        > [!method]
        > `B / Logic 模式`
        > 适合做论证骨架、段落功能分析和 rebuttal 训练。

        > [!q2-focus]
        > 无论使用哪种模式，都建议优先完成 `Q2 深答区`。
        > 它是整篇笔记从“看过”到“真正吃透”的核心桥梁。

        ## 文件分区

        - `00_System/`：模板、视图、文档、样式说明
        - `01_Inbox/`：还没整理的临时阅读材料
        - `02_Literature/`：论文、作者、概念、主题与期刊
        - `03_Courses/`：课程周阅读与作业
        - `04_Research/`：研究问题、项目与综述草稿
        - `05_Reading-Logs/`：阅读日志
        - `06_Exports/`：HTML 导出产物
        - `99_Archive/`：归档
        """
    ),
    "00_System/02_Views/Literature Dashboard.md": dedent(
        """\
        ---
        cssclasses:
          - dashboard-view
        ---

        # Literature Dashboard

        > [!info]
        > 默认层使用 Obsidian 核心 `Bases`。
        > 这次把已对齐的 `year / venue / doi / tags` frontmatter 直接接进了总览层。
        > 如果你已经安装 `Dataview`，下面保留的是更适合做聚合和排查的增强查询。

        ## Bases 视图

        ### 文献总表

        ![[00_System/02_Views/Bases/Literature Dashboard.base#Library]]

        ### 按年份

        ![[00_System/02_Views/Bases/Literature Dashboard.base#By Year]]

        ### 按文献类型

        ![[00_System/02_Views/Bases/Literature Dashboard.base#By Publication Type]]

        ### 按期刊 / 会议

        ![[00_System/02_Views/Bases/Literature Dashboard.base#By Venue]]

        ### 按标签

        ![[00_System/02_Views/Bases/Literature Dashboard.base#By Tag]]

        ### 按作者

        ![[00_System/02_Views/Bases/Literature Dashboard.base#By Author]]

        ### DOI 缺口

        ![[00_System/02_Views/Bases/Literature Dashboard.base#Missing DOI]]

        ## Dataview 聚合（可选增强）

        > [!question|q1]
        > 如果你把论文放在别的目录，只需要把下面查询里的 `FROM "02_Literature/Papers"` 改掉即可。

        ### 最近整理完成的文献

        ```dataview
        TABLE year AS "年份", venue AS "期刊/会议", doi AS "DOI", tags AS "标签", status AS "状态"
        FROM "02_Literature/Papers"
        WHERE type = "paper"
        SORT year DESC, venue ASC, file.name ASC
        ```

        ### 按年份总览

        ```dataview
        TABLE year AS "年份", venue AS "期刊/会议", doi AS "DOI", tags AS "标签", short_title AS "短标题"
        FROM "02_Literature/Papers"
        WHERE type = "paper"
        SORT year DESC, short_title ASC
        ```

        ### 按文献类型聚合

        ```dataview
        TABLE WITHOUT ID key AS "文献类型", length(rows) AS "篇数", rows.file.link AS "文献"
        FROM "02_Literature/Papers"
        WHERE type = "paper" AND publication_type
        GROUP BY publication_type
        SORT length(rows) DESC, key ASC
        ```

        ### 按期刊 / 会议聚合

        ```dataview
        TABLE WITHOUT ID key AS "期刊/会议", length(rows) AS "篇数", rows.file.link AS "文献"
        FROM "02_Literature/Papers"
        WHERE type = "paper" AND venue
        GROUP BY venue
        SORT length(rows) DESC, key ASC
        ```

        ### 按标签聚合

        ```dataview
        TABLE WITHOUT ID key AS "标签", length(rows) AS "篇数", rows.file.link AS "文献"
        FROM "02_Literature/Papers"
        FLATTEN tags AS tag
        WHERE type = "paper" AND tag
        GROUP BY tag
        SORT length(rows) DESC, key ASC
        ```

        ### 按作者聚合

        ```dataview
        TABLE WITHOUT ID key AS "作者", length(rows) AS "篇数", rows.file.link AS "文献"
        FROM "02_Literature/Papers"
        FLATTEN authors AS author
        WHERE type = "paper" AND author
        GROUP BY author
        SORT length(rows) DESC, key ASC
        ```

        ### DOI 缺口排查

        ```dataview
        TABLE year AS "年份", venue AS "期刊/会议", tags AS "标签", url AS "URL", status AS "状态"
        FROM "02_Literature/Papers"
        WHERE type = "paper" AND (doi = null OR doi = "")
        SORT year DESC, file.name ASC
        ```

        ### 标签与阅读状态交叉查看

        ```dataview
        TABLE tags AS "标签", reading_stage AS "阅读阶段", priority AS "优先级", rating AS "评分"
        FROM "02_Literature/Papers"
        WHERE type = "paper"
        SORT status ASC, priority DESC, year DESC
        ```
        """
    ),
    "00_System/02_Views/Reading Queue.md": dedent(
        """\
        ---
        cssclasses:
          - dashboard-view
        ---

        # Reading Queue

        > [!question|q1]
        > 这个页面只抓 `status = to-read` 或 `status = reading` 的文献。

        ## Bases 视图

        ![[00_System/02_Views/Bases/Reading Queue.base#Queue]]

        ## Dataview 查询（可选增强）

        ```dataview
        TABLE status AS "状态", reading_stage AS "阶段", priority AS "优先级", course AS "课程", topics AS "主题"
        FROM "02_Literature/Papers"
        WHERE type = "paper" AND (status = "to-read" OR status = "reading")
        SORT priority DESC, year DESC
        ```
        """
    ),
    "00_System/02_Views/Questions Dashboard.md": dedent(
        """\
        ---
        cssclasses:
          - dashboard-view
        ---

        # Questions Dashboard

        > [!info]
        > 这个页面现在分成两层：
        > 核心层用 `Bases` 跟踪 `Q2` 和独立研究问题；
        > 可选增强层继续用 `Dataview` 汇总正文中的 inline user questions。

        ## Bases 视图

        ### Q2 跟踪

        ![[00_System/02_Views/Bases/Questions Dashboard.base#Q2 Tracker]]

        ### 独立研究问题笔记

        ![[00_System/02_Views/Bases/Questions Dashboard.base#Research Question Notes]]

        ## Dataview 查询（可选增强）

        ### 所有 open / pending 的用户问题

        > [!info]
        > 这个查询依赖文献页中 `# 用户提出的问题` 里的列表型 inline fields。
        > `Bases` 目前不擅长跨笔记扁平化这类正文数据，因此这部分仍由 Dataview 负责。

        ```dataview
        TABLE WITHOUT ID
          file.link AS "文献",
          item.question_id AS "问题 ID",
          item.question_text AS "问题内容",
          item.status AS "状态",
          item.linked_paragraphs AS "段落",
          item.tentative_answer AS "暂定回答"
        FROM "02_Literature/Papers"
        FLATTEN file.lists AS item
        WHERE item.question_id AND (item.status = "open" OR item.status = "pending")
        SORT file.name ASC, item.question_id ASC
        ```

        ### 所有 Q2 尚未完成的论文

        > [!q2-focus]
        > 建议把 `q2_status` 统一写成 `pending / draft / sourced / complete`，这样视图会更稳定。

        ```dataview
        TABLE q2_status AS "Q2 状态", q2_confidence AS "Q2 可信度", status AS "阅读状态", course AS "课程"
        FROM "02_Literature/Papers"
        WHERE type = "paper" AND (q2_status = null OR q2_status != "complete")
        SORT priority DESC, year DESC
        ```
        """
    ),
    "00_System/02_Views/Concepts Map.md": dedent(
        """\
        ---
        cssclasses:
          - dashboard-view
        ---

        # Concepts Map

        > [!info]
        > 默认层使用 `Bases`。如果装了 `Dataview`，可以继续使用下面的可选查询。

        ## Bases 视图

        ![[00_System/02_Views/Bases/Concepts Map.base#Concepts]]

        ## Dataview 查询（可选增强）

        ```dataview
        TABLE term_zh AS "中文", definition AS "定义", related_papers AS "相关论文", debates AS "争议"
        FROM "02_Literature/Concepts"
        WHERE type = "concept"
        SORT term ASC
        ```
        """
    ),
    "00_System/02_Views/Authors Index.md": dedent(
        """\
        ---
        cssclasses:
          - dashboard-view
        ---

        # Authors Index

        > [!info]
        > 默认层使用 `Bases`。如果装了 `Dataview`，可以继续使用下面的可选查询。

        ## Bases 视图

        ![[00_System/02_Views/Bases/Authors Index.base#Authors]]

        ## Dataview 查询（可选增强）

        ```dataview
        TABLE name_zh AS "中文名", affiliation AS "机构", fields AS "领域", key_works AS "代表作品"
        FROM "02_Literature/Authors"
        WHERE type = "author"
        SORT name ASC
        ```
        """
    ),
    "00_System/02_Views/Course Overview.md": dedent(
        """\
        ---
        cssclasses:
          - dashboard-view
        ---

        # Course Overview

        > [!info]
        > 默认层使用 `Bases`。如果装了 `Dataview`，可以继续使用下面的可选查询。

        ## Bases 视图

        ![[00_System/02_Views/Bases/Course Overview.base#Courses]]

        ## Dataview 查询（可选增强）

        ```dataview
        TABLE course AS "课程", week AS "Week", theme AS "主题", required_readings AS "必读", assignment AS "作业"
        FROM "03_Courses/Weekly"
        WHERE type = "course-week"
        SORT course ASC, week ASC
        ```
        """
    ),
    "00_System/05_Docs/README.md": dedent(
        """\
        # Obsidian Academic Reading System

        ## 目录结构

        ```text
        00_System/
          00_Dashboard/
          01_Templates/
          02_Views/
            Bases/
          03_Style/
          04_Scripts/
          05_Docs/
        01_Inbox/
        02_Literature/
          Papers/
          Authors/
          Journals/
          Topics/
          Concepts/
        03_Courses/
          Weekly/
          Assignments/
        04_Research/
          Questions/
          Projects/
          Review-Drafts/
        05_Reading-Logs/
        06_Exports/
          HTML/
          Assets/
        99_Archive/
        ```

        ## 当前插件策略

        > [!thesis]
        > 现在这套系统采用：
        > `Core-first, Community-second`
        >
        > 核心层：
        > `Properties + Templates + Bases + Callouts + CSS snippets`
        >
        > 增强层：
        > `Dataview + Templater`

        这样做的目的，是让你在没装社区插件时也能稳定写、稳定看、稳定同步。

        ## 必须启用的内容

        - Obsidian 原生 `Properties`
        - Obsidian 原生 `Callouts`
        - Obsidian 原生 `Templates`
        - Obsidian 原生 `Bases`
        - `.obsidian/snippets/` 下的 5 个 CSS snippets

        ## 推荐但可选的社区插件

        - `Dataview`
          适合做跨页聚合、inline fields flatten、开放问题总览。
        - `Templater`
          适合做自动命名、自动日期、自动插入模板变量。

        除这两个以外，建议先不要继续扩插件，避免后期维护成本失控。

        ## CSS snippets 放哪里

        放在：

        - `.obsidian/snippets/vault-theme-academic.css`
        - `.obsidian/snippets/vault-callouts.css`
        - `.obsidian/snippets/vault-paper-layout.css`
        - `.obsidian/snippets/vault-dashboard.css`
        - `.obsidian/snippets/vault-mobile.css`

        启用方式：

        1. 打开 Obsidian `Settings`
        2. 进入 `Appearance`
        3. 在 `CSS snippets` 中刷新并启用以上 5 个文件

        ## 模板放哪里

        模板位于：

        - `00_System/01_Templates/`

        当前最低依赖做法：

        - 在核心 `Templates` 插件里把这个目录设为模板目录

        增强做法：

        - 如果安装了 `Templater`，也可以把这里作为模板目录继续扩自动化

        ## 视图现在怎么用

        ### 默认方式

        优先使用这些核心 `Bases` 视图：

        - `00_System/02_Views/Bases/Literature Dashboard.base`
        - `00_System/02_Views/Bases/Reading Queue.base`
        - `00_System/02_Views/Bases/Questions Dashboard.base`
        - `00_System/02_Views/Bases/Concepts Map.base`
        - `00_System/02_Views/Bases/Authors Index.base`
        - `00_System/02_Views/Bases/Course Overview.base`

        ### 增强方式

        如果装了 `Dataview`，再打开对应 `.md` 页面底部的查询区：

        - `00_System/02_Views/Literature Dashboard.md`
        - `00_System/02_Views/Reading Queue.md`
        - `00_System/02_Views/Questions Dashboard.md`
        - `00_System/02_Views/Concepts Map.md`
        - `00_System/02_Views/Authors Index.md`
        - `00_System/02_Views/Course Overview.md`

        ## 如何新建一篇文献笔记

        1. 在 `02_Literature/Papers/` 新建笔记
        2. 插入 `00_System/01_Templates/Literature Note.md`
        3. 按命名规范重命名：
           `[Year] FirstAuthor - Short Title`
        4. 先填 frontmatter，再写正文

        ## 如何填写 Q1-Q10

        1. 用 `Q1` 确认文章到底在解决什么问题
        2. 立刻做 `Q2`，把核心主张压成一句话
        3. 再补 `Q3-Q6` 的概念、证据、方法和反驳
        4. 最后用 `Q7-Q10` 做批评、判断和迁移

        ## 如何重点完成 Q2

        优先完成 `# Q2 深答区`：

        - 精炼回答：50-100 字
        - 分析回答：200-400 字
        - 支持摘录：至少 2 条
        - 原文出处：至少 2 个 `paragraph_id` 或精确段号
        - 依赖概念：至少 1 个
        - 潜在反驳：至少 1 条
        - 我的最终判断：必须自己下结论
        - 可信度：`high / medium / low`

        建议统一使用：

        - `pending`
        - `draft`
        - `sourced`
        - `complete`

        ## 如何记录“用户提出的问题”

        目前推荐保留在文献笔记的 `# 用户提出的问题` 里，格式例如：

        ```markdown
        - question_id:: UQ-01
          question_text:: 这篇文章为什么能证明作者的核心主张？
          asked_by:: user
          status:: open
          linked_paragraphs:: p03, p07
          linked_quotes:: [[#p03]], [[#p07]]
          tentative_answer:: 目前只能部分支持
          final_answer::
          note:: 需要补看对照实验
        ```

        这套写法的优点是：

        - Obsidian 内好编辑
        - 与正文距离近
        - 后续仍可映射到 HTML 导出

        它的局限是：

        - 核心 `Bases` 不擅长跨笔记扁平化这类正文 inline fields
        - 如果你很重视全局问题汇总，建议后续把高价值问题逐步升级为 `04_Research/Questions/` 下的独立问题笔记

        ## 如何导出 HTML

        1. 进入 `06_Exports/HTML/`
        2. 选择：
           - `export-question-mode.html`
           - `export-logic-mode.html`
        3. 复制一份模板
        4. 替换成当前文献的标题、原文、批注和总结

        ## 如何在 A / B 模式间切换

        切换到 Question 模式：

        - `question_mode: A`
        - `cssclasses` 使用 `question-mode-a`
        - 重点维护 `Q1-Q10` 与 `Q2 深答区`

        切换到 Logic 模式：

        - `question_mode: B`
        - `cssclasses` 使用 `logic-mode-b`
        - 重点维护 `Logic Skeleton` 与段落逻辑批注

        ## 没装插件时的降级方式

        没有 Dataview：

        - 主要仪表板仍可通过 `Bases` 使用
        - 只有“inline user questions 跨页汇总”这类高级聚合会缺失

        没有 Templater：

        - 直接用核心 `Templates` 插入模板即可
        - `created`、`updated` 手工改一下就行

        没有启用 CSS snippets：

        - 文档仍然是干净的 Markdown
        - 只是少了视觉增强，不影响结构

        ## 命名规范

        - 文献主笔记：`[Year] FirstAuthor - Short Title`
        - 作者页：`Author - Full Name`
        - 概念页：`Concept - Term`
        - 研究问题页：`Question - Topic`
        - 课程周页：`Course - Week 03 - Topic`
        - 阅读日志：`Reading Log - YYYY-MM-DD`

        ## 进一步阅读

        - [[00_System/05_Docs/Plugin Strategy Review|Plugin Strategy Review]]
        """
    ),
}


def main() -> None:
    for rel_path, content in FILES.items():
        target = VAULT_ROOT / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        print(f"Wrote: {target}")


if __name__ == "__main__":
    main()
