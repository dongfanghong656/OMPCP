from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Callable


ATTEMPT_THEME_NAV_PATH = "15_尝试归档与索引/00_总览/尝试主题导航.md"
ATTEMPT_READER_ENTRY_PATH = "13_阅读区/10_尝试归档与索引/尝试主题阅读入口.md"
ATTEMPT_PROTOTYPE_OVERVIEW_PATH = "15_尝试归档与索引/02_工具与原型尝试/原型路线总览.md"
ATTEMPT_VAULT_PROTOTYPES_PATH = "15_尝试归档与索引/02_工具与原型尝试/Vault与论文流程原型索引.md"
ATTEMPT_VALIDATION_PROTOTYPES_PATH = "15_尝试归档与索引/02_工具与原型尝试/验证表达与基线原型索引.md"
ATTEMPT_CODEX_DIAGNOSTICS_PATH = "15_尝试归档与索引/02_工具与原型尝试/Codex App 线程排查索引.md"
READER_START_ENTRY_PATH = "13_阅读区/00_从这里开始/新手起步入口.md"
SYSTEM_READER_ENTRY_PATH = "13_阅读区/01_OCT系统与原理/OCT系统与原理起步入口.md"
LITERATURE_READER_ENTRY_PATH = "13_阅读区/02_文献阅读区/文献阅读起步入口.md"
LITERATURE_BRIDGE_SHELF_PATH = "13_阅读区/02_文献阅读区/桥接论文书架.md"
LITERATURE_ROUTE_MAP_PATH = "13_阅读区/02_文献阅读区/桥接论文阅读路线图.md"
LITERATURE_DECONV_ROUTE_PATH = "13_阅读区/02_文献阅读区/反卷积主线阅读路线.md"
LITERATURE_SYSTEM_ROUTE_PATH = "13_阅读区/02_文献阅读区/系统专用化阅读路线.md"
LITERATURE_BRIDGE_GUIDE_PATH = "13_阅读区/02_文献阅读区/桥接论文中文导读.md"
LITERATURE_CHINESE_INDEX_PATH = "13_阅读区/02_文献阅读区/中文阅读版文献索引.md"
EXPERIMENT_READER_ENTRY_PATH = "13_阅读区/03_实验与评估/实验验证起步入口.md"
FIGURE_READER_ENTRY_PATH = "13_阅读区/04_图示与路线图/图示表达起步入口.md"
WRITING_READER_ENTRY_PATH = "13_阅读区/05_写作与论文表达/写作表达起步入口.md"
TERM_READER_ENTRY_PATH = "13_阅读区/06_术语与问题/术语与问题起步入口.md"
ACTION_READER_ENTRY_PATH = "13_阅读区/07_未完成任务与下一步/行动起步入口.md"
EXECUTION_READER_ENTRY_PATH = "13_阅读区/08_日常规范与办事/执行规范起步入口.md"
RETRIEVAL_READER_ENTRY_PATH = "13_阅读区/09_项目进展与管理/检索与文献管理总览.md"
PROJECT_DECISION_READER_ENTRY_PATH = "13_阅读区/09_项目进展与管理/项目推进与决策入口.md"

PAPER_DOSSIER_FALLBACKS = {
    "02_Literature/Paper-Dossiers/_Index.md": "02_Literature/Papers/_Index.md",
    "02_Literature/Paper-Dossiers/[1991] Huang - Optical coherence tomography/_Index.md": "02_Literature/Papers/[1991] Huang - Optical coherence tomography.md",
    "02_Literature/Paper-Dossiers/[2003] Choma - Sensitivity advantage of swept source and/_Index.md": "02_Literature/Papers/[2003] Choma - Sensitivity advantage of swept source and.md",
    "02_Literature/Paper-Dossiers/[2003] de Boer - Improved signal-to-noise ratio in spectral-domain compared/_Index.md": "02_Literature/Papers/[2003] de Boer - Improved signal-to-noise ratio in spectral-domain compared.md",
    "02_Literature/Paper-Dossiers/[2003] 吴开杰 - OCT系统实用化的研究进展/_Index.md": "02_Literature/Papers/[2003] 吴开杰 - OCT系统实用化的研究进展.md",
    "02_Literature/Paper-Dossiers/[2004] Cense - Ultrahigh-resolution high-speed retinal imaging using/_Index.md": "02_Literature/Papers/[2004] Cense - Ultrahigh-resolution high-speed retinal imaging using.md",
    "02_Literature/Paper-Dossiers/[2004] Nassif - In vivo high-resolution video-rate spectral-domain/_Index.md": "02_Literature/Papers/[2004] Nassif - In vivo high-resolution video-rate spectral-domain.md",
    "02_Literature/Paper-Dossiers/[2005] Wojtkowski - Three-dimensional Retinal Imaging with High-Speed/_Index.md": "02_Literature/Papers/[2005] Wojtkowski - Three-dimensional Retinal Imaging with High-Speed.md",
    "02_Literature/Paper-Dossiers/[2010] 邹恒 - 基于时域和频域的光学相干层析成像系统的研究/_Index.md": "02_Literature/Papers/[2010] 邹恒 - 基于时域和频域的光学相干层析成像系统的研究.md",
    "02_Literature/Paper-Dossiers/[2022] Dong - Spatially adaptive blind deconvolution methods for/_Index.md": "02_Literature/Papers/[2022] Unknown - Spatially adaptive blind deconvolution methods for.md",
    "02_Literature/Paper-Dossiers/[2022] Ge - Superresolving artifact-free optical co-daab5363/_Index.md": "02_Literature/Papers/[2022] Unknown - Superresolving artifact-free optical coherence tomography with.md",
    "02_Literature/Paper-Dossiers/[2024] Ge - Deblurring artifact-free optical cohere-7ab44c80/_Index.md": "02_Literature/Papers/[2024] Ge - Deblurring artifact-free optical cohere-7ab44c80.md",
    "02_Literature/Paper-Dossiers/[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography/_Index.md": "02_Literature/Papers/[2025] Unknown - Deconvolution Techniques in Optical Coherence Tomography.md",
    "02_Literature/Paper-Dossiers/[2025] Unknown - Enhanced A-scan spatial resolution in spectral/_Index.md": "02_Literature/Papers/[2025] Unknown - Enhanced A-scan spatial resolution in spectral.md",
}

CONVERSATION_THEME_NAV_PATH = "09_Conversations/高价值会话主题导航.md"
CONVERSATION_READER_ENTRY_PATH = "13_阅读区/09_项目进展与管理/高价值会话入口.md"
CONVERSATION_SYSTEM_INDEX_PATH = "09_Conversations/研究系统与知识库演进会话索引.md"
CONVERSATION_LEARNING_INDEX_PATH = "09_Conversations/OCT学习与逐篇文献会话索引.md"
CONVERSATION_DECONV_INDEX_PATH = "09_Conversations/反卷积与验证会话索引.md"
CONVERSATION_TOOLING_INDEX_PATH = "09_Conversations/Codex与工具恢复会话索引.md"
CONVERSATION_CAREER_INDEX_PATH = "09_Conversations/就业与行业观察会话索引.md"

PROGRESS_THEME_NAV_PATH = "04_Progress/研究推进主线导航.md"
PROGRESS_READER_ENTRY_PATH = "13_阅读区/09_项目进展与管理/研究主线入口.md"
PROGRESS_MANUSCRIPT_INDEX_PATH = "04_Progress/反卷积验证与稿件主线索引.md"
PROGRESS_SPECTROMETER_INDEX_PATH = "04_Progress/OCT光谱仪系统专项索引.md"
PROGRESS_PIPELINE_INDEX_PATH = "04_Progress/知识库与文献管线索引.md"
PROGRESS_TRI_AGENT_INDEX_PATH = "04_Progress/Tri-Agent与控制平面索引.md"
PROGRESS_EVIDENCE_NAV_PATH = "04_Progress/研究问题证据链导航.md"
PROGRESS_EVIDENCE_READER_ENTRY_PATH = "13_阅读区/09_项目进展与管理/研究问题证据入口.md"
PROGRESS_DECONV_EVIDENCE_PATH = "04_Progress/反卷积真实增益证据链.md"
PROGRESS_SYSTEM_EVIDENCE_PATH = "04_Progress/OCT系统专用化证据链.md"
PROGRESS_DELIVERY_EVIDENCE_PATH = "04_Progress/知识库持续交付证据链.md"
PROGRESS_CORE_CONCLUSION_GUIDE_PATH = "04_Progress/核心结论入口.md"
PROGRESS_DECONV_CONCLUSION_GUIDE_PATH = "04_Progress/反卷积结论入口.md"
PROGRESS_SYSTEM_CONCLUSION_GUIDE_PATH = "04_Progress/系统判断入口.md"
PROGRESS_DELIVERY_CONCLUSION_GUIDE_PATH = "04_Progress/交付与治理结论入口.md"
PROGRESS_KEY_PAPER_GUIDE_PATH = "04_Progress/关键论文档案入口.md"
PROGRESS_FOUNDATION_PAPER_GUIDE_PATH = "04_Progress/方法奠基论文入口.md"
PROGRESS_SYSTEM_PAPER_GUIDE_PATH = "04_Progress/系统专用化论文入口.md"
PROGRESS_DECONV_PAPER_GUIDE_PATH = "04_Progress/反卷积主线论文入口.md"
PROGRESS_KEY_EXPERIMENT_GUIDE_PATH = "04_Progress/关键实验实例入口.md"
PROGRESS_SUCCESS_EXPERIMENT_GUIDE_PATH = "04_Progress/验证成功样例入口.md"
PROGRESS_FAILURE_EXPERIMENT_GUIDE_PATH = "04_Progress/失败与排障样例入口.md"
PROGRESS_CALIBRATION_EXPERIMENT_GUIDE_PATH = "04_Progress/系统校准样例入口.md"

WORKSPACE_PAPER_BRIDGE_OVERVIEW_PATH = "C:/codex-data/tmp-vault-reorg/vault-reorg/20260420-workspace-paper-bridge-overview.md"
WORKSPACE_PAPER_BRIDGE_BATCHES = [
    {
        "label": "方法奠基桥接第一批",
        "summary": "把最早的 OCT 奠基、谱域过渡和一篇 2024 去模糊主线补成第一批 bridge。",
        "entry_path": "04_Progress/方法奠基论文入口.md",
        "entry_label": "方法奠基论文入口",
        "run_path": "C:/codex-data/tmp-vault-reorg/vault-reorg/20260415-150502-workspace-paper-bridge-batch-v2-filtered/run.md",
        "bundle_path": "C:/codex-data/tmp-vault-reorg/targeted-bundles/20260415-v29b-workspace-paper-bridge-foundation-system-1/bundle",
        "papers": [
            "1991 Huang",
            "2003 Choma",
            "2003 de Boer",
            "2003 吴开杰",
            "2004 Cense",
            "2004 Nassif",
            "2005 Wojtkowski",
            "2010 邹恒",
            "2024 Ge",
        ],
    },
    {
        "label": "方法奠基桥接第二批",
        "summary": "把 1996 到 2012 的 FD / SS / OFDI 奠基链继续补成第二批 bridge，方便顺着早期系统演进读完整条方法线。",
        "entry_path": "04_Progress/方法奠基论文入口.md",
        "entry_label": "方法奠基论文入口",
        "run_path": "C:/codex-data/tmp-vault-reorg/vault-reorg/20260420-093825-workspace-paper-bridge-batch-v3-foundation-system-2/run.md",
        "bundle_path": "C:/codex-data/tmp-vault-reorg/targeted-bundles/20260420-v30-workspace-paper-bridge-foundation-system-2/bundle",
        "papers": [
            "1996 Tearney",
            "1997 Su",
            "1997 Endoscopic Optical Biopsy",
            "1997 Rapid and scalable scans",
            "1998 Szydlo",
            "2003 Leitgeb",
            "2003 Delay and dispersion",
            "2004 Wojtkowski Fourier-domain OCT",
            "2006 Lim",
            "2008 Fourier-domain OCT using swept source",
            "2011 An",
            "2012 Choi",
        ],
    },
    {
        "label": "系统专用化桥接第一批",
        "summary": "把工程实现、实时监测、精密控制和 OCT elastography 这一组系统专用化文献补成第三批 bridge。",
        "entry_path": "04_Progress/系统专用化论文入口.md",
        "entry_label": "系统专用化论文入口",
        "run_path": "C:/codex-data/tmp-vault-reorg/vault-reorg/20260420-093935-workspace-paper-bridge-batch-v4-system-specialization-1/run.md",
        "bundle_path": "C:/codex-data/tmp-vault-reorg/targeted-bundles/20260420-v31-workspace-paper-bridge-system-specialization-1/bundle",
        "papers": [
            "2008 de Bruin",
            "2011 Zhong",
            "2014 Wang",
            "2020 OCT elastography",
        ],
    },
]

INDEX_TITLE_MAP = {
    "02_Literature/Papers": "文献论文索引",
    "02_Literature/Paper-Dossiers": "论文档案索引",
    "12_Zotero/04_Item-Backfills": "Zotero 回填索引",
    "09_Conversations": "会话索引",
    "04_Progress": "进展索引",
    "10_Tasks": "任务索引",
    "05_Experiments/00_Verification-Plans": "验证计划索引",
    "05_Experiments/03_PSF-Measurement": "PSF 测量索引",
    "05_Experiments/04_Deconvolution-Baselines": "反卷积基线索引",
    "05_Experiments/05_No-Ground-Truth-Evaluation": "无真值评估索引",
    "05_Experiments/06_Statistical-Analysis": "统计分析索引",
    "06_Writing/05_Claim-to-Evidence": "论点到证据索引",
    "06_Writing/translation-workbench": "翻译工作台索引",
    "06_Writing/translated-papers": "译文索引",
}

ATTEMPT_VAULT_WORKFLOW_NOTES = [
    "15_尝试归档与索引/02_工具与原型尝试/2026-03-17-initial-vault-build-and-seed-literature-ingestion.md",
    "15_尝试归档与索引/02_工具与原型尝试/2026-03-18-translated-paper-workflow-validation.md",
    "15_尝试归档与索引/02_工具与原型尝试/2026-03-19-figure-study-packet-and-figure-analysis-layer.md",
    "15_尝试归档与索引/02_工具与原型尝试/2026-03-19-reader-facing-vault-and-daily-norms-zone.md",
    "15_尝试归档与索引/02_工具与原型尝试/2026-03-20-历史尝试回填与关键词记忆增强.md",
]
ATTEMPT_VALIDATION_PROTOTYPE_NOTES = [
    "15_尝试归档与索引/02_工具与原型尝试/2026-03-20-measured-psf-vs-gaussian-validation-page-v0.2.md",
    "15_尝试归档与索引/02_工具与原型尝试/2026-03-18-translated-paper-workflow-validation.md",
]
ATTEMPT_CODEX_APP_NOTES = [
    "15_尝试归档与索引/02_工具与原型尝试/2026-04-13-官方-codex-app-recent-list-疑似第二次响应失接.md",
    "15_尝试归档与索引/02_工具与原型尝试/2026-04-13-官方-codex-app-多账号独立线程集的可行性判断.md",
    "15_尝试归档与索引/02_工具与原型尝试/2026-04-13-官方-codex-app-线程列表缺失首屏分页-50-条的验证.md",
    "15_尝试归档与索引/02_工具与原型尝试/2026-04-13-官方-codex-app-线程缺失主因排序调整到分页与-pinned-持久化.md",
    "15_尝试归档与索引/02_工具与原型尝试/2026-04-13-官方-codex-app-线程缺失单根回写与-rollout-错配的二次定位.md",
    "15_尝试归档与索引/02_工具与原型尝试/2026-04-13-官方-codex-app-缺失线程的-pinned-thread-ids-验证.md",
    "15_尝试归档与索引/02_工具与原型尝试/2026-04-13-官方-codex-app-缺失线程的关闭态-pinned-注入验证.md",
]

CONVERSATION_SYSTEM_NOTES = [
    "09_Conversations/2026-03-17-initial-vault-build-and-first-literature-batch-153435.md",
    "09_Conversations/2026-03-18-structured-vault-governance-and-seed-note-expansion-165639.md",
    "09_Conversations/2026-03-18-theory-governance-and-behavioral-constitution-expansion-173646.md",
    "09_Conversations/2026-03-18-three-track-literature,-zotero,-and-delivery-upgrade-124623.md",
    "09_Conversations/2026-03-18-translation,-zotero,-and-delivery-framework-extension-132427.md",
    "09_Conversations/2026-03-18-vault-architecture-and-obsidian-filing-expansion-155731.md",
    "09_Conversations/2026-03-19-reader-facing-vault-expansion-and-daily-norms-zone-113933.md",
    "09_Conversations/2026-03-20-2026-03-20-attempt-archive-and-keyword-index-layer-added-to-the-oct-research-system-104331.md",
    "09_Conversations/2026-03-20-historical-attempt-backfill-and-keyword-memory-upgrade-111534.md",
    "09_Conversations/2026-03-23-long-dialogue-reuse-protocol-learned-from-oct-conversations-101453.md",
    "09_Conversations/2026-04-03-codex-history-recovery-priority-and-obsidian-sync-rule-170557.md",
]
CONVERSATION_LEARNING_NOTES = [
    "09_Conversations/2026-03-18-book-theory-backbone-and-evaluation-innovation-expansion-172359.md",
    "09_Conversations/2026-03-18-critical-paper-cards,-experiment-templates,-and-dashboard-expansion-170533.md",
    "09_Conversations/2026-03-18-high-weight-theory-expansion-and-template-integration-174411.md",
    "09_Conversations/2026-03-19-figure-analysis-framework-and-long-horizon-learning-upgrade-095843.md",
    "09_Conversations/2026-03-19-figure-workflow-script-and-project-roadmap-drafting-110446.md",
    "09_Conversations/2026-03-20-oct-classified-basics-154205.md",
    "09_Conversations/2026-03-20-oct-classified-effective-spectrum-and-pixel-matching-155556.md",
    "09_Conversations/2026-03-20-oct-classified-pixels-and-reference-power-2-155000.md",
    "09_Conversations/2026-03-20-oct-knowledge-classification-153431.md",
    "09_Conversations/2026-03-20-oct-learning-process-and-protocol-152818.md",
    "09_Conversations/2026-03-20-oct-spectrometer-knowledge-organization-153756.md",
    "09_Conversations/2026-03-20-oct-spectrometer-tuning-qa-151400.md",
    "09_Conversations/2026-03-20-oct光谱仪四阶段深化学习执行-105919.md",
    "09_Conversations/2026-03-20-oct光谱仪学习盘点与深化计划-104251.md",
    "09_Conversations/2026-03-23-oct-classified-grating-match-and-detector-plane-175142.md",
    "09_Conversations/2026-03-23-oct-decision-layer-three-windows-175621.md",
    "09_Conversations/2026-03-23-杰文师兄文献夹批量学习-102208.md",
    "09_Conversations/2026-03-23-逐篇学习：1991-2003-oct基础链-105232.md",
    "09_Conversations/2026-03-23-逐篇学习：2003-2006-fd-ss-ofdi链-175137.md",
    "09_Conversations/2026-03-24-逐篇学习：2008-amd-ofdi-1050nm-100202.md",
    "09_Conversations/2026-03-27-逐篇学习基础链标准化回填-013738.md",
]
CONVERSATION_DECONV_NOTES = [
    "09_Conversations/2026-03-20-2026-03-20-validation-methodology-written-into-base-layer,-skill,-and-vault-102533.md",
    "09_Conversations/2026-03-20-2026-03-20-validation-prototype-control-upgrade-with-sliders,-toggles,-seed,-version,-and-export-014057.md",
    "09_Conversations/2026-03-20-formal-verification-plan-for-measured-psf-versus-gaussian-baseline-002315.md",
    "09_Conversations/2026-03-20-minimal-visual-validation-page-draft-for-measured-psf-versus-gaussian-baseline-003710.md",
    "09_Conversations/2026-03-20-validation-driven-methodology-layer-and-research-ui-protocol-001415.md",
    "09_Conversations/2026-04-02-psf-deconvolution-code-radar-round2-230000.md",
    "09_Conversations/2026-04-12-oct-deconvolution-code-and-algorithm-package-for-gpt-review.md",
    "09_Conversations/2026-04-12-oct-deconvolution-theory-package-for-gpt-pro-review.md",
    "09_Conversations/2026-04-12-反卷积文章逻辑梳理与GPT深调研委托.md",
    "09_Conversations/2026-04-13-rl-wiener-blind-rl-round4-120500.md",
    "09_Conversations/2026-04-13-young-oct-lfs-and-deconvolution-round3-111500.md",
]
CONVERSATION_TOOLING_NOTES = [
    "09_Conversations/2026-03-17-openclaw-migration-and-zotero-local-repair-165330.md",
    "09_Conversations/2026-03-23-ecm-local-package-verification-and-runtime-split-103840.md",
    "09_Conversations/2026-03-23-ecm-matlab新窗口命令与antigravity-matlab调查-153226.md",
    "09_Conversations/2026-03-23-ecm-window-conversation-critical-review-100612.md",
    "09_Conversations/2026-03-23-matlab-startup-blocker-narrowed-to-pathdef-access-denial-105342.md",
    "09_Conversations/2026-03-23-prepared-manual-windows-checklist-for-matlab-path-repair-143153.md",
    "09_Conversations/2026-04-13-codex-app-线程仍不全：定位到官方桌面首屏仅拉取-50-条-000750.md",
    "09_Conversations/2026-04-13-codex-app-线程仍未全显：补定位到单根回写与-active-rollout-路径错配-003725.md",
    "09_Conversations/2026-04-13-codex-app-线程补全验证：利用-pinned-thread-ids-强制注水缺失页-001147.md",
    "09_Conversations/2026-04-13-codex-app-线程补全验证：已在关闭状态下注入-pinned-thread-ids-并重启官方-app-002218.md",
    "09_Conversations/2026-04-13-codex-官方-app-主因排序调整：分页与-pinned-持久化优先于-active-root-010704.md",
    "09_Conversations/2026-04-13-codex-官方-app-分页链新判断：第二次-thread-list-响应可能未被前端状态机接住-093720.md",
    "09_Conversations/2026-04-13-codex-官方-app-多账号独立线程可行性判断：当前证据不支持原生按账号分离线程集-100806.md",
]
CONVERSATION_CAREER_NOTES = [
    "09_Conversations/2026-04-12-oct-job-content-role-breakdown-173904.md",
    "09_Conversations/2026-04-12-oct-master-employment-scale-salary-deep-dive-135101.md",
    "09_Conversations/2026-04-12-oct-non-algorithm-jobs-and-mechanical-support-142835.md",
    "09_Conversations/2026-04-12-wechat-oct-job-companies-positions-round2-182722.md",
    "09_Conversations/2026-04-12-wechat-oct-job-companies-positions-round2-183458.md",
    "09_Conversations/2026-04-12-wechat-public-account-oct-employment-supplement-131951.md",
    "09_Conversations/2026-04-12-xhs-wechat-oct-nonalgorithm-mechanical-addendum-161727.md",
    "09_Conversations/2026-04-12-xiaohongshu-oct就业去向与薪资甄别-120210.md",
]

PROGRESS_MANUSCRIPT_NOTES = [
    "04_Progress/01_Project-Roadmap/roadmap-overview.md",
    "04_Progress/03_Risk-Register/risk-register.md",
    "04_Progress/03_Risk-Register/controversy-and-debate-map.md",
    "04_Progress/03_Risk-Register/long-horizon-key-questions-for-oct-figure-analysis.md",
    "04_Progress/04_Decision-Log/decision-log.md",
    "04_Progress/05_Claim-Tracker/claim-tracker.md",
    "04_Progress/2026-03-18-research-gap-matrix.md",
    "04_Progress/three-month-manuscript-track.md",
    "04_Progress/platform-integration-progress.md",
]
PROGRESS_SPECTROMETER_NOTES = [
    "04_Progress/oct-spectrometer-system-specific-template.md",
    "04_Progress/oct-spectrometer-system-specific-open-questions.md",
    "04_Progress/oct-spectrometer-system-specific-decision-map.md",
]
PROGRESS_PIPELINE_NOTES = [
    "04_Progress/2026-03-18-vault-architecture-expansion.md",
    "04_Progress/2026-03-18-translation-zotero-and-delivery-extension.md",
    "04_Progress/2026-03-18-obsidian-bridge-and-gmail-switch.md",
    "04_Progress/platform-integration-progress.md",
]
PROGRESS_TRI_AGENT_NOTES = [
    "04_Progress/tri-agent-control-plane-progress.md",
    "10_Tasks/system-expansion-backlog.md",
    "10_Tasks/01_This-Week/this-week-focus.md",
    "10_Tasks/Tri-Agent/Tri-Agent Task Bus Board.md",
    "10_Tasks/Tri-Agent/Tri-Agent-Permission-Config.md",
    "10_Tasks/Tri-Agent/Tri-Agent-Experience-Summary-2026-04-02.md",
    "10_Tasks/Tri-Agent/Antigravity-Integration-Protocol-2026-04-02.md",
    "10_Tasks/Tri-Agent/Antigravity-Vault-Auto-Sync-Rule.md",
    "10_Tasks/Tri-Agent/Claude-Adoption-Record-2026-04-01.md",
    "10_Tasks/Tri-Agent/Claude-Vault-Auto-Sync-Rule.md",
]

PROGRESS_DECONV_EVIDENCE_SECTIONS = [
    (
        "进展判断",
        [
            PROGRESS_MANUSCRIPT_INDEX_PATH,
            "04_Progress/three-month-manuscript-track.md",
            "04_Progress/05_Claim-Tracker/claim-tracker.md",
            "04_Progress/03_Risk-Register/risk-register.md",
        ],
    ),
    (
        "实验与验证",
        [
            "05_Experiments/00_Verification-Plans/_Index.md",
            "05_Experiments/03_PSF-Measurement/_Index.md",
            "05_Experiments/04_Deconvolution-Baselines/_Index.md",
            "05_Experiments/05_No-Ground-Truth-Evaluation/_Index.md",
            "05_Experiments/06_Statistical-Analysis/_Index.md",
            "05_Experiments/00_Verification-Plans/verification-plan-measured-psf-vs-gaussian-phantom.md",
            "05_Experiments/01_Phantom/phantom-bead-baseline-instance.md",
            "05_Experiments/03_PSF-Measurement/psf-measurement-instance-bead-scan.md",
            "05_Experiments/04_Deconvolution-Baselines/classical-baseline-comparison-sheet.md",
            "05_Experiments/04_Deconvolution-Baselines/raw-interferogram-to-bscan-debug-protocol.md",
            "05_Experiments/lateral-resolution-validation-matrix.md",
        ],
    ),
    (
        "论文与档案",
        [
            "02_Literature/Paper-Dossiers/_Index.md",
            "02_Literature/Paper-Dossiers/[2022] Ge - Superresolving artifact-free optical co-daab5363/_Index.md",
            "02_Literature/Paper-Dossiers/[2024] Ge - Deblurring artifact-free optical cohere-7ab44c80/_Index.md",
            "02_Literature/Paper-Dossiers/[2022] Dong - Spatially adaptive blind deconvolution methods for/_Index.md",
            "02_Literature/Paper-Dossiers/[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography/_Index.md",
            "02_Literature/Paper-Dossiers/[2025] Unknown - Enhanced A-scan spatial resolution in spectral/_Index.md",
        ],
    ),
    (
        "写作与表达",
        [
            "06_Writing/05_Claim-to-Evidence/_Index.md",
            "06_Writing/03_Figures-and-Captions/_Index.md",
            "06_Writing/03_Figures-and-Captions/minimal-validation-page-draft-measured-psf-vs-gaussian.md",
            "06_Writing/03_Figures-and-Captions/current-oct-deconvolution-technical-roadmap-draft.md",
        ],
    ),
    (
        "会话与讨论",
        [
            CONVERSATION_DECONV_INDEX_PATH,
            "09_Conversations/2026-04-12-反卷积文章逻辑梳理与GPT深调研委托.md",
            "09_Conversations/2026-04-13-rl-wiener-blind-rl-round4-120500.md",
        ],
    ),
]

PROGRESS_SYSTEM_EVIDENCE_SECTIONS = [
    (
        "进展判断",
        [
            PROGRESS_SPECTROMETER_INDEX_PATH,
            "04_Progress/oct-spectrometer-system-specific-template.md",
            "04_Progress/oct-spectrometer-system-specific-open-questions.md",
            "04_Progress/oct-spectrometer-system-specific-decision-map.md",
        ],
    ),
    (
        "实验与系统检查",
        [
            "05_Experiments/OCT-Spectrometer-Three-Window-Decision-Flow.md",
            "05_Experiments/OCT-Spectrometer-System-Data-Package-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Evidence-Intake-Worksheet.md",
            "05_Experiments/OCT-Spectrometer-Adjustment-and-Validation-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Effective-Spectrum-Inspection-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Pixel-and-Spot-Matching-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Grating-Match-Inspection-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Reference-Arm-Power-Adjustment-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Detector-Plane-and-Edge-Aberration-Checklist.md",
        ],
    ),
    (
        "论文与档案",
        [
            "02_Literature/Paper-Dossiers/_Index.md",
            "02_Literature/Paper-Dossiers/[2003] 吴开杰 - OCT系统实用化的研究进展/_Index.md",
            "02_Literature/Paper-Dossiers/[2010] 邹恒 - 基于时域和频域的光学相干层析成像系统的研究/_Index.md",
            "02_Literature/Paper-Dossiers/[2003] de Boer - Improved signal-to-noise ratio in spectral-domain compared/_Index.md",
            "02_Literature/Paper-Dossiers/[2003] Choma - Sensitivity advantage of swept source and/_Index.md",
        ],
    ),
    (
        "图示与讨论",
        [
            "06_Writing/03_Figures-and-Captions/seed-paper-system-and-figure-comparison-board.md",
            CONVERSATION_LEARNING_INDEX_PATH,
            "09_Conversations/2026-04-14-oct-system-specific-decision-map-and-worksheet-110025.md",
            "09_Conversations/2026-04-13-oct-system-specific-template-and-data-package-120346.md",
        ],
    ),
]

PROGRESS_DELIVERY_EVIDENCE_SECTIONS = [
    (
        "进展判断",
        [
            PROGRESS_PIPELINE_INDEX_PATH,
            "04_Progress/2026-03-18-vault-architecture-expansion.md",
            "04_Progress/2026-03-18-translation-zotero-and-delivery-extension.md",
            "04_Progress/2026-03-18-obsidian-bridge-and-gmail-switch.md",
            "04_Progress/platform-integration-progress.md",
        ],
    ),
    (
        "文献与归档层",
        [
            "02_Literature/Papers/_Index.md",
            "02_Literature/Paper-Dossiers/_Index.md",
            "12_Zotero/04_Item-Backfills/_Index.md",
        ],
    ),
    (
        "翻译与写作交付",
        [
            "06_Writing/translated-papers/_Index.md",
            "06_Writing/translation-workbench/_Index.md",
            "06_Writing/05_Claim-to-Evidence/_Index.md",
        ],
    ),
    (
        "对话与尝试脉络",
        [
            CONVERSATION_SYSTEM_INDEX_PATH,
            ATTEMPT_THEME_NAV_PATH,
            ATTEMPT_VAULT_PROTOTYPES_PATH,
            CONVERSATION_READER_ENTRY_PATH,
        ],
    ),
]


@dataclass(frozen=True)
class Note:
    rel_path: str
    title: str
    frontmatter: dict[str, str]
    top_folder: str
    parent_folder: str
    stem: str
    is_index: bool


def norm_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def wikilink(rel_path: str | Path, label: str | None = None) -> str:
    target = norm_path(rel_path)
    if target.endswith(".md"):
        target = target[:-3]
    return f"[[{target}|{label}]]" if label else f"[[{target}]]"


def slug_title(stem: str) -> str:
    title = stem.replace("-", " ").replace("_", " ").strip()
    title = re.sub(r"\s+", " ", title)
    return title or stem


PROGRESS_KEY_PAPER_GUIDE_SECTIONS = [
    (
        "反卷积主线论文",
        [
            "02_Literature/Paper-Dossiers/[2022] Dong - Spatially adaptive blind deconvolution methods for/_Index.md",
            "02_Literature/Paper-Dossiers/[2022] Ge - Superresolving artifact-free optical co-daab5363/_Index.md",
            "02_Literature/Paper-Dossiers/[2024] Ge - Deblurring artifact-free optical cohere-7ab44c80/_Index.md",
            "02_Literature/Paper-Dossiers/[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography/_Index.md",
            "02_Literature/Paper-Dossiers/[2025] Unknown - Enhanced A-scan spatial resolution in spectral/_Index.md",
        ],
    ),
    (
        "方法奠基论文",
        [
            "02_Literature/Paper-Dossiers/[1991] Huang - Optical coherence tomography/_Index.md",
            "02_Literature/Paper-Dossiers/[2003] Choma - Sensitivity advantage of swept source and/_Index.md",
            "02_Literature/Paper-Dossiers/[2003] de Boer - Improved signal-to-noise ratio in spectral-domain compared/_Index.md",
        ],
    ),
    (
        "系统专用化论文",
        [
            "02_Literature/Paper-Dossiers/[2003] 吴开杰 - OCT系统实用化的研究进展/_Index.md",
            "02_Literature/Paper-Dossiers/[2004] Cense - Ultrahigh-resolution high-speed retinal imaging using/_Index.md",
            "02_Literature/Paper-Dossiers/[2004] Nassif - In vivo high-resolution video-rate spectral-domain/_Index.md",
            "02_Literature/Paper-Dossiers/[2005] Wojtkowski - Three-dimensional Retinal Imaging with High-Speed/_Index.md",
            "02_Literature/Paper-Dossiers/[2010] 邹恒 - 基于时域和频域的光学相干层析成像系统的研究/_Index.md",
        ],
    ),
]

PROGRESS_FOUNDATION_PAPER_GUIDE_SECTIONS = [
    (
        "从 OCT 成像原理到 Fourier / Swept Source 基线",
        [
            "02_Literature/Paper-Dossiers/[1991] Huang - Optical coherence tomography/_Index.md",
            "02_Literature/Paper-Dossiers/[2003] Choma - Sensitivity advantage of swept source and/_Index.md",
            "02_Literature/Paper-Dossiers/[2003] de Boer - Improved signal-to-noise ratio in spectral-domain compared/_Index.md",
        ],
    ),
]

PROGRESS_SYSTEM_PAPER_GUIDE_SECTIONS = [
    (
        "系统实用化与高速谱域路线",
        [
            "02_Literature/Paper-Dossiers/[2003] 吴开杰 - OCT系统实用化的研究进展/_Index.md",
            "02_Literature/Paper-Dossiers/[2004] Cense - Ultrahigh-resolution high-speed retinal imaging using/_Index.md",
            "02_Literature/Paper-Dossiers/[2004] Nassif - In vivo high-resolution video-rate spectral-domain/_Index.md",
            "02_Literature/Paper-Dossiers/[2005] Wojtkowski - Three-dimensional Retinal Imaging with High-Speed/_Index.md",
            "02_Literature/Paper-Dossiers/[2010] 邹恒 - 基于时域和频域的光学相干层析成像系统的研究/_Index.md",
        ],
    ),
]

PROGRESS_DECONV_PAPER_GUIDE_SECTIONS = [
    (
        "反卷积、超分辨与综述主线",
        [
            "02_Literature/Paper-Dossiers/[2022] Dong - Spatially adaptive blind deconvolution methods for/_Index.md",
            "02_Literature/Paper-Dossiers/[2022] Ge - Superresolving artifact-free optical co-daab5363/_Index.md",
            "02_Literature/Paper-Dossiers/[2024] Ge - Deblurring artifact-free optical cohere-7ab44c80/_Index.md",
            "02_Literature/Paper-Dossiers/[2025] Abbasi - Deconvolution Techniques in Optical Coherence Tomography/_Index.md",
            "02_Literature/Paper-Dossiers/[2025] Unknown - Enhanced A-scan spatial resolution in spectral/_Index.md",
        ],
    ),
]

PROGRESS_CORE_CONCLUSION_GUIDE_SECTIONS = [
    (
        "总判断与边界",
        [
            "04_Progress/05_Claim-Tracker/claim-tracker.md",
            "06_Writing/05_Claim-to-Evidence/current-claim-boundaries.md",
            "04_Progress/04_Decision-Log/decision-log.md",
            "04_Progress/03_Risk-Register/risk-register.md",
            "04_Progress/03_Risk-Register/controversy-and-debate-map.md",
        ],
    ),
    (
        "问题与证据总线",
        [
            "04_Progress/研究问题证据链导航.md",
            "04_Progress/反卷积真实增益证据链.md",
            "04_Progress/OCT系统专用化证据链.md",
            "04_Progress/知识库持续交付证据链.md",
        ],
    ),
]

PROGRESS_DECONV_CONCLUSION_GUIDE_SECTIONS = [
    (
        "当前主张与稿件边界",
        [
            "04_Progress/反卷积真实增益证据链.md",
            "04_Progress/反卷积验证与稿件主线索引.md",
            "04_Progress/three-month-manuscript-track.md",
            "04_Progress/05_Claim-Tracker/claim-tracker.md",
            "06_Writing/05_Claim-to-Evidence/current-claim-boundaries.md",
        ],
    ),
    (
        "争议点与复核来源",
        [
            "04_Progress/03_Risk-Register/controversy-and-debate-map.md",
            "09_Conversations/2026-04-12-反卷积文章逻辑梳理与GPT深调研委托.md",
            "09_Conversations/2026-04-12-oct-deconvolution-theory-package-for-gpt-pro-review.md",
            "09_Conversations/2026-04-13-rl-wiener-blind-rl-round4-120500.md",
        ],
    ),
]

PROGRESS_SYSTEM_CONCLUSION_GUIDE_SECTIONS = [
    (
        "当前系统判断",
        [
            "04_Progress/OCT系统专用化证据链.md",
            "04_Progress/OCT光谱仪系统专项索引.md",
            "04_Progress/oct-spectrometer-system-specific-decision-map.md",
            "04_Progress/oct-spectrometer-system-specific-open-questions.md",
            "04_Progress/oct-spectrometer-system-specific-template.md",
        ],
    ),
    (
        "判断来源与讨论依据",
        [
            "09_Conversations/2026-04-14-oct-system-specific-decision-map-and-worksheet-110025.md",
            "09_Conversations/2026-04-13-oct-system-specific-template-and-data-package-120346.md",
            "09_Conversations/2026-03-23-oct-decision-layer-three-windows-175621.md",
            "09_Conversations/2026-03-20-oct-spectrometer-tuning-qa-151400.md",
            "09_Conversations/2026-03-20-oct-classified-effective-spectrum-and-pixel-matching-155556.md",
        ],
    ),
]

PROGRESS_DELIVERY_CONCLUSION_GUIDE_SECTIONS = [
    (
        "治理与交付判断",
        [
            "04_Progress/知识库持续交付证据链.md",
            "04_Progress/知识库与文献管线索引.md",
            "04_Progress/2026-03-18-vault-architecture-expansion.md",
            "04_Progress/2026-03-18-translation-zotero-and-delivery-extension.md",
            "04_Progress/2026-03-18-obsidian-bridge-and-gmail-switch.md",
            "04_Progress/platform-integration-progress.md",
        ],
    ),
    (
        "交付演进会话依据",
        [
            "09_Conversations/2026-03-17-initial-vault-build-and-first-literature-batch-153435.md",
            "09_Conversations/2026-03-18-translation,-zotero,-and-delivery-framework-extension-132427.md",
            "09_Conversations/2026-03-18-vault-architecture-and-obsidian-filing-expansion-155731.md",
            "09_Conversations/研究系统与知识库演进会话索引.md",
        ],
    ),
]

PROGRESS_KEY_EXPERIMENT_GUIDE_SECTIONS = [
    (
        "验证成功样例",
        [
            "05_Experiments/04_Deconvolution-Baselines/classical-baseline-comparison-sheet.md",
            "05_Experiments/lateral-resolution-validation-matrix.md",
            "05_Experiments/01_Phantom/phantom-bead-baseline-instance.md",
            "05_Experiments/03_PSF-Measurement/psf-measurement-instance-bead-scan.md",
            "05_Experiments/00_Verification-Plans/verification-plan-measured-psf-vs-gaussian-phantom.md",
        ],
    ),
    (
        "失败与排障样例",
        [
            "05_Experiments/08_Failure-Cases/failure-mode-catalog.md",
            "05_Experiments/04_Deconvolution-Baselines/raw-interferogram-to-bscan-debug-protocol.md",
            "05_Experiments/OCT-Raw-to-Bscan-and-PSF-Smoke-Test-Protocol.md",
            "05_Experiments/OCT-Parasitic-Interference-Diagnostic-Card.md",
            "05_Experiments/OCT-Optical-Path-Difference-Adjustment-Card.md",
            "05_Experiments/05_No-Ground-Truth-Evaluation/no-ground-truth-metric-checklist.md",
            "05_Experiments/experiment-program.md",
        ],
    ),
    (
        "系统校准样例",
        [
            "05_Experiments/OCT-Spectrometer-Evidence-Intake-Worksheet.md",
            "05_Experiments/OCT-Spectrometer-System-Data-Package-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Three-Window-Decision-Flow.md",
            "05_Experiments/OCT-Spectrometer-Adjustment-and-Validation-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Effective-Spectrum-Inspection-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Pixel-and-Spot-Matching-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Reference-Arm-Power-Adjustment-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Grating-Match-Inspection-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Fiber-Stability-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Detector-Plane-and-Edge-Aberration-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Camera-Coverage-and-Roll-off-Checklist.md",
        ],
    ),
    (
        "写作与论证锚点",
        [
            "06_Writing/03_Figures-and-Captions/minimal-validation-page-draft-measured-psf-vs-gaussian.md",
            "06_Writing/03_Figures-and-Captions/current-oct-deconvolution-technical-roadmap-draft.md",
            "06_Writing/05_Claim-to-Evidence/current-claim-boundaries.md",
            "06_Writing/03_Figures-and-Captions/seed-paper-system-and-figure-comparison-board.md",
        ],
    ),
]

PROGRESS_SUCCESS_EXPERIMENT_GUIDE_SECTIONS = [
    (
        "正式验证与收益判断",
        [
            "05_Experiments/00_Verification-Plans/verification-plan-measured-psf-vs-gaussian-phantom.md",
            "05_Experiments/01_Phantom/phantom-bead-baseline-instance.md",
            "05_Experiments/03_PSF-Measurement/psf-measurement-instance-bead-scan.md",
            "05_Experiments/04_Deconvolution-Baselines/classical-baseline-comparison-sheet.md",
            "05_Experiments/lateral-resolution-validation-matrix.md",
        ],
    ),
    (
        "结果收口与论证锚点",
        [
            "06_Writing/03_Figures-and-Captions/minimal-validation-page-draft-measured-psf-vs-gaussian.md",
            "06_Writing/03_Figures-and-Captions/current-oct-deconvolution-technical-roadmap-draft.md",
            "06_Writing/05_Claim-to-Evidence/current-claim-boundaries.md",
        ],
    ),
]

PROGRESS_FAILURE_EXPERIMENT_GUIDE_SECTIONS = [
    (
        "失败与不稳定行为",
        [
            "05_Experiments/08_Failure-Cases/failure-mode-catalog.md",
            "05_Experiments/05_No-Ground-Truth-Evaluation/no-ground-truth-metric-checklist.md",
            "05_Experiments/experiment-program.md",
        ],
    ),
    (
        "最短排障链",
        [
            "05_Experiments/04_Deconvolution-Baselines/raw-interferogram-to-bscan-debug-protocol.md",
            "05_Experiments/OCT-Raw-to-Bscan-and-PSF-Smoke-Test-Protocol.md",
            "05_Experiments/OCT-Parasitic-Interference-Diagnostic-Card.md",
            "05_Experiments/OCT-Optical-Path-Difference-Adjustment-Card.md",
        ],
    ),
]

PROGRESS_CALIBRATION_EXPERIMENT_GUIDE_SECTIONS = [
    (
        "系统证据起步",
        [
            "05_Experiments/OCT-Spectrometer-Evidence-Intake-Worksheet.md",
            "05_Experiments/OCT-Spectrometer-System-Data-Package-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Three-Window-Decision-Flow.md",
            "05_Experiments/OCT-Spectrometer-Adjustment-and-Validation-Checklist.md",
        ],
    ),
    (
        "像面、光路与匹配检查",
        [
            "05_Experiments/OCT-Spectrometer-Effective-Spectrum-Inspection-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Pixel-and-Spot-Matching-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Reference-Arm-Power-Adjustment-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Grating-Match-Inspection-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Fiber-Stability-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Detector-Plane-and-Edge-Aberration-Checklist.md",
            "05_Experiments/OCT-Spectrometer-Camera-Coverage-and-Roll-off-Checklist.md",
        ],
    ),
]

def preferred_index_title(rel_path: str, fallback: str) -> str:
    rel = norm_path(rel_path)
    folder = str(Path(rel).parent).replace("\\", "/")
    return INDEX_TITLE_MAP.get(folder, fallback)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    frontmatter: dict[str, str] = {}
    end_idx = None
    for idx in range(1, len(lines)):
        line = lines[idx]
        if line.strip() == "---":
            end_idx = idx
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip("'\"")
    if end_idx is None:
        return {}, text
    body = "\n".join(lines[end_idx + 1 :]).lstrip("\n")
    return frontmatter, body


def extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def scan_notes(vault_root: Path) -> dict[str, Note]:
    notes: dict[str, Note] = {}
    for path in sorted(vault_root.rglob("*.md")):
        rel_path = norm_path(path.relative_to(vault_root))
        raw_text = path.read_text(encoding="utf-8-sig")
        frontmatter, body = parse_frontmatter(raw_text)
        stem = path.stem
        title = frontmatter.get("title") or extract_title(body, slug_title(stem))
        top_folder = rel_path.split("/", 1)[0]
        parent_folder = norm_path(path.relative_to(vault_root).parent)
        notes[rel_path] = Note(
            rel_path=rel_path,
            title=title,
            frontmatter=frontmatter,
            top_folder=top_folder,
            parent_folder="" if parent_folder == "." else parent_folder,
            stem=stem,
            is_index=stem == "_Index",
        )
    return notes


def descendants(notes: dict[str, Note], folder: str) -> list[Note]:
    prefix = f"{folder}/" if folder else ""
    return [note for note in notes.values() if note.rel_path.startswith(prefix) and not note.is_index]


def direct_notes(notes: dict[str, Note], folder: str) -> list[Note]:
    return sorted(
        [note for note in notes.values() if note.parent_folder == folder and not note.is_index],
        key=lambda note: (note.title.lower(), note.rel_path.lower()),
    )


def child_dirs(notes: dict[str, Note], folder: str) -> list[str]:
    prefix = f"{folder}/" if folder else ""
    children: set[str] = set()
    for note in notes.values():
        if not note.rel_path.startswith(prefix):
            continue
        rest = note.rel_path[len(prefix) :]
        if "/" not in rest:
            continue
        child = rest.split("/", 1)[0]
        children.add(f"{folder}/{child}" if folder else child)
    return sorted(children)


def resolve_paths(notes: dict[str, Note], paths: list[str]) -> list[Note]:
    resolved: list[Note] = []
    for path in paths:
        if path in notes:
            note = notes[path]
            if note.is_index:
                note = Note(
                    rel_path=note.rel_path,
                    title=preferred_index_title(note.rel_path, note.title),
                    frontmatter=note.frontmatter,
                    top_folder=note.top_folder,
                    parent_folder=note.parent_folder,
                    stem=note.stem,
                    is_index=note.is_index,
                )
            resolved.append(note)
            continue
        rel = norm_path(path)
        fallback = PAPER_DOSSIER_FALLBACKS.get(rel)
        if fallback:
            fallback_rel = norm_path(fallback)
            if fallback_rel in notes:
                note = notes[fallback_rel]
                if note.is_index:
                    note = Note(
                        rel_path=note.rel_path,
                        title=preferred_index_title(note.rel_path, note.title),
                        frontmatter=note.frontmatter,
                        top_folder=note.top_folder,
                        parent_folder=note.parent_folder,
                        stem=note.stem,
                        is_index=note.is_index,
                    )
                resolved.append(note)
                continue
        stem = Path(rel).stem
        if stem == "_Index":
            title = preferred_index_title(rel, Path(rel).parent.name)
        else:
            title = slug_title(stem)
        resolved.append(
            Note(
                rel_path=rel,
                title=title,
                frontmatter={},
                top_folder=rel.split("/", 1)[0],
                parent_folder=Path(rel).parent.as_posix(),
                stem=stem,
                is_index=stem == "_Index",
            )
        )
    return sorted(resolved, key=lambda note: (note.title.lower(), note.rel_path.lower()))


def resolve_existing_paths(notes: dict[str, Note], paths: list[str]) -> list[Note]:
    resolved: list[Note] = []
    seen: set[str] = set()
    for path in paths:
        candidates = [norm_path(path)]
        fallback = PAPER_DOSSIER_FALLBACKS.get(norm_path(path))
        if fallback:
            candidates.append(norm_path(fallback))
        for candidate in candidates:
            if candidate not in notes:
                continue
            note = notes[candidate]
            if note.is_index:
                note = Note(
                    rel_path=note.rel_path,
                    title=preferred_index_title(note.rel_path, note.title),
                    frontmatter=note.frontmatter,
                    top_folder=note.top_folder,
                    parent_folder=note.parent_folder,
                    stem=note.stem,
                    is_index=note.is_index,
                )
            if note.rel_path not in seen:
                resolved.append(note)
                seen.add(note.rel_path)
            break
    return sorted(resolved, key=lambda note: (note.title.lower(), note.rel_path.lower()))


def bullet_links(items: list[tuple[str, str]]) -> list[str]:
    lines: list[str] = []
    for rel_path, label in items:
        lines.append(f"- {wikilink(rel_path, label)}")
    return lines


def external_link(path: str, label: str) -> str:
    return f"[{label}](file:///{path.replace(' ', '%20')})"


def note_section(title: str, items: list[Note]) -> list[str]:
    if not items:
        return []
    lines = [f"## {title}", ""]
    for note in items:
        lines.append(f"- {wikilink(note.rel_path, note.title)}")
    lines.append("")
    return lines


def cluster_note(title: str, summary: str, items: list[Note]) -> str:
    lines = [f"# {title}", "", summary, ""]
    lines.extend(note_section("相关笔记", items) or ["## 相关笔记", "", "- 暂无匹配笔记", ""])
    return "\n".join(lines).rstrip() + "\n"


def build_sectioned_note(
    title: str,
    summary: str,
    sections: list[tuple[str, list[str]]],
    notes: dict[str, Note],
) -> str:
    lines = [f"# {title}", "", summary, ""]
    rendered = False
    for heading, paths in sections:
        items = resolve_paths(notes, paths)
        if not items:
            continue
        rendered = True
        lines.extend(note_section(heading, items))
    if not rendered:
        lines.extend(["## 相关笔记", "", "- 暂无匹配笔记", ""])
    return "\n".join(lines).rstrip() + "\n"


def build_attempt_theme_navigation(notes: dict[str, Note]) -> str:
    lines = [
        "# 尝试主题导航",
        "",
        "这页把早期原型、验证尝试和工具排查重新按主题串起来，方便按问题线索回找。",
        "",
        "## 主题入口",
        "",
        *bullet_links(
            [
                (ATTEMPT_PROTOTYPE_OVERVIEW_PATH, "原型路线总览"),
                (ATTEMPT_VAULT_PROTOTYPES_PATH, "Vault与论文流程原型索引"),
                (ATTEMPT_VALIDATION_PROTOTYPES_PATH, "验证表达与基线原型索引"),
                (ATTEMPT_CODEX_DIAGNOSTICS_PATH, "Codex App 线程排查索引"),
            ]
        ),
        "",
        "## 阅读区入口",
        "",
        f"- {wikilink(ATTEMPT_READER_ENTRY_PATH, '尝试主题阅读入口')}",
        "",
    ]
    return "\n".join(lines)


def build_attempt_reader_entry() -> str:
    lines = [
        "# 尝试主题阅读入口",
        "",
        "这页适合从“我记得之前试过什么”出发，直接跳到对应的原型簇和排查簇。",
        "",
        "## 先从这里进",
        "",
        *bullet_links(
            [
                (ATTEMPT_PROTOTYPE_OVERVIEW_PATH, "原型路线总览"),
                (ATTEMPT_VAULT_PROTOTYPES_PATH, "Vault与论文流程原型索引"),
                (ATTEMPT_VALIDATION_PROTOTYPES_PATH, "验证表达与基线原型索引"),
                (ATTEMPT_CODEX_DIAGNOSTICS_PATH, "Codex App 线程排查索引"),
                (ATTEMPT_THEME_NAV_PATH, "尝试主题导航"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_conversation_theme_navigation() -> str:
    lines = [
        "# 高价值会话主题导航",
        "",
        "这页不按日期翻会话，而是按你真正会回找的问题主题组织。",
        "",
        "## 主题簇",
        "",
        *bullet_links(
            [
                (CONVERSATION_SYSTEM_INDEX_PATH, "研究系统与知识库演进会话索引"),
                (CONVERSATION_LEARNING_INDEX_PATH, "OCT学习与逐篇文献会话索引"),
                (CONVERSATION_DECONV_INDEX_PATH, "反卷积与验证会话索引"),
                (CONVERSATION_TOOLING_INDEX_PATH, "Codex与工具恢复会话索引"),
                (CONVERSATION_CAREER_INDEX_PATH, "就业与行业观察会话索引"),
            ]
        ),
        "",
        "## 相关协作入口",
        "",
        f"- {wikilink('09_Conversations/Tri-Agent/_Index.md', 'Tri-Agent 会话索引')}",
        "",
    ]
    return "\n".join(lines)


def build_conversation_reader_entry() -> str:
    lines = [
        "# 高价值会话入口",
        "",
        "这页适合你记得的是“我们讨论过哪类问题”，但不想先回忆具体日期。",
        "",
        "## 常用跳转",
        "",
        *bullet_links(
            [
                (CONVERSATION_THEME_NAV_PATH, "高价值会话主题导航"),
                (CONVERSATION_DECONV_INDEX_PATH, "反卷积与验证会话索引"),
                (CONVERSATION_LEARNING_INDEX_PATH, "OCT学习与逐篇文献会话索引"),
                (CONVERSATION_SYSTEM_INDEX_PATH, "研究系统与知识库演进会话索引"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_progress_theme_navigation() -> str:
    lines = [
        "# 研究推进主线导航",
        "",
        "> [!summary]",
        "> 这页不是按目录翻文件，而是按“研究现在沿着哪条线推进”来回找。",
        "",
        "## 核心研究线",
        "",
        *bullet_links(
            [
                (PROGRESS_MANUSCRIPT_INDEX_PATH, "反卷积验证与稿件主线索引"),
                (PROGRESS_SPECTROMETER_INDEX_PATH, "OCT光谱仪系统专项索引"),
                (PROGRESS_PIPELINE_INDEX_PATH, "知识库与文献管线索引"),
            ]
        ),
        "",
        "## 按关键对象回找",
        "",
        f"- 当前主张与判断：{wikilink(PROGRESS_CORE_CONCLUSION_GUIDE_PATH, '核心结论入口')}",
        f"- 单篇关键论文：{wikilink(PROGRESS_KEY_PAPER_GUIDE_PATH, "关键论文档案入口")}",
        f"- 方法奠基论文：{wikilink(PROGRESS_FOUNDATION_PAPER_GUIDE_PATH, '方法奠基论文入口')}",
        f"- 系统专用化论文：{wikilink(PROGRESS_SYSTEM_PAPER_GUIDE_PATH, '系统专用化论文入口')}",
        f"- 反卷积主线论文：{wikilink(PROGRESS_DECONV_PAPER_GUIDE_PATH, '反卷积主线论文入口')}",
        f"- 单次关键实验实例：{wikilink(PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, "关键实验实例入口")}",
        f"- 验证成功样例：{wikilink(PROGRESS_SUCCESS_EXPERIMENT_GUIDE_PATH, '验证成功样例入口')}",
        f"- 失败与排障样例：{wikilink(PROGRESS_FAILURE_EXPERIMENT_GUIDE_PATH, '失败与排障样例入口')}",
        f"- 系统校准样例：{wikilink(PROGRESS_CALIBRATION_EXPERIMENT_GUIDE_PATH, '系统校准样例入口')}",
        "",
        "## 支撑协作线",
        "",
        *bullet_links(
            [
                (PROGRESS_TRI_AGENT_INDEX_PATH, "Tri-Agent与控制平面索引"),
                ("10_Tasks/_Index.md", "任务索引"),
            ]
        ),
        "",
        "## 阅读入口",
        "",
        *bullet_links(
            [
                (PROGRESS_READER_ENTRY_PATH, "研究主线入口"),
                (PROGRESS_EVIDENCE_READER_ENTRY_PATH, "研究问题证据入口"),
                (PROJECT_DECISION_READER_ENTRY_PATH, "项目推进与决策入口"),
                (CONVERSATION_READER_ENTRY_PATH, "高价值会话入口"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_core_conclusion_guide(notes: dict[str, Note]) -> str:
    lines = [
        "# 核心结论入口",
        "",
        "把当前已经形成的判断按“反卷积 / 系统 / 交付治理”三条线收拢，适合你先回找结论，再反查论文、实验和会话依据。",
        "",
        "## 三条结论回找线",
        "",
        *bullet_links(
            [
                (PROGRESS_DECONV_CONCLUSION_GUIDE_PATH, "反卷积结论入口"),
                (PROGRESS_SYSTEM_CONCLUSION_GUIDE_PATH, "系统判断入口"),
                (PROGRESS_DELIVERY_CONCLUSION_GUIDE_PATH, "交付与治理结论入口"),
            ]
        ),
        "",
    ]
    for heading, paths in PROGRESS_CORE_CONCLUSION_GUIDE_SECTIONS:
        items = resolve_paths(notes, paths)
        if items:
            lines.extend(note_section(heading, items))
    return "\n".join(lines).rstrip() + "\n"


def build_key_paper_guide(notes: dict[str, Note]) -> str:
    lines = [
        "# 关键论文档案入口",
        "",
        "把最常回找的关键论文按“方法奠基 / 系统专用化 / 反卷积主线”三条线重排。当前 workspace 会优先落到已经在库的论文笔记，而不是依赖缺失的 dossier 目录。",
        "",
        "## 三条论文回找线",
        "",
        *bullet_links(
            [
                (PROGRESS_FOUNDATION_PAPER_GUIDE_PATH, "方法奠基论文入口"),
                (PROGRESS_SYSTEM_PAPER_GUIDE_PATH, "系统专用化论文入口"),
                (PROGRESS_DECONV_PAPER_GUIDE_PATH, "反卷积主线论文入口"),
            ]
        ),
        "",
        "## 稳定入口",
        "",
        *bullet_links(
            [
                ("02_Literature/Papers/_Index.md", "文献论文索引"),
                (LITERATURE_READER_ENTRY_PATH, "文献阅读起步入口"),
                (LITERATURE_ROUTE_MAP_PATH, "桥接论文阅读路线图"),
                (LITERATURE_SYSTEM_ROUTE_PATH, "系统专用化阅读路线"),
                (LITERATURE_DECONV_ROUTE_PATH, "反卷积主线阅读路线"),
                (LITERATURE_BRIDGE_SHELF_PATH, "桥接论文书架"),
                (RETRIEVAL_READER_ENTRY_PATH, "检索与文献管理总览"),
                ("06_Writing/translated-papers/_Index.md", "译文索引"),
            ]
        ),
        "",
    ]
    for heading, paths in PROGRESS_KEY_PAPER_GUIDE_SECTIONS:
        items = resolve_existing_paths(notes, paths)
        if items:
            lines.extend(note_section(heading, items))
    return "\n".join(lines).rstrip() + "\n"


def build_paper_line_guide(
    title: str,
    summary: str,
    sections: list[tuple[str, list[str]]],
    notes: dict[str, Note],
) -> str:
    lines = [
        f"# {title}",
        "",
        summary,
        "",
        "## 稳定入口",
        "",
        *bullet_links(
            [
                ("02_Literature/Papers/_Index.md", "文献论文索引"),
                (LITERATURE_READER_ENTRY_PATH, "文献阅读起步入口"),
                (LITERATURE_BRIDGE_SHELF_PATH, "桥接论文书架"),
                (RETRIEVAL_READER_ENTRY_PATH, "检索与文献管理总览"),
            ]
        ),
        "",
    ]
    rendered = False
    for heading, paths in sections:
        items = resolve_existing_paths(notes, paths)
        if not items:
            continue
        rendered = True
        lines.extend(note_section(heading, items))
    if not rendered:
        lines.extend(
            [
                "## 当前可走的入口",
                "",
                "- 当前 workspace 里这条线的单篇论文笔记还没完全落盘，但桥接批次已经备好。",
                f"- 先从 {wikilink(LITERATURE_BRIDGE_SHELF_PATH, '桥接论文书架')} 找对应批次，再回到 {wikilink(LITERATURE_READER_ENTRY_PATH, '文献阅读起步入口')} 确认阅读顺序；如果要继续补入库动作，再去 {wikilink(RETRIEVAL_READER_ENTRY_PATH, '检索与文献管理总览')}。",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_key_experiment_guide(notes: dict[str, Note]) -> str:
    lines = [
        "# 关键实验实例入口",
        "",
        "把最常回找的单次实验实例按“验证成功 / 失败排障 / 系统校准”三条线重排，再补上写作锚点，方便从争议点直接落到具体实例。",
        "",
        "## 三条实验回找线",
        "",
        *bullet_links(
            [
                (PROGRESS_SUCCESS_EXPERIMENT_GUIDE_PATH, "验证成功样例入口"),
                (PROGRESS_FAILURE_EXPERIMENT_GUIDE_PATH, "失败与排障样例入口"),
                (PROGRESS_CALIBRATION_EXPERIMENT_GUIDE_PATH, "系统校准样例入口"),
            ]
        ),
        "",
    ]
    for heading, paths in PROGRESS_KEY_EXPERIMENT_GUIDE_SECTIONS:
        items = resolve_paths(notes, paths)
        if items:
            lines.extend(note_section(heading, items))
    return "\n".join(lines).rstrip() + "\n"


def build_progress_reader_entry() -> str:
    lines = [
        "# 研究主线入口",
        "",
        "这页适合你记得的是“现在研究推进到哪一段”，但不想先在 `04_Progress` 和 `10_Tasks` 里逐个翻文件。",
        "",
        "## 核心推进线",
        "",
        f"- 反卷积验证、证据边界和稿件推进：{wikilink(PROGRESS_MANUSCRIPT_INDEX_PATH, '反卷积验证与稿件主线索引')}",
        f"- OCT 光谱仪系统专项判断：{wikilink(PROGRESS_SPECTROMETER_INDEX_PATH, 'OCT光谱仪系统专项索引')}",
        f"- Zotero、翻译和知识库管线演进：{wikilink(PROGRESS_PIPELINE_INDEX_PATH, '知识库与文献管线索引')}",
        "",
        "## 按研究问题回找",
        "",
        f"- 研究问题总入口：{wikilink(PROGRESS_EVIDENCE_READER_ENTRY_PATH, '研究问题证据入口')}",
        f"- 问题链总览：{wikilink(PROGRESS_EVIDENCE_NAV_PATH, '研究问题证据链导航')}",
        "",
        "## 按当前判断回找",
        "",
        f"- 当前核心结论：{wikilink(PROGRESS_CORE_CONCLUSION_GUIDE_PATH, '核心结论入口')}",
        "",
        "## 按关键对象回找",
        "",
        *bullet_links(
            [
                (PROGRESS_CORE_CONCLUSION_GUIDE_PATH, "核心结论入口"),
                (PROGRESS_KEY_PAPER_GUIDE_PATH, "关键论文档案入口"),
                (PROGRESS_FOUNDATION_PAPER_GUIDE_PATH, "方法奠基论文入口"),
                (PROGRESS_SYSTEM_PAPER_GUIDE_PATH, "系统专用化论文入口"),
                (PROGRESS_DECONV_PAPER_GUIDE_PATH, "反卷积主线论文入口"),
                (PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, "关键实验实例入口"),
                (PROGRESS_SUCCESS_EXPERIMENT_GUIDE_PATH, "验证成功样例入口"),
                (PROGRESS_FAILURE_EXPERIMENT_GUIDE_PATH, "失败与排障样例入口"),
                (PROGRESS_CALIBRATION_EXPERIMENT_GUIDE_PATH, "系统校准样例入口"),
            ]
        ),
        "",
        "## 支撑协作线",
        "",
        f"- Tri-Agent、任务总线和控制平面：{wikilink(PROGRESS_TRI_AGENT_INDEX_PATH, 'Tri-Agent与控制平面索引')}",
        f"- 高价值对话证据：{wikilink(CONVERSATION_THEME_NAV_PATH, '高价值会话主题导航')}",
        "",
        "## 和原目录的关系",
        "",
        "- `04_Progress` 仍然保留按状态和决策沉淀的原始结构；这页只负责把主线重新串起来。",
        "",
    ]
    return "\n".join(lines)


def build_progress_evidence_navigation() -> str:
    lines = [
        "# 研究问题证据链导航",
        "",
        "这页按“你现在到底想回答哪个研究问题”来组织入口，每条链都直接接到进展、实验、论文、写作和对话证据。",
        "",
        "## 三条核心证据链",
        "",
        *bullet_links(
            [
                (PROGRESS_DECONV_EVIDENCE_PATH, "反卷积真实增益证据链"),
                (PROGRESS_SYSTEM_EVIDENCE_PATH, "OCT系统专用化证据链"),
                (PROGRESS_DELIVERY_EVIDENCE_PATH, "知识库持续交付证据链"),
            ]
        ),
        "",
        "## 按关键对象下钻",
        "",
        *bullet_links(
            [
                (PROGRESS_CORE_CONCLUSION_GUIDE_PATH, "核心结论入口"),
                (PROGRESS_KEY_PAPER_GUIDE_PATH, "关键论文档案入口"),
                (PROGRESS_FOUNDATION_PAPER_GUIDE_PATH, "方法奠基论文入口"),
                (PROGRESS_SYSTEM_PAPER_GUIDE_PATH, "系统专用化论文入口"),
                (PROGRESS_DECONV_PAPER_GUIDE_PATH, "反卷积主线论文入口"),
                (PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, "关键实验实例入口"),
                (PROGRESS_SUCCESS_EXPERIMENT_GUIDE_PATH, "验证成功样例入口"),
                (PROGRESS_FAILURE_EXPERIMENT_GUIDE_PATH, "失败与排障样例入口"),
                (PROGRESS_CALIBRATION_EXPERIMENT_GUIDE_PATH, "系统校准样例入口"),
            ]
        ),
        "",
        "## 上游导航",
        "",
        *bullet_links(
            [
                (PROGRESS_THEME_NAV_PATH, "研究推进主线导航"),
                (PROGRESS_READER_ENTRY_PATH, "研究主线入口"),
                (CONVERSATION_THEME_NAV_PATH, "高价值会话主题导航"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_progress_evidence_reader_entry() -> str:
    lines = [
        "# 研究问题证据入口",
        "",
        "这页适合你脑子里已经是一个研究问题，比如“反卷积到底能不能证明有效”，而不是某个目录名。",
        "",
        "## 先按问题进",
        "",
        *bullet_links(
            [
                (PROGRESS_EVIDENCE_NAV_PATH, "研究问题证据链导航"),
                (PROGRESS_DECONV_EVIDENCE_PATH, "反卷积真实增益证据链"),
                (PROGRESS_SYSTEM_EVIDENCE_PATH, "OCT系统专用化证据链"),
                (PROGRESS_DELIVERY_EVIDENCE_PATH, "知识库持续交付证据链"),
            ]
        ),
        "",
        "## 也可以按证据对象找",
        "",
        *bullet_links(
            [
                (PROGRESS_CORE_CONCLUSION_GUIDE_PATH, "核心结论入口"),
                (PROGRESS_KEY_PAPER_GUIDE_PATH, "关键论文档案入口"),
                (PROGRESS_FOUNDATION_PAPER_GUIDE_PATH, "方法奠基论文入口"),
                (PROGRESS_SYSTEM_PAPER_GUIDE_PATH, "系统专用化论文入口"),
                (PROGRESS_DECONV_PAPER_GUIDE_PATH, "反卷积主线论文入口"),
                (PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, "关键实验实例入口"),
                (PROGRESS_SUCCESS_EXPERIMENT_GUIDE_PATH, "验证成功样例入口"),
                (PROGRESS_FAILURE_EXPERIMENT_GUIDE_PATH, "失败与排障样例入口"),
                (PROGRESS_CALIBRATION_EXPERIMENT_GUIDE_PATH, "系统校准样例入口"),
            ]
        ),
        "",
        "## 如果你记得的是推进阶段",
        "",
        *bullet_links(
            [
                (PROGRESS_READER_ENTRY_PATH, "研究主线入口"),
                (PROGRESS_THEME_NAV_PATH, "研究推进主线导航"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_folder_index(folder: str, notes: dict[str, Note]) -> str:
    folder_notes = descendants(notes, folder)
    direct = direct_notes(notes, folder)
    children = child_dirs(notes, folder)
    title = INDEX_TITLE_MAP.get(folder, f"{folder.split('/')[-1]} 索引")
    lines = [f"# {title}", "", f"- 目录：`{folder}`", f"- 笔记数：`{len(folder_notes)}`", ""]
    if children:
        lines.extend(["## 子目录入口", ""])
        for child in children:
            lines.append(f"- {wikilink(f'{child}/_Index.md', child.split('/')[-1])}")
        lines.append("")
    if direct:
        lines.extend(note_section("本层笔记", direct))
    return "\n".join(lines).rstrip() + "\n"


def build_papers_index(notes: dict[str, Note]) -> str:
    papers = [
        note
        for note in descendants(notes, "02_Literature/Papers")
        if note.parent_folder == "02_Literature/Papers"
        and note.frontmatter.get("library_status") != "synthetic-example"
    ]
    papers.sort(key=lambda note: (note.frontmatter.get("year", ""), note.title.lower(), note.rel_path.lower()))
    lines = ["# 文献论文索引", "", "## 论文条目", ""]
    for note in papers:
        label = note.frontmatter.get("title") or note.title
        lines.append(f"- {wikilink(note.rel_path, label)}")
    lines.append("")
    return "\n".join(lines)


def build_zotero_index(notes: dict[str, Note]) -> str:
    items = [note for note in descendants(notes, "12_Zotero/04_Item-Backfills") if note.parent_folder == "12_Zotero/04_Item-Backfills"]
    items.sort(key=lambda note: note.title.lower())
    lines = ["# Zotero 回填索引", "", "## 回填条目", ""]
    for note in items:
        label = note.frontmatter.get("zotero_key", "").strip()
        label = f"{label} - {note.title}" if label else note.title
        lines.append(f"- {wikilink(note.rel_path, label)}")
    lines.append("")
    return "\n".join(lines)


def build_home_navigation(notes: dict[str, Note]) -> str:
    lines = [
        "# 知识库导航中心",
        "",
        "这页只保留第一屏最值得进的入口。你不需要先记目录名，先按“判断 / 问题 / 对象 / 说明”四种方式进就够了。",
        "",
        "## 第一屏入口",
        "",
        *bullet_links(
            [
                (PROGRESS_CORE_CONCLUSION_GUIDE_PATH, "核心结论入口"),
                (PROGRESS_READER_ENTRY_PATH, "研究主线入口"),
                (PROGRESS_EVIDENCE_READER_ENTRY_PATH, "研究问题证据入口"),
                (PROGRESS_KEY_PAPER_GUIDE_PATH, "关键论文档案入口"),
                (PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, "关键实验实例入口"),
            ]
        ),
        "",
        "## 按你现在要做的事进",
        "",
        f"- 第一次回到这个库，想先别迷路：{wikilink(READER_START_ENTRY_PATH, '新手起步入口')}",
        f"- 想先把 OCT 系统图、成像原理和分辨率地基抓清：{wikilink(SYSTEM_READER_ENTRY_PATH, 'OCT系统与原理起步入口')}",
        f"- 想先从论文把全局抓起来：{wikilink(LITERATURE_READER_ENTRY_PATH, '文献阅读起步入口')}",
        f"- 想先判断还缺哪篇文献、从哪补、补回来怎么入库：{wikilink(RETRIEVAL_READER_ENTRY_PATH, '检索与文献管理总览')}",
        f"- 想先把当前缺在 workspace 的早期关键论文接回可写阅读区：{wikilink(LITERATURE_BRIDGE_SHELF_PATH, '桥接论文书架')}",
        f"- 想先把实验闭环和验证顺序抓清：{wikilink(EXPERIMENT_READER_ENTRY_PATH, '实验验证起步入口')}",
        f"- 想先把图示阅读和表达方式抓清：{wikilink(FIGURE_READER_ENTRY_PATH, '图示表达起步入口')}",
        f"- 想先把可写主张、图文表达和风险边界抓清：{wikilink(WRITING_READER_ENTRY_PATH, '写作表达起步入口')}",
        f"- 想把反复出现的术语、创新点和长期问题串起来：{wikilink(TERM_READER_ENTRY_PATH, '术语与问题起步入口')}",
        f"- 想确认现在最该推进哪条、风险和节奏怎么排：{wikilink(PROJECT_DECISION_READER_ENTRY_PATH, '项目推进与决策入口')}",
        f"- 想直接看还没做完什么以及下一步怎么继续：{wikilink(ACTION_READER_ENTRY_PATH, '行动起步入口')}",
        f"- 想先把日常执行、AI协作沉淀和办事流程放稳：{wikilink(EXECUTION_READER_ENTRY_PATH, '执行规范起步入口')}",
        f"- 先看当前已经形成的判断：{wikilink(PROGRESS_CORE_CONCLUSION_GUIDE_PATH, '核心结论入口')}",
        f"- 先追某个问题到证据：{wikilink(PROGRESS_EVIDENCE_READER_ENTRY_PATH, '研究问题证据入口')}",
        f"- 先找具体论文和实验：{wikilink(PROGRESS_KEY_PAPER_GUIDE_PATH, '关键论文档案入口')} / {wikilink(PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, '关键实验实例入口')}",
        f"- 先回看关键讨论和历史尝试：{wikilink(CONVERSATION_READER_ENTRY_PATH, '高价值会话入口')} / {wikilink(ATTEMPT_READER_ENTRY_PATH, '历史尝试主题入口')}",
        "",
        "## 系统说明与总索引",
        "",
        *bullet_links(
            [
                ("00_Home/目录总索引.md", "目录总索引"),
                ("00_Home/分类逻辑说明.md", "分类底层逻辑"),
                ("00_Home/知识库体检报告.md", "知识库体检报告"),
                ("02_Literature/Papers/_Index.md", "论文档案索引"),
                ("00_Home/System-Map.md", "System Map"),
                ("00_Home/Search-Guide.md", "Search Guide"),
                ("00_Home/Research-Dashboard.md", "Research Dashboard"),
                ("13_阅读区/00_从这里开始/项目内容全景图.md", "项目内容全景图"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_home_landing() -> str:
    lines = [
        "# Home",
        "",
        "默认首页现在只做第一屏跳转。完整导航请进入 [[知识库导航中心]]。",
        "",
        "## 快速进入",
        "",
        *bullet_links(
            [
                ("00_Home/知识库导航中心.md", "知识库导航中心"),
                (READER_START_ENTRY_PATH, "新手起步入口"),
                (SYSTEM_READER_ENTRY_PATH, "OCT系统与原理起步入口"),
                (LITERATURE_READER_ENTRY_PATH, "文献阅读起步入口"),
                (RETRIEVAL_READER_ENTRY_PATH, "检索与文献管理总览"),
                (EXPERIMENT_READER_ENTRY_PATH, "实验验证起步入口"),
                (FIGURE_READER_ENTRY_PATH, "图示表达起步入口"),
                (WRITING_READER_ENTRY_PATH, "写作表达起步入口"),
                (TERM_READER_ENTRY_PATH, "术语与问题起步入口"),
                (PROJECT_DECISION_READER_ENTRY_PATH, "项目推进与决策入口"),
                (ACTION_READER_ENTRY_PATH, "行动起步入口"),
                (EXECUTION_READER_ENTRY_PATH, "执行规范起步入口"),
                (PROGRESS_CORE_CONCLUSION_GUIDE_PATH, "核心结论入口"),
                (PROGRESS_READER_ENTRY_PATH, "研究主线入口"),
                (PROGRESS_EVIDENCE_READER_ENTRY_PATH, "研究问题证据入口"),
                (PROGRESS_KEY_PAPER_GUIDE_PATH, "关键论文档案入口"),
                (PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, "关键实验实例入口"),
            ]
        ),
        "",
        "## 说明页",
        "",
        *bullet_links(
            [
                ("00_Home/System-Map.md", "System Map"),
                ("00_Home/Search-Guide.md", "Search Guide"),
                ("00_Home/目录总索引.md", "目录总索引"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_reader_start_entry() -> str:
    lines = [
        "# 新手起步入口",
        "",
        "如果你刚打开这个知识库，先不要钻目录。先看总览，再决定是从判断、问题、论文还是实验进入，会更快回到状态。",
        "",
        "## 第一次打开先看",
        "",
        *bullet_links(
            [
                ("00_Home/Home.md", "Home"),
                ("00_Home/知识库导航中心.md", "知识库导航中心"),
                ("13_阅读区/00_从这里开始/项目内容全景图.md", "项目内容全景图"),
                ("13_阅读区/00_从这里开始/阅读总览.md", "阅读总览"),
            ]
        ),
        "",
        "## 按你现在的需要进",
        "",
        f"- 想先知道现在已经形成了什么判断：{wikilink(PROGRESS_CORE_CONCLUSION_GUIDE_PATH, '核心结论入口')}",
        f"- 想先把系统图、成像逻辑和系统参数读明白：{wikilink(SYSTEM_READER_ENTRY_PATH, 'OCT系统与原理起步入口')}",
        f"- 想先从论文把领域和主线抓清：{wikilink(LITERATURE_READER_ENTRY_PATH, '文献阅读起步入口')}",
        f"- 想先把补文献、Zotero 接入和检索方向理顺：{wikilink(RETRIEVAL_READER_ENTRY_PATH, '检索与文献管理总览')}",
        f"- 想先把当前缺在 workspace 的早期关键论文接回阅读区：{wikilink(LITERATURE_BRIDGE_SHELF_PATH, '桥接论文书架')}",
        f"- 想先把实验设计、baseline 和判据接成闭环：{wikilink(EXPERIMENT_READER_ENTRY_PATH, '实验验证起步入口')}",
        f"- 想先把看图、审图和自己画图的逻辑接顺：{wikilink(FIGURE_READER_ENTRY_PATH, '图示表达起步入口')}",
        f"- 想把前面的理解真正转成可写论断：{wikilink(WRITING_READER_ENTRY_PATH, '写作表达起步入口')}",
        f"- 想把关键术语、创新点和长期疑问放到一起看：{wikilink(TERM_READER_ENTRY_PATH, '术语与问题起步入口')}",
        f"- 想知道现在该推进什么、先盯哪类风险：{wikilink(PROJECT_DECISION_READER_ENTRY_PATH, '项目推进与决策入口')}",
        f"- 想直接看还没做完什么、今天从哪一步继续：{wikilink(ACTION_READER_ENTRY_PATH, '行动起步入口')}",
        f"- 想先把执行规范、AI协作沉淀和办事流程理顺：{wikilink(EXECUTION_READER_ENTRY_PATH, '执行规范起步入口')}",
        f"- 想顺着项目主线快速回到研究状态：{wikilink(PROGRESS_READER_ENTRY_PATH, '研究主线入口')}",
        f"- 想围着某个问题追证据：{wikilink(PROGRESS_EVIDENCE_READER_ENTRY_PATH, '研究问题证据入口')}",
        f"- 想直接找论文和实验：{wikilink(PROGRESS_KEY_PAPER_GUIDE_PATH, '关键论文档案入口')} / {wikilink(PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, '关键实验实例入口')}",
        f"- 想先按讨论和历史尝试找脉络：{wikilink(CONVERSATION_READER_ENTRY_PATH, '高价值会话入口')} / {wikilink(ATTEMPT_READER_ENTRY_PATH, '尝试主题阅读入口')}",
        "",
        "## 如果你想按顺序系统进入",
        "",
        *bullet_links(
            [
                ("13_阅读区/00_从这里开始/推荐阅读顺序.md", "推荐阅读顺序"),
                ("13_阅读区/00_从这里开始/阅读总览.md", "阅读总览"),
                ("13_阅读区/00_从这里开始/项目内容全景图.md", "项目内容全景图"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_reader_start_index(notes: dict[str, Note]) -> str:
    direct = direct_notes(notes, "13_阅读区/00_从这里开始")
    lines = [
        "# 阅读区起步索引",
        "",
        "这页只保留起步区最常用的入口。先从这里定向，再决定要不要进入更深的阅读层。",
        "",
        "## 起步入口",
        "",
        *bullet_links(
            [
                (READER_START_ENTRY_PATH, "新手起步入口"),
                ("13_阅读区/00_从这里开始/推荐阅读顺序.md", "推荐阅读顺序"),
                ("13_阅读区/00_从这里开始/阅读总览.md", "阅读总览"),
                ("13_阅读区/00_从这里开始/项目内容全景图.md", "项目内容全景图"),
            ]
        ),
        "",
        "## 和主系统接起来",
        "",
        *bullet_links(
            [
                ("00_Home/知识库导航中心.md", "知识库导航中心"),
                (PROGRESS_CORE_CONCLUSION_GUIDE_PATH, "核心结论入口"),
                (SYSTEM_READER_ENTRY_PATH, "OCT系统与原理起步入口"),
                (TERM_READER_ENTRY_PATH, "术语与问题起步入口"),
                (RETRIEVAL_READER_ENTRY_PATH, "检索与文献管理总览"),
                (ACTION_READER_ENTRY_PATH, "行动起步入口"),
                (EXECUTION_READER_ENTRY_PATH, "执行规范起步入口"),
                (PROGRESS_READER_ENTRY_PATH, "研究主线入口"),
                (PROGRESS_EVIDENCE_READER_ENTRY_PATH, "研究问题证据入口"),
                (PROGRESS_KEY_PAPER_GUIDE_PATH, "关键论文档案入口"),
                (PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, "关键实验实例入口"),
            ]
        ),
        "",
    ]
    if direct:
        lines.extend(note_section("本层阅读页", direct))
    return "\n".join(lines).rstrip() + "\n"


def build_system_reader_entry() -> str:
    lines = [
        "# OCT系统与原理起步入口",
        "",
        "如果你今天准备补系统和原理地基，不要先背元件名。先把成像为什么成立、系统参数为什么影响分辨率和稳定性、系统图为什么能接到性能判断想清，再回去读论文会快很多。",
        "",
        "## 如果你只有 30 分钟",
        "",
        *bullet_links(
            [
                ("13_阅读区/01_OCT系统与原理/系统与原理总览.md", "系统与原理总览"),
                ("03_Concepts/01_OCT-Physics/oct-image-formation-and-resolution.md", "oct-image-formation-and-resolution"),
                ("03_Concepts/10_Figure-and-Image-Analysis/reading-oct-system-schematics-from-physics-to-performance.md", "reading-oct-system-schematics-from-physics-to-performance"),
            ]
        ),
        "",
        "## 今天先抓哪条原理线",
        "",
        "- 先抓成像为什么成立：把图像形成、相干性和分辨率之间的关系放稳。",
        "- 再抓系统为什么会影响结果：系统校准、采样、k 线性化和色散补偿会直接决定你后面看到的图像质量。",
        "- 如果今天是边看论文边补地基，就顺手把系统图和性能判断连起来，不要把硬件、信号和算法拆开看。",
        "",
        "## 按你今天的任务进",
        "",
        f"- 想先看这一层最完整的总览：{wikilink('13_阅读区/01_OCT系统与原理/系统与原理总览.md', '系统与原理总览')}",
        f"- 想先补 OCT 成像和分辨率地基：{wikilink('03_Concepts/01_OCT-Physics/oct-image-formation-and-resolution.md', 'oct-image-formation-and-resolution')}",
        f"- 想把系统图读懂，并接到性能判断：{wikilink('03_Concepts/10_Figure-and-Image-Analysis/reading-oct-system-schematics-from-physics-to-performance.md', 'reading-oct-system-schematics-from-physics-to-performance')}",
        f"- 想把系统原理接回论文阅读：{wikilink(LITERATURE_READER_ENTRY_PATH, '文献阅读起步入口')}",
        f"- 想把系统与参数理解接回图示表达：{wikilink(FIGURE_READER_ENTRY_PATH, '图示表达起步入口')}",
        f"- 想把反复出现的术语和长期问题一起带着看：{wikilink(TERM_READER_ENTRY_PATH, '术语与问题起步入口')}",
        "",
        "## 对应底层原理入口",
        "",
        *bullet_links(
            [
                ("03_Concepts/01_OCT-Physics/oct-image-formation-and-resolution.md", "oct-image-formation-and-resolution"),
                ("03_Concepts/01_OCT-Physics/mutual-coherence-and-cross-spectral-density-for-oct.md", "mutual-coherence-and-cross-spectral-density-for-oct"),
                ("03_Concepts/02_System-Build-and-Calibration/sd-oct-and-ss-oct-system-calibration-checklist.md", "sd-oct-and-ss-oct-system-calibration-checklist"),
                ("03_Concepts/02_System-Build-and-Calibration/sampling-k-linearization-and-dispersion-boundaries.md", "sampling-k-linearization-and-dispersion-boundaries"),
                ("03_Concepts/03_PSF-and-Imaging-Model/lateral-psf-and-space-variance.md", "lateral-psf-and-space-variance"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_system_reader_index(notes: dict[str, Note]) -> str:
    direct = [note for note in direct_notes(notes, "13_阅读区/01_OCT系统与原理") if note.rel_path != SYSTEM_READER_ENTRY_PATH]
    lines = [
        "# OCT系统与原理索引",
        "",
        "这页只保留系统与原理区最值得先点开的入口。先把成像地基、系统参数和系统图阅读接起来，再去看更深的理论细节。",
        "",
        "## 起步入口",
        "",
        *bullet_links(
            [
                (SYSTEM_READER_ENTRY_PATH, "OCT系统与原理起步入口"),
                ("13_阅读区/01_OCT系统与原理/系统与原理总览.md", "系统与原理总览"),
            ]
        ),
        "",
        "## 继续往下",
        "",
        *bullet_links(
            [
                (LITERATURE_READER_ENTRY_PATH, "文献阅读起步入口"),
                (FIGURE_READER_ENTRY_PATH, "图示表达起步入口"),
                (TERM_READER_ENTRY_PATH, "术语与问题起步入口"),
            ]
        ),
        "",
    ]
    if direct:
        lines.extend(note_section("本层阅读页", direct))
    return "\n".join(lines).rstrip() + "\n"


def build_literature_reader_entry() -> str:
    lines = [
        "# 文献阅读起步入口",
        "",
        "如果你今天准备从文献进入，不要先把论文平铺扫一遍。先分清哪篇负责评价地基、哪篇贴近方法主线、哪篇负责给你 field map，阅读效率会高很多。",
        "",
        "## 如果你只有 30 分钟",
        "",
        *bullet_links(
            [
                (LITERATURE_ROUTE_MAP_PATH, "桥接论文阅读路线图"),
                (LITERATURE_DECONV_ROUTE_PATH, "反卷积主线阅读路线"),
                (LITERATURE_SYSTEM_ROUTE_PATH, "系统专用化阅读路线"),
                (LITERATURE_BRIDGE_GUIDE_PATH, "桥接论文中文导读"),
                (LITERATURE_CHINESE_INDEX_PATH, "中文阅读版文献索引"),
                ("02_Literature/Papers/_Index.md", "文献论文索引"),
            ]
        ),
        "",
        "## 先读哪几篇，为什么先读",
        "",
        "- 先看 `2014 PSF phantom`：它是评价地基，先把 benchmark 逻辑看稳，后面才不会把“效果变尖”误当成“证据更硬”。",
        "- 再看 `2022 blind deconvolution`：它离你当前主线最近，能最快告诉你经典 blind 路线的价值、假设和边界。",
        "- 再看 `2025 review`：它能把反卷积领域的主问题、常见路线和卡点压成一张 field map。",
        "",
        f"这三篇和 bridge 批次怎么接成一条顺读路线，现在先看 {wikilink(LITERATURE_ROUTE_MAP_PATH, '桥接论文阅读路线图')}；想看每一批内部为什么这样排，再去 {wikilink(LITERATURE_BRIDGE_GUIDE_PATH, '桥接论文中文导读')}。",
        "",
        "## 按你今天的任务进",
        "",
        f"- 想直接拿到一条从 bridge 到在库论文再到实验的顺读路径：{wikilink(LITERATURE_ROUTE_MAP_PATH, '桥接论文阅读路线图')}",
        f"- 想只沿反卷积这条主线往前读：{wikilink(LITERATURE_DECONV_ROUTE_PATH, '反卷积主线阅读路线')}",
        f"- 想只沿系统专用化这条支线往前读：{wikilink(LITERATURE_SYSTEM_ROUTE_PATH, '系统专用化阅读路线')}",
        f"- 想知道每一批里先读哪篇以及各自角色：{wikilink(LITERATURE_BRIDGE_GUIDE_PATH, '桥接论文中文导读')}",
        f"- 想直接读已有完整中文材料：{wikilink(LITERATURE_CHINESE_INDEX_PATH, '中文阅读版文献索引')} / {wikilink('06_Writing/translated-papers/_Index.md', '译文索引')}",
        f"- 想先把系统图、分辨率和物理地基读稳：{wikilink(SYSTEM_READER_ENTRY_PATH, 'OCT系统与原理起步入口')}",
        f"- 想把文献判断接到实验验证：{wikilink(EXPERIMENT_READER_ENTRY_PATH, '实验验证起步入口')}",
        f"- 想进一步准备图示表达和路线图：{wikilink(FIGURE_READER_ENTRY_PATH, '图示表达起步入口')}",
        f"- 想开始整理哪些话已经能写进论文：{wikilink(WRITING_READER_ENTRY_PATH, '写作表达起步入口')}",
        f"- 想把已入库论文和当前阅读笔记集中回找：{wikilink('02_Literature/Papers/_Index.md', '文献论文索引')} / {wikilink('06_Writing/translated-papers/_Index.md', '译文索引')}",
        f"- 想先把当前缺在 workspace 的早期关键论文接回阅读区：{wikilink(LITERATURE_BRIDGE_SHELF_PATH, '桥接论文书架')}",
        f"- 想把关键术语、创新点和长期问题一起带着读：{wikilink(TERM_READER_ENTRY_PATH, '术语与问题起步入口')}",
        f"- 想把读到的判断接回当前优先级和补文献决策：{wikilink(PROJECT_DECISION_READER_ENTRY_PATH, '项目推进与决策入口')}",
        f"- 想判断下一篇该补哪篇翻译或继续往哪检索：{wikilink(RETRIEVAL_READER_ENTRY_PATH, '检索与文献管理总览')} / {wikilink('06_Writing/translation-workbench/_Index.md', '翻译工作台索引')}",
        "",
        "## 回到总入口",
        "",
        *bullet_links(
            [
                ("00_Home/知识库导航中心.md", "知识库导航中心"),
                (READER_START_ENTRY_PATH, "新手起步入口"),
                (PROGRESS_READER_ENTRY_PATH, "研究主线入口"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_literature_reader_index(notes: dict[str, Note]) -> str:
    direct = direct_notes(notes, "13_阅读区/02_文献阅读区")
    lines = [
        "# 文献阅读区索引",
        "",
        "这页只保留文献区最值得先点开的入口。先把论文角色、中文可读性和 dossier 聚合关系看清，再决定深入哪一篇。",
        "",
        "## 起步入口",
        "",
        *bullet_links(
            [
                (LITERATURE_READER_ENTRY_PATH, "文献阅读起步入口"),
                (LITERATURE_ROUTE_MAP_PATH, "桥接论文阅读路线图"),
                (LITERATURE_DECONV_ROUTE_PATH, "反卷积主线阅读路线"),
                (LITERATURE_SYSTEM_ROUTE_PATH, "系统专用化阅读路线"),
                (LITERATURE_BRIDGE_SHELF_PATH, "桥接论文书架"),
                (LITERATURE_BRIDGE_GUIDE_PATH, "桥接论文中文导读"),
                (LITERATURE_CHINESE_INDEX_PATH, "中文阅读版文献索引"),
            ]
        ),
        "",
        "## 继续往下",
        "",
        *bullet_links(
            [
                ("02_Literature/Papers/_Index.md", "文献论文索引"),
                ("06_Writing/translated-papers/_Index.md", "译文索引"),
                (RETRIEVAL_READER_ENTRY_PATH, "检索与文献管理总览"),
            ]
        ),
        "",
    ]
    if direct:
        lines.extend(note_section("本层阅读页", direct))
    return "\n".join(lines).rstrip() + "\n"


def build_literature_bridge_shelf() -> str:
    lines = [
        "# 桥接论文书架",
        "",
        "这页把已经准备好的 workspace paper bridge 批次接回当前可写阅读区。由于 `02_Literature/Papers` 子树还在拒绝创建新文件，这些缺失论文先以外部 bundle 形式备好，再由这页统一带你回找。",
        "",
        "## 现在怎么用",
        "",
        f"- 想先按论文主线找：{wikilink(PROGRESS_KEY_PAPER_GUIDE_PATH, '关键论文档案入口')} / {wikilink(PROGRESS_FOUNDATION_PAPER_GUIDE_PATH, '方法奠基论文入口')} / {wikilink(PROGRESS_SYSTEM_PAPER_GUIDE_PATH, '系统专用化论文入口')}",
        f"- 想先按当前阅读顺序和中文材料进入：{wikilink(LITERATURE_READER_ENTRY_PATH, '文献阅读起步入口')} / {wikilink(LITERATURE_ROUTE_MAP_PATH, '桥接论文阅读路线图')} / {wikilink(LITERATURE_DECONV_ROUTE_PATH, '反卷积主线阅读路线')} / {wikilink(LITERATURE_SYSTEM_ROUTE_PATH, '系统专用化阅读路线')} / {wikilink(LITERATURE_BRIDGE_GUIDE_PATH, '桥接论文中文导读')} / {wikilink('06_Writing/translated-papers/_Index.md', '译文索引')}",
        f"- 想把补回动作接到检索、Zotero 和主线：{wikilink(RETRIEVAL_READER_ENTRY_PATH, '检索与文献管理总览')} / {wikilink(PROJECT_DECISION_READER_ENTRY_PATH, '项目推进与决策入口')}",
        f"- 总览记录：{external_link(WORKSPACE_PAPER_BRIDGE_OVERVIEW_PATH, 'Workspace Paper Bridge Overview')}",
        "",
        "## 当前状态",
        "",
        "- 已准备 bridge 批次：`3`",
        "- 当前识别到的真实缺口：`0`",
        "- 这些 bridge 还没有直接写进 workspace `02_Literature/Papers`，因为该子树仍在拒绝创建新文件。",
        "",
    ]
    for batch in WORKSPACE_PAPER_BRIDGE_BATCHES:
        lines.extend(
            [
                f"## {batch['label']}",
                "",
                str(batch["summary"]),
                "",
                f"- 对应主线：{wikilink(str(batch['entry_path']), str(batch['entry_label']))}",
                f"- bundle：{external_link(str(batch['bundle_path']), str(batch['label']) + ' bundle')}",
                f"- 运行记录：{external_link(str(batch['run_path']), str(batch['label']) + ' run')}",
                f"- 包含：{'、'.join(str(paper) for paper in batch['papers'])}",
                "",
            ]
        )
    lines.extend(
        [
            "## 回到阅读入口",
            "",
            *bullet_links(
                [
                    (LITERATURE_READER_ENTRY_PATH, "文献阅读起步入口"),
                    (LITERATURE_ROUTE_MAP_PATH, "桥接论文阅读路线图"),
                    (LITERATURE_DECONV_ROUTE_PATH, "反卷积主线阅读路线"),
                    (LITERATURE_SYSTEM_ROUTE_PATH, "系统专用化阅读路线"),
                    (LITERATURE_BRIDGE_GUIDE_PATH, "桥接论文中文导读"),
                    (READER_START_ENTRY_PATH, "新手起步入口"),
                    ("00_Home/知识库导航中心.md", "知识库导航中心"),
                    (PROGRESS_KEY_PAPER_GUIDE_PATH, "关键论文档案入口"),
                    (RETRIEVAL_READER_ENTRY_PATH, "检索与文献管理总览"),
                ]
            ),
            "",
        ]
    )
    return "\n".join(lines)


def build_literature_route_map() -> str:
    lines = [
        "# 桥接论文阅读路线图",
        "",
        "这页把 bridge 批次、当前 workspace 已在库论文、译文入口和实验验证入口压成一条顺读路径。目标不是把所有论文一次读完，而是让你每一步都知道“这篇是铺地基、定 benchmark，还是直接服务当前验证主线”。",
        "",
        "## 两条细分支线",
        "",
        *bullet_links(
            [
                (LITERATURE_DECONV_ROUTE_PATH, "反卷积主线阅读路线"),
                (LITERATURE_SYSTEM_ROUTE_PATH, "系统专用化阅读路线"),
            ]
        ),
        "",
        "## 最短主线：从地基一路走到当前验证",
        "",
        f"- 第 1 步，先从 {wikilink(LITERATURE_BRIDGE_GUIDE_PATH, '桥接论文中文导读')} 里的“方法奠基桥接第一批”起步，把 `1991 Huang / 2003 Choma / 2003 de Boer` 这组最核心地基先读顺。",
        f"- 第 2 步，接 {wikilink('02_Literature/Papers/[2014] Unknown - Variations in optical coherence tomography resolution.md', '2014 PSF phantom / resolution benchmark')}，把“怎么证明分辨率真的提升”这件事先站稳。",
        f"- 第 3 步，读 {wikilink('02_Literature/Papers/[2022] Unknown - Spatially adaptive blind deconvolution methods for.md', '2022 blind deconvolution')}，它最贴近你当前的反卷积主线。",
        f"- 第 4 步，接 {wikilink('02_Literature/Papers/[2025] Unknown - Deconvolution Techniques in Optical Coherence Tomography.md', '2025 deconvolution review')}，把 field map 和常见路线压成全局判断。",
        f"- 第 5 步，读 {wikilink('02_Literature/Papers/[2025] Unknown - Enhanced A-scan spatial resolution in spectral.md', '2025 Wigner-Ville paper')}；如果今天只想读中文材料，就直接接 {wikilink('06_Writing/translated-papers/enhanced-a-scan-spatial-resolution-in-spectral-domain-oct-exploiting-the-wigner-ville-technique.md', 'Wigner-Ville 中文译文')}。",
        f"- 第 6 步，把文献判断接回 {wikilink(EXPERIMENT_READER_ENTRY_PATH, '实验验证起步入口')}，不要停在“论文觉得可行”，而是继续落到验证矩阵和 baseline。",
        "",
        "## 如果你今天偏系统专用化",
        "",
        f"- 先看 {wikilink(LITERATURE_BRIDGE_GUIDE_PATH, '桥接论文中文导读')} 里的“系统专用化桥接第一批”，把 `2008 de Bruin / 2011 Zhong / 2014 Wang / 2020 OCT elastography` 这一组读成工程化支线。",
        f"- 再回到 {wikilink(PROGRESS_SYSTEM_PAPER_GUIDE_PATH, '系统专用化论文入口')} 和 {wikilink(SYSTEM_READER_ENTRY_PATH, 'OCT系统与原理起步入口')}，把系统用途、参数约束和实现逻辑放在一起看。",
        f"- 如果这条线要继续往当前工作靠拢，再接 {wikilink(PROJECT_DECISION_READER_ENTRY_PATH, '项目推进与决策入口')}，判断它和现阶段主线有没有必要强耦合。",
        "",
        "## 如果你今天只想读中文材料",
        "",
        f"- 先看 {wikilink(LITERATURE_CHINESE_INDEX_PATH, '中文阅读版文献索引')}。",
        f"- 再看 {wikilink(LITERATURE_BRIDGE_GUIDE_PATH, '桥接论文中文导读')}，先把 bridge 批次里每组的阅读角色弄清。",
        f"- 想直接读已经有中文稿的内容，就去 {wikilink('06_Writing/translated-papers/_Index.md', '译文索引')}；目前最直接的是 {wikilink('06_Writing/translated-papers/enhanced-a-scan-spatial-resolution-in-spectral-domain-oct-exploiting-the-wigner-ville-technique.md', 'Wigner-Ville 中文译文')}。",
        "",
        "## 回到稳定入口",
        "",
        *bullet_links(
            [
                (LITERATURE_READER_ENTRY_PATH, "文献阅读起步入口"),
                (LITERATURE_DECONV_ROUTE_PATH, "反卷积主线阅读路线"),
                (LITERATURE_SYSTEM_ROUTE_PATH, "系统专用化阅读路线"),
                (LITERATURE_BRIDGE_GUIDE_PATH, "桥接论文中文导读"),
                (LITERATURE_BRIDGE_SHELF_PATH, "桥接论文书架"),
                (PROGRESS_KEY_PAPER_GUIDE_PATH, "关键论文档案入口"),
                (EXPERIMENT_READER_ENTRY_PATH, "实验验证起步入口"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_literature_deconv_route() -> str:
    lines = [
        "# 反卷积主线阅读路线",
        "",
        "这条路线把你当前最贴近的方法主线压成一条更窄的顺读路径。它默认你不是来补 OCT 全史，而是要尽快回答“反卷积到底值不值得做、该怎么证明它真的有增益”。",
        "",
        "## 推荐顺序",
        "",
        f"- 第 1 步，先补 {wikilink('02_Literature/Papers/[2014] Unknown - Variations in optical coherence tomography resolution.md', '2014 PSF phantom / resolution benchmark')}，先把分辨率评价地基站稳。",
        f"- 第 2 步，读 {wikilink('02_Literature/Papers/[2022] Unknown - Spatially adaptive blind deconvolution methods for.md', '2022 blind deconvolution')}，它最直接告诉你 blind 路线的价值、假设和边界。",
        f"- 第 3 步，读 {wikilink('02_Literature/Papers/[2025] Unknown - Deconvolution Techniques in Optical Coherence Tomography.md', '2025 deconvolution review')}，把主问题、常见路线和已知卡点压成全局判断。",
        f"- 第 4 步，读 {wikilink('02_Literature/Papers/[2022] Unknown - Superresolving artifact-free optical coherence tomography with.md', '2022 RPM superresolving paper')}，把另一条增强路线也纳入比较，不要只盯 blind deconvolution。",
        f"- 第 5 步，接 {wikilink('02_Literature/Papers/[2025] Unknown - Enhanced A-scan spatial resolution in spectral.md', '2025 Wigner-Ville paper')}；如果今天只想走中文材料，就直接看 {wikilink('06_Writing/translated-papers/enhanced-a-scan-spatial-resolution-in-spectral-domain-oct-exploiting-the-wigner-ville-technique.md', 'Wigner-Ville 中文译文')}。",
        f"- 第 6 步，把判断接回 {wikilink(EXPERIMENT_READER_ENTRY_PATH, '实验验证起步入口')} 和 {wikilink(PROGRESS_DECONV_EVIDENCE_PATH, '反卷积真实增益证据链')}，把“文献可行”推进到“证据能站住”。",
        "",
        "## 如果你还没补完地基",
        "",
        f"- 先回 {wikilink(LITERATURE_BRIDGE_GUIDE_PATH, '桥接论文中文导读')} 里的“方法奠基桥接第一批”和“方法奠基桥接第二批”。",
        f"- 想把总顺序重新看一遍，就回 {wikilink(LITERATURE_ROUTE_MAP_PATH, '桥接论文阅读路线图')}。",
        "",
        "## 回到稳定入口",
        "",
        *bullet_links(
            [
                (LITERATURE_READER_ENTRY_PATH, "文献阅读起步入口"),
                (LITERATURE_ROUTE_MAP_PATH, "桥接论文阅读路线图"),
                (PROGRESS_DECONV_PAPER_GUIDE_PATH, "反卷积主线论文入口"),
                (EXPERIMENT_READER_ENTRY_PATH, "实验验证起步入口"),
                (PROGRESS_DECONV_EVIDENCE_PATH, "反卷积真实增益证据链"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_literature_system_route() -> str:
    lines = [
        "# 系统专用化阅读路线",
        "",
        "这条路线适合你今天更关心系统工程、专用化场景和实现约束，而不是直接盯着反卷积算法本身。目标是先把“系统为什么这样做、代价和收益在哪里”读顺，再决定是否并回当前主线。",
        "",
        "## 推荐顺序",
        "",
        f"- 第 1 步，先回 {wikilink(LITERATURE_BRIDGE_GUIDE_PATH, '桥接论文中文导读')} 里的“系统专用化桥接第一批”，把 `2008 de Bruin / 2011 Zhong / 2014 Wang / 2020 OCT elastography` 这一组先读顺。",
        f"- 第 2 步，接 {wikilink(PROGRESS_SYSTEM_PAPER_GUIDE_PATH, '系统专用化论文入口')}，把当前 workspace 里这条线的稳定入口和回找方式先抓住。",
        f"- 第 3 步，回到 {wikilink(SYSTEM_READER_ENTRY_PATH, 'OCT系统与原理起步入口')}，把系统参数、成像逻辑和物理约束重新放稳，不要只从应用侧看。",
        f"- 第 4 步，如果这条系统线最后还是要服务当前工作，就接 {wikilink(PROJECT_DECISION_READER_ENTRY_PATH, '项目推进与决策入口')}，判断它和现阶段研究主线到底该怎么耦合。",
        f"- 第 5 步，需要落到实验层时，再去 {wikilink(EXPERIMENT_READER_ENTRY_PATH, '实验验证起步入口')}，确认要补的是哪类 baseline、哪类测量和哪类系统校准。",
        "",
        "## 如果你想回到总路线",
        "",
        f"- 回 {wikilink(LITERATURE_ROUTE_MAP_PATH, '桥接论文阅读路线图')} 看它和反卷积主线怎么汇合。",
        f"- 如果发现自己其实在追的是方法收益，不是系统用途，就切到 {wikilink(LITERATURE_DECONV_ROUTE_PATH, '反卷积主线阅读路线')}。",
        "",
        "## 回到稳定入口",
        "",
        *bullet_links(
            [
                (LITERATURE_READER_ENTRY_PATH, "文献阅读起步入口"),
                (LITERATURE_ROUTE_MAP_PATH, "桥接论文阅读路线图"),
                (PROGRESS_SYSTEM_PAPER_GUIDE_PATH, "系统专用化论文入口"),
                (SYSTEM_READER_ENTRY_PATH, "OCT系统与原理起步入口"),
                (PROJECT_DECISION_READER_ENTRY_PATH, "项目推进与决策入口"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_literature_bridge_guide() -> str:
    lines = [
        "# 桥接论文中文导读",
        "",
        "这页不是简单列 bundle，而是把三批 bridge 放回“先读哪篇、为什么先读”的顺序里。目标是让你先抓住每一批最该先补的地基，再决定要不要继续深挖原文或补翻译。",
        "",
        "## 先看总路线",
        "",
        f"- 如果你不想自己拼顺序，先看 {wikilink(LITERATURE_ROUTE_MAP_PATH, '桥接论文阅读路线图')}。",
        "",
        "## 今天先怎么选",
        "",
        f"- 如果你今天要补 OCT 方法地基，先从 {external_link(WORKSPACE_PAPER_BRIDGE_BATCHES[0]['run_path'], '方法奠基桥接第一批')} 开始。",
        f"- 如果你已经知道 OCT 基本轮廓，想把 FD / SS / OFDI 的早期演进读成一条线，就接 {external_link(WORKSPACE_PAPER_BRIDGE_BATCHES[1]['run_path'], '方法奠基桥接第二批')}。",
        f"- 如果你今天更关心工程实现、实时监测或系统专用化，再看 {external_link(WORKSPACE_PAPER_BRIDGE_BATCHES[2]['run_path'], '系统专用化桥接第一批')}。",
        "",
        "## 方法奠基桥接第一批：先把 OCT 原点抓稳",
        "",
        "- 先读 `1991 Huang`：它定义了 OCT 这件事本身，是整个阅读树的原点。",
        "- 再读 `2003 Choma`：它帮你抓住 swept source / Fourier-domain 的 sensitivity advantage，到后面很多系统路线都会回到这里。",
        "- 再读 `2003 de Boer`：它把 spectral-domain 相比 time-domain 的信噪比优势讲得更直接，是理解频域路线很稳的一块地基。",
        "- 这一批剩下的 `2004 Cense / 2004 Nassif / 2005 Wojtkowski / 2010 邹恒 / 2024 Ge` 适合在前 3 篇读顺以后，再补成“系统成像能力是怎么一步步抬起来的”。",
        f"- 批次入口：{external_link(WORKSPACE_PAPER_BRIDGE_BATCHES[0]['bundle_path'], '方法奠基桥接第一批 bundle')} / {external_link(WORKSPACE_PAPER_BRIDGE_BATCHES[0]['run_path'], '方法奠基桥接第一批 run')}",
        "",
        "## 方法奠基桥接第二批：把频域和扫频路线读成演进链",
        "",
        "- 先读 `1996 Tearney`：把早期轴向分辨率和系统实现的想法补回来。",
        "- 再读 `2003 Leitgeb`：这是频域 / 谱域路线里非常关键的一站，适合放在系统演进链中轴位置。",
        "- 再读 `2004 Wojtkowski Fourier-domain OCT`：把 Fourier-domain OCT 的系统化表达补完整。",
        "- 最后再看 `2012 Choi` 以及这批其余条目，把早期地基一路接到更成熟的 FD / SS / OFDI 框架。",
        f"- 批次入口：{external_link(WORKSPACE_PAPER_BRIDGE_BATCHES[1]['bundle_path'], '方法奠基桥接第二批 bundle')} / {external_link(WORKSPACE_PAPER_BRIDGE_BATCHES[1]['run_path'], '方法奠基桥接第二批 run')}",
        "",
        "## 系统专用化桥接第一批：先看工程问题，再看应用扩展",
        "",
        "- 先读 `2008 de Bruin`：它更接近工程实现和专用系统思路，能帮你从“会成像”转到“怎么把系统做成特定用途”。",
        "- 再读 `2011 Zhong`：继续补系统在实时监测、控制或专用任务里的落地方式。",
        "- 再读 `2014 Wang`：把专用化系统如何服务具体场景再往前推进一层。",
        "- 最后看 `2020 OCT elastography`：它更像一条应用扩展支线，适合在前面工程逻辑读顺以后再补。",
        f"- 批次入口：{external_link(WORKSPACE_PAPER_BRIDGE_BATCHES[2]['bundle_path'], '系统专用化桥接第一批 bundle')} / {external_link(WORKSPACE_PAPER_BRIDGE_BATCHES[2]['run_path'], '系统专用化桥接第一批 run')}",
        "",
        "## 回到稳定入口",
        "",
        *bullet_links(
            [
                (LITERATURE_READER_ENTRY_PATH, "文献阅读起步入口"),
                (LITERATURE_ROUTE_MAP_PATH, "桥接论文阅读路线图"),
                (LITERATURE_DECONV_ROUTE_PATH, "反卷积主线阅读路线"),
                (LITERATURE_SYSTEM_ROUTE_PATH, "系统专用化阅读路线"),
                (LITERATURE_BRIDGE_SHELF_PATH, "桥接论文书架"),
                (LITERATURE_CHINESE_INDEX_PATH, "中文阅读版文献索引"),
                (PROGRESS_KEY_PAPER_GUIDE_PATH, "关键论文档案入口"),
                (RETRIEVAL_READER_ENTRY_PATH, "检索与文献管理总览"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_literature_chinese_index() -> str:
    lines = [
        "# 中文阅读版文献索引",
        "",
        "这页优先收录适合中文阅读或中文导读进入的文献入口。它不是逐篇完整翻译库，而是让你先快速读懂论文角色，再决定要不要继续补原文、补翻译或补 bridge。",
        "",
        "## 今天先点哪里",
        "",
        *bullet_links(
            [
                (LITERATURE_READER_ENTRY_PATH, "文献阅读起步入口"),
                (LITERATURE_ROUTE_MAP_PATH, "桥接论文阅读路线图"),
                (LITERATURE_DECONV_ROUTE_PATH, "反卷积主线阅读路线"),
                (LITERATURE_SYSTEM_ROUTE_PATH, "系统专用化阅读路线"),
                (LITERATURE_BRIDGE_GUIDE_PATH, "桥接论文中文导读"),
                ("06_Writing/translated-papers/_Index.md", "译文索引"),
                ("02_Literature/Papers/_Index.md", "文献论文索引"),
            ]
        ),
        "",
        "## 已有中文导读 / 中文整理入口",
        "",
        *bullet_links(
            [
                (LITERATURE_ROUTE_MAP_PATH, "桥接论文阅读路线图"),
                (LITERATURE_DECONV_ROUTE_PATH, "反卷积主线阅读路线"),
                (LITERATURE_SYSTEM_ROUTE_PATH, "系统专用化阅读路线"),
                ("06_Writing/translated-papers/_Index.md", "译文索引"),
                ("06_Writing/translation-workbench/_Index.md", "翻译工作台索引"),
                (LITERATURE_BRIDGE_GUIDE_PATH, "桥接论文中文导读"),
                (LITERATURE_BRIDGE_SHELF_PATH, "桥接论文书架"),
            ]
        ),
        "",
        "## 按研究主线回找",
        "",
        *bullet_links(
                [
                    (PROGRESS_KEY_PAPER_GUIDE_PATH, "关键论文档案入口"),
                    (PROGRESS_FOUNDATION_PAPER_GUIDE_PATH, "方法奠基论文入口"),
                    (PROGRESS_SYSTEM_PAPER_GUIDE_PATH, "系统专用化论文入口"),
                    (PROGRESS_DECONV_PAPER_GUIDE_PATH, "反卷积主线论文入口"),
                ]
            ),
        "",
        "## 如果你还缺论文或想继续补入库",
        "",
        *bullet_links(
            [
                (RETRIEVAL_READER_ENTRY_PATH, "检索与文献管理总览"),
                (PROJECT_DECISION_READER_ENTRY_PATH, "项目推进与决策入口"),
                (LITERATURE_BRIDGE_SHELF_PATH, "桥接论文书架"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_experiment_reader_entry() -> str:
    lines = [
        "# 实验验证起步入口",
        "",
        "如果你今天准备接实验，不要先盯着单张结果图。先把验证问题、baseline、体模/PSF 采集和判据放进同一条闭环里，后面的结果才站得住。",
        "",
        "## 如果你只有 30 分钟",
        "",
        *bullet_links(
            [
                ("13_阅读区/03_实验与评估/实验与评价总览.md", "实验与评价总览"),
                ("13_阅读区/03_实验与评估/正式验证计划：体模上 Measured-PSF 对 Gaussian Baseline.md", "正式验证计划：体模上 Measured-PSF 对 Gaussian Baseline"),
                (PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, "关键实验实例入口"),
            ]
        ),
        "",
        "## 今天先抓哪条实验线",
        "",
        "- 先看 `lateral-resolution-validation-matrix`：它把当前最值得先做的验证问题压成一张实验矩阵。",
        "- 再看 `phantom-bead-baseline-instance` 和 `psf-measurement-instance-bead-scan`：它们决定你到底有没有可靠输入，不只是有没有算法输出。",
        "- 再看 `no-ground-truth-metric-checklist`：它提醒你在没有真值时，什么能算证据，什么只是更好看的图。",
        "",
        "## 按你今天的任务进",
        "",
        f"- 想快速知道实验闭环缺哪一环：{wikilink('13_阅读区/03_实验与评估/实验与评价总览.md', '实验与评价总览')}",
        f"- 想直接看当前最正式的一版验证计划：{wikilink('13_阅读区/03_实验与评估/正式验证计划：体模上 Measured-PSF 对 Gaussian Baseline.md', '正式验证计划：体模上 Measured-PSF 对 Gaussian Baseline')}",
        f"- 想看关键实验样例、成功样例和失败样例：{wikilink(PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, '关键实验实例入口')} / {wikilink(PROGRESS_SUCCESS_EXPERIMENT_GUIDE_PATH, '验证成功样例入口')} / {wikilink(PROGRESS_FAILURE_EXPERIMENT_GUIDE_PATH, '失败与排障样例入口')}",
        f"- 想把实验判断接回论文和证据链：{wikilink(LITERATURE_READER_ENTRY_PATH, '文献阅读起步入口')} / {wikilink(PROGRESS_EVIDENCE_READER_ENTRY_PATH, '研究问题证据入口')}",
        f"- 想把验证逻辑压成更易读的图页和路线图：{wikilink(FIGURE_READER_ENTRY_PATH, '图示表达起步入口')}",
        f"- 想继续压成可写论断和稿件语言：{wikilink(WRITING_READER_ENTRY_PATH, '写作表达起步入口')}",
        f"- 想把实验结果接成下一阶段优先级和风险判断：{wikilink(PROJECT_DECISION_READER_ENTRY_PATH, '项目推进与决策入口')}",
        "",
        "## 对应底层实验入口",
        "",
        *bullet_links(
            [
                ("05_Experiments/lateral-resolution-validation-matrix.md", "lateral-resolution-validation-matrix"),
                ("05_Experiments/01_Phantom/phantom-bead-baseline-instance.md", "phantom-bead-baseline-instance"),
                ("05_Experiments/03_PSF-Measurement/psf-measurement-instance-bead-scan.md", "psf-measurement-instance-bead-scan"),
                ("05_Experiments/05_No-Ground-Truth-Evaluation/no-ground-truth-metric-checklist.md", "no-ground-truth-metric-checklist"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_experiment_reader_index(notes: dict[str, Note]) -> str:
    direct = direct_notes(notes, "13_阅读区/03_实验与评估")
    lines = [
        "# 实验与评估索引",
        "",
        "这页只保留实验区最值得先点开的入口。先把实验问题、验证计划和样例入口接起来，再去看更深的实验记录。",
        "",
        "## 起步入口",
        "",
        *bullet_links(
            [
                (EXPERIMENT_READER_ENTRY_PATH, "实验验证起步入口"),
                ("13_阅读区/03_实验与评估/实验与评价总览.md", "实验与评价总览"),
                ("13_阅读区/03_实验与评估/正式验证计划：体模上 Measured-PSF 对 Gaussian Baseline.md", "正式验证计划：体模上 Measured-PSF 对 Gaussian Baseline"),
            ]
        ),
        "",
        "## 继续往下",
        "",
        *bullet_links(
            [
                (PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, "关键实验实例入口"),
                (PROGRESS_SUCCESS_EXPERIMENT_GUIDE_PATH, "验证成功样例入口"),
                (PROGRESS_FAILURE_EXPERIMENT_GUIDE_PATH, "失败与排障样例入口"),
                ("05_Experiments/00_Verification-Plans/_Index.md", "验证计划索引"),
            ]
        ),
        "",
    ]
    if direct:
        lines.extend(note_section("本层阅读页", direct))
    return "\n".join(lines).rstrip() + "\n"


def build_figure_reader_entry() -> str:
    lines = [
        "# 图示表达起步入口",
        "",
        "如果你今天准备看图、审图或开始画自己的图，不要先盯着美观。先把图到底要承载什么判断、展示什么证据、避免什么误导想清，图才会真正服务研究主线。",
        "",
        "## 如果你只有 30 分钟",
        "",
        *bullet_links(
            [
                ("13_阅读区/04_图示与路线图/图示阅读与路线图总览.md", "图示阅读与路线图总览"),
                ("13_阅读区/04_图示与路线图/最小可视化验证页草案：体模上 Measured-PSF 对 Gaussian Baseline.md", "最小可视化验证页草案：体模上 Measured-PSF 对 Gaussian Baseline"),
                ("06_Writing/03_Figures-and-Captions/_Index.md", "图示与图注索引"),
            ]
        ),
        "",
        "## 今天先抓哪种图",
        "",
        "- 先看系统图：弄清一张系统图应该怎样从物理结构连到性能判断，而不是只会认元件名。",
        "- 再看信号图和结果图：确认自己知道每张图应该追问什么，尤其是效果图背后的 artifact 风险和 claim 边界。",
        "- 如果今天要画自己的图，就直接看路线图底稿和最小可视化验证页草案，先学会压逻辑，再谈美化。",
        "",
        "## 按你今天的任务进",
        "",
        f"- 想学会怎么看别人论文里的系统图、信号图、结果图：{wikilink('13_阅读区/04_图示与路线图/图示阅读与路线图总览.md', '图示阅读与路线图总览')}",
        f"- 想把验证逻辑压成一张更容易读懂的页面：{wikilink('13_阅读区/04_图示与路线图/最小可视化验证页草案：体模上 Measured-PSF 对 Gaussian Baseline.md', '最小可视化验证页草案：体模上 Measured-PSF 对 Gaussian Baseline')}",
        f"- 想把图示表达接回实验和论文：{wikilink(EXPERIMENT_READER_ENTRY_PATH, '实验验证起步入口')} / {wikilink(LITERATURE_READER_ENTRY_PATH, '文献阅读起步入口')}",
        f"- 想把图和论断真正接到写作：{wikilink(WRITING_READER_ENTRY_PATH, '写作表达起步入口')}",
        f"- 想先把系统图和物理原理补稳，再回来审图：{wikilink(SYSTEM_READER_ENTRY_PATH, 'OCT系统与原理起步入口')}",
        f"- 想把图页表达接回项目节奏和下一步取舍：{wikilink(PROJECT_DECISION_READER_ENTRY_PATH, '项目推进与决策入口')}",
        f"- 想直接下钻到写作区的图示资产：{wikilink('06_Writing/03_Figures-and-Captions/_Index.md', '图示与图注索引')} / {wikilink('06_Writing/03_Figures-and-Captions/current-oct-deconvolution-technical-roadmap-draft.md', 'current-oct-deconvolution-technical-roadmap-draft')}",
        "",
        "## 对应底层图示入口",
        "",
        *bullet_links(
            [
                ("03_Concepts/10_Figure-and-Image-Analysis/reading-oct-system-schematics-from-physics-to-performance.md", "reading-oct-system-schematics-from-physics-to-performance"),
                ("03_Concepts/10_Figure-and-Image-Analysis/reading-frequency-domain-oct-signal-and-processing-figures.md", "reading-frequency-domain-oct-signal-and-processing-figures"),
                ("03_Concepts/10_Figure-and-Image-Analysis/auditing-oct-result-figures-and-effect-claims.md", "auditing-oct-result-figures-and-effect-claims"),
                ("06_Writing/03_Figures-and-Captions/seed-paper-system-and-figure-comparison-board.md", "seed-paper-system-and-figure-comparison-board"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_figure_reader_index(notes: dict[str, Note]) -> str:
    direct = direct_notes(notes, "13_阅读区/04_图示与路线图")
    lines = [
        "# 图示与路线图索引",
        "",
        "这页只保留图示区最值得先点开的入口。先把图要表达什么、怎么审图、怎么接回实验和写作想清，再去做更细的图资产整理。",
        "",
        "## 起步入口",
        "",
        *bullet_links(
            [
                (FIGURE_READER_ENTRY_PATH, "图示表达起步入口"),
                ("13_阅读区/04_图示与路线图/图示阅读与路线图总览.md", "图示阅读与路线图总览"),
                ("13_阅读区/04_图示与路线图/最小可视化验证页草案：体模上 Measured-PSF 对 Gaussian Baseline.md", "最小可视化验证页草案：体模上 Measured-PSF 对 Gaussian Baseline"),
            ]
        ),
        "",
        "## 继续往下",
        "",
        *bullet_links(
            [
                ("06_Writing/03_Figures-and-Captions/_Index.md", "图示与图注索引"),
                (EXPERIMENT_READER_ENTRY_PATH, "实验验证起步入口"),
                (LITERATURE_READER_ENTRY_PATH, "文献阅读起步入口"),
            ]
        ),
        "",
    ]
    if direct:
        lines.extend(note_section("本层阅读页", direct))
    return "\n".join(lines).rstrip() + "\n"


def build_writing_reader_entry() -> str:
    lines = [
        "# 写作表达起步入口",
        "",
        "如果你今天准备真正开始写，不要先追求句子漂亮。先把哪些主张已经够稳、哪些图能支撑这些主张、哪些争议必须主动交代想清，写作才会顺下来。",
        "",
        "## 如果你只有 30 分钟",
        "",
        *bullet_links(
            [
                ("13_阅读区/05_写作与论文表达/写作阅读区.md", "写作阅读区"),
                ("06_Writing/05_Claim-to-Evidence/current-claim-boundaries.md", "current-claim-boundaries"),
                ("04_Progress/05_Claim-Tracker/claim-tracker.md", "claim-tracker"),
            ]
        ),
        "",
        "## 今天先抓哪条写作线",
        "",
        "- 先看 `current-claim-boundaries`：判断哪些话现在能写，哪些话还不能写满。",
        "- 再看 `claim-tracker` 和 `controversy-and-debate-map`：把当前能写的主张和最危险的争议点同时放到眼前。",
        "- 如果今天要落到图和结构，就接着看技术路线图底稿和种子论文图示比较板。",
        "",
        "## 按你今天的任务进",
        "",
        f"- 想快速知道现在最适合写哪一块：{wikilink('13_阅读区/05_写作与论文表达/写作阅读区.md', '写作阅读区')}",
        f"- 想先压主张和证据边界：{wikilink('06_Writing/05_Claim-to-Evidence/current-claim-boundaries.md', 'current-claim-boundaries')} / {wikilink('04_Progress/05_Claim-Tracker/claim-tracker.md', 'claim-tracker')}",
        f"- 想把图示表达继续转成稿件表达：{wikilink(FIGURE_READER_ENTRY_PATH, '图示表达起步入口')}",
        f"- 想直接进入写作区底层资产：{wikilink('06_Writing/_Index.md', '写作区索引')} / {wikilink('06_Writing/03_Figures-and-Captions/_Index.md', '图示与图注索引')}",
        f"- 想回看论文和实验，确认这些话站不站得住：{wikilink(LITERATURE_READER_ENTRY_PATH, '文献阅读起步入口')} / {wikilink(EXPERIMENT_READER_ENTRY_PATH, '实验验证起步入口')}",
        f"- 想把当前可写内容接回优先级、风险和下一步：{wikilink(PROJECT_DECISION_READER_ENTRY_PATH, '项目推进与决策入口')}",
        f"- 想把一些老是反复出现的术语和创新点也一起理顺：{wikilink(TERM_READER_ENTRY_PATH, '术语与问题起步入口')}",
        "",
        "## 对应底层写作入口",
        "",
        *bullet_links(
            [
                ("06_Writing/05_Claim-to-Evidence/current-claim-boundaries.md", "current-claim-boundaries"),
                ("04_Progress/05_Claim-Tracker/claim-tracker.md", "claim-tracker"),
                ("04_Progress/03_Risk-Register/controversy-and-debate-map.md", "controversy-and-debate-map"),
                ("06_Writing/03_Figures-and-Captions/current-oct-deconvolution-technical-roadmap-draft.md", "current-oct-deconvolution-technical-roadmap-draft"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_writing_reader_index(notes: dict[str, Note]) -> str:
    direct = direct_notes(notes, "13_阅读区/05_写作与论文表达")
    lines = [
        "# 写作与论文表达索引",
        "",
        "这页只保留写作区最值得先点开的入口。先把可写主张、证据边界和图文表达接起来，再深入具体写作资产。",
        "",
        "## 起步入口",
        "",
        *bullet_links(
            [
                (WRITING_READER_ENTRY_PATH, "写作表达起步入口"),
                ("13_阅读区/05_写作与论文表达/写作阅读区.md", "写作阅读区"),
            ]
        ),
        "",
        "## 继续往下",
        "",
        *bullet_links(
            [
                ("06_Writing/_Index.md", "写作区索引"),
                ("06_Writing/03_Figures-and-Captions/_Index.md", "图示与图注索引"),
                (FIGURE_READER_ENTRY_PATH, "图示表达起步入口"),
                (EXPERIMENT_READER_ENTRY_PATH, "实验验证起步入口"),
            ]
        ),
        "",
    ]
    if direct:
        lines.extend(note_section("本层阅读页", direct))
    return "\n".join(lines).rstrip() + "\n"


def build_term_reader_entry() -> str:
    lines = [
        "# 术语与问题起步入口",
        "",
        "如果你今天不是要补一篇具体论文，而是想把反复出现的术语、创新点和长期问题放到一起看，这页更适合你。它的作用不是堆术语表，而是帮你维持稳定的问题意识。",
        "",
        "## 如果你只有 30 分钟",
        "",
        *bullet_links(
            [
                ("13_阅读区/06_术语与问题/关键术语与长期问题.md", "关键术语与长期问题"),
                ("13_阅读区/06_术语与问题/创新点与关键问题总览.md", "创新点与关键问题总览"),
                ("03_Concepts/09_Theory-Governance/theory-landscape-and-priority-map.md", "theory-landscape-and-priority-map"),
            ]
        ),
        "",
        "## 今天先抓哪类问题",
        "",
        "- 想知道一个术语到底在项目里占什么位置：先看关键术语与长期问题，不要孤立理解名词。",
        "- 想判断一个想法算不算创新点：先看创新点与关键问题总览，再回到创新筛选规则。",
        "- 想知道哪些疑点值得长期追踪：把长期问题、风险登记和争议地图放在一起看。",
        "",
        "## 按你今天的任务进",
        "",
        f"- 想先把最常复现的术语和长期问题抓稳：{wikilink('13_阅读区/06_术语与问题/关键术语与长期问题.md', '关键术语与长期问题')}",
        f"- 想看当前已显化出来的创新方向和关键问题：{wikilink('13_阅读区/06_术语与问题/创新点与关键问题总览.md', '创新点与关键问题总览')}",
        f"- 想把术语放回整个理论地图里：{wikilink('03_Concepts/09_Theory-Governance/theory-landscape-and-priority-map.md', 'theory-landscape-and-priority-map')}",
        f"- 想把这些概念接回系统原理和论文：{wikilink(SYSTEM_READER_ENTRY_PATH, 'OCT系统与原理起步入口')} / {wikilink(LITERATURE_READER_ENTRY_PATH, '文献阅读起步入口')}",
        f"- 想把创新点和疑点接回可写主张与风险边界：{wikilink(WRITING_READER_ENTRY_PATH, '写作表达起步入口')} / {wikilink(PROJECT_DECISION_READER_ENTRY_PATH, '项目推进与决策入口')}",
        "",
        "## 对应底层问题入口",
        "",
        *bullet_links(
            [
                ("03_Concepts/09_Theory-Governance/theory-landscape-and-priority-map.md", "theory-landscape-and-priority-map"),
                ("03_Concepts/09_Theory-Governance/theory-selection-and-ban-rules.md", "theory-selection-and-ban-rules"),
                ("03_Concepts/08_Innovation-Notes/innovation-hypothesis-board.md", "innovation-hypothesis-board"),
                ("03_Concepts/08_Innovation-Notes/innovation-screening-rubric.md", "innovation-screening-rubric"),
                ("04_Progress/03_Risk-Register/long-horizon-key-questions-for-oct-figure-analysis.md", "long-horizon-key-questions-for-oct-figure-analysis"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_term_reader_index(notes: dict[str, Note]) -> str:
    direct = [
        note
        for note in direct_notes(notes, "13_阅读区/06_术语与问题")
        if note.rel_path != TERM_READER_ENTRY_PATH and not note.stem.startswith("_Index-")
    ]
    lines = [
        "# 术语与问题索引",
        "",
        "这页只保留术语与问题区最值得先点开的入口。先把术语、创新点和长期问题放到同一层上，再回到论文、写作和推进判断。",
        "",
        "## 起步入口",
        "",
        *bullet_links(
            [
                (TERM_READER_ENTRY_PATH, "术语与问题起步入口"),
                ("13_阅读区/06_术语与问题/关键术语与长期问题.md", "关键术语与长期问题"),
                ("13_阅读区/06_术语与问题/创新点与关键问题总览.md", "创新点与关键问题总览"),
            ]
        ),
        "",
        "## 继续往下",
        "",
        *bullet_links(
            [
                (SYSTEM_READER_ENTRY_PATH, "OCT系统与原理起步入口"),
                (LITERATURE_READER_ENTRY_PATH, "文献阅读起步入口"),
                (WRITING_READER_ENTRY_PATH, "写作表达起步入口"),
                (PROJECT_DECISION_READER_ENTRY_PATH, "项目推进与决策入口"),
            ]
        ),
        "",
    ]
    if direct:
        lines.extend(note_section("本层阅读页", direct))
    return "\n".join(lines).rstrip() + "\n"


def build_action_reader_entry() -> str:
    lines = [
        "# 行动起步入口",
        "",
        "如果你今天不是想继续理解，而是想直接知道“还没做完什么、现在最值得接着做哪一步”，这页最适合你。它不替代底层任务系统，而是把中文阅读版任务板和主线判断接到一起。",
        "",
        "## 如果你只有 30 分钟",
        "",
        *bullet_links(
            [
                ("13_阅读区/07_未完成任务与下一步/未完成任务看板.md", "未完成任务看板"),
                (PROJECT_DECISION_READER_ENTRY_PATH, "项目推进与决策入口"),
                ("10_Tasks/_Index.md", "任务索引"),
            ]
        ),
        "",
        "## 今天先抓哪类动作",
        "",
        "- 想先补核心文献和评价地基：先看未完成任务看板，再回到文献阅读起步入口。",
        "- 想先把 baseline、体模和实例推进到可执行：直接接实验验证起步入口。",
        "- 想把图、路线图和写作表达往前推：把图示表达起步入口和写作表达起步入口连着看。",
        "",
        "## 按你今天的任务进",
        "",
        f"- 想先看中文阅读版的未完成任务板：{wikilink('13_阅读区/07_未完成任务与下一步/未完成任务看板.md', '未完成任务看板')}",
        f"- 想把待办先压回到底层任务系统：{wikilink('10_Tasks/_Index.md', '任务索引')} / {wikilink('10_Tasks/system-expansion-backlog.md', 'system-expansion-backlog')}",
        f"- 想先判断哪件事现在最值得推进：{wikilink(PROJECT_DECISION_READER_ENTRY_PATH, '项目推进与决策入口')}",
        f"- 想先把怎么做更稳、哪些规范别漏掉理顺：{wikilink(EXECUTION_READER_ENTRY_PATH, '执行规范起步入口')}",
        f"- 想继续补核心文献和中文阅读版：{wikilink(LITERATURE_READER_ENTRY_PATH, '文献阅读起步入口')}",
        f"- 想推进 baseline、体模和真实数据实例：{wikilink(EXPERIMENT_READER_ENTRY_PATH, '实验验证起步入口')}",
        f"- 想把当前逻辑压成图和稿件表达：{wikilink(FIGURE_READER_ENTRY_PATH, '图示表达起步入口')} / {wikilink(WRITING_READER_ENTRY_PATH, '写作表达起步入口')}",
        "",
        "## 对应底层行动入口",
        "",
        *bullet_links(
            [
                ("10_Tasks/_Index.md", "任务索引"),
                ("10_Tasks/system-expansion-backlog.md", "system-expansion-backlog"),
                (PROGRESS_READER_ENTRY_PATH, "研究主线入口"),
                (PROJECT_DECISION_READER_ENTRY_PATH, "项目推进与决策入口"),
                (EXECUTION_READER_ENTRY_PATH, "执行规范起步入口"),
                (PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, "关键实验实例入口"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_action_reader_index(notes: dict[str, Note]) -> str:
    direct = [note for note in direct_notes(notes, "13_阅读区/07_未完成任务与下一步") if note.rel_path != ACTION_READER_ENTRY_PATH]
    lines = [
        "# 未完成任务与下一步索引",
        "",
        "这页只保留行动层最值得先点开的入口。先把阅读版任务板、底层任务系统和推进判断接起来，再决定今天具体动哪一步。",
        "",
        "## 起步入口",
        "",
        *bullet_links(
            [
                (ACTION_READER_ENTRY_PATH, "行动起步入口"),
                ("13_阅读区/07_未完成任务与下一步/未完成任务看板.md", "未完成任务看板"),
            ]
        ),
        "",
        "## 继续往下",
        "",
        *bullet_links(
            [
                (PROJECT_DECISION_READER_ENTRY_PATH, "项目推进与决策入口"),
                ("10_Tasks/_Index.md", "任务索引"),
                ("10_Tasks/system-expansion-backlog.md", "system-expansion-backlog"),
                (LITERATURE_READER_ENTRY_PATH, "文献阅读起步入口"),
                (EXPERIMENT_READER_ENTRY_PATH, "实验验证起步入口"),
            ]
        ),
        "",
    ]
    if direct:
        lines.extend(note_section("本层阅读页", direct))
    return "\n".join(lines).rstrip() + "\n"


def build_execution_reader_entry() -> str:
    lines = [
        "# 执行规范起步入口",
        "",
        "如果你今天不是在补知识内容，而是想把“平时怎么做才不乱、怎么沉淀 AI 协作、怎么把办事和科研规范放稳”理顺，这页更适合你。它的重点不是增加流程负担，而是减少返工和靠临时回忆。",
        "",
        "## 如果你只有 30 分钟",
        "",
        *bullet_links(
            [
                ("13_阅读区/08_日常规范与办事/日常规范与办事总览.md", "日常规范与办事总览"),
                ("13_阅读区/08_日常规范与办事/AI协作学习入口.md", "AI协作学习入口"),
                ("14_日常规范与办事/04_AI协作与调试/00_总览/AI协作与调试总览.md", "AI协作与调试总览"),
            ]
        ),
        "",
        "## 今天先抓哪类规范",
        "",
        "- 想把报销、采购、论文规范和实验记录这类日常执行放稳：先看日常规范与办事总览。",
        "- 想知道 AI 协作内容什么时候值得升级进长期层：先看 AI协作学习入口，再看候选升级说明。",
        "- 想在每轮工作结束时少漏东西：回到 AI 协作协议和候选卡模板，不要只靠会话记忆。",
        "",
        "## 按你今天的任务进",
        "",
        f"- 想先看这一层的中文阅读总览：{wikilink('13_阅读区/08_日常规范与办事/日常规范与办事总览.md', '日常规范与办事总览')}",
        f"- 想系统理解 AI 协作沉淀为什么存在、怎么分层：{wikilink('13_阅读区/08_日常规范与办事/AI协作学习入口.md', 'AI协作学习入口')}",
        f"- 想直接理解候选升级池和正式升级怎么接：{wikilink('13_阅读区/08_日常规范与办事/AI协作候选升级说明.md', 'AI协作候选升级说明')}",
        f"- 想把执行规范接回今天的行动和下一步：{wikilink(ACTION_READER_ENTRY_PATH, '行动起步入口')} / {wikilink(PROJECT_DECISION_READER_ENTRY_PATH, '项目推进与决策入口')}",
        f"- 想回到底层规范体系：{wikilink('14_日常规范与办事/00_总览/日常规范总览.md', '日常规范总览')} / {wikilink('14_日常规范与办事/04_AI协作与调试/_Index.md', 'AI协作与调试索引')}",
        "",
        "## 对应底层规范入口",
        "",
        *bullet_links(
            [
                ("14_日常规范与办事/00_总览/日常规范总览.md", "日常规范总览"),
                ("14_日常规范与办事/02_科研规范/实验记录与数据整理规范.md", "实验记录与数据整理规范"),
                ("14_日常规范与办事/04_AI协作与调试/00_总览/AI协作与调试总览.md", "AI协作与调试总览"),
                ("00_Home/Templates/AI-Reuse-Candidate-Card-Template.md", "AI-Reuse-Candidate-Card-Template"),
                ("13_阅读区/08_日常规范与办事/AI协作候选升级说明.md", "AI协作候选升级说明"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_execution_reader_index(notes: dict[str, Note]) -> str:
    direct = [note for note in direct_notes(notes, "13_阅读区/08_日常规范与办事") if note.rel_path != EXECUTION_READER_ENTRY_PATH]
    lines = [
        "# 日常规范与办事索引",
        "",
        "这页只保留执行规范层最值得先点开的入口。先把日常规范、AI 协作沉淀和规范协议接起来，再决定今天该补哪一块。",
        "",
        "## 起步入口",
        "",
        *bullet_links(
            [
                (EXECUTION_READER_ENTRY_PATH, "执行规范起步入口"),
                ("13_阅读区/08_日常规范与办事/日常规范与办事总览.md", "日常规范与办事总览"),
                ("13_阅读区/08_日常规范与办事/AI协作学习入口.md", "AI协作学习入口"),
                ("13_阅读区/08_日常规范与办事/AI协作候选升级说明.md", "AI协作候选升级说明"),
            ]
        ),
        "",
        "## 继续往下",
        "",
        *bullet_links(
            [
                (ACTION_READER_ENTRY_PATH, "行动起步入口"),
                (PROJECT_DECISION_READER_ENTRY_PATH, "项目推进与决策入口"),
                ("14_日常规范与办事/00_总览/日常规范总览.md", "日常规范总览"),
                ("14_日常规范与办事/04_AI协作与调试/_Index.md", "AI协作与调试索引"),
            ]
        ),
        "",
    ]
    if direct:
        lines.extend(note_section("本层阅读页", direct))
    return "\n".join(lines).rstrip() + "\n"


def build_retrieval_reader_entry() -> str:
    lines = [
        "# 检索与文献管理总览",
        "",
        "如果你今天不是先读已有论文，而是想判断“还缺哪篇、先去哪里找、找回来之后怎么接进 Zotero 和知识库”，先从这页进。它的重点不是再做一轮散搜，而是把持续检索、库状态和入库去向压到同一屏里。",
        "",
        "## 如果你只有 30 分钟",
        "",
        *bullet_links(
            [
                ("11_Retrieval/_Index.md", "检索索引"),
                ("11_Retrieval/oct-code-radar-watchlist.md", "OCT code radar watchlist"),
                ("12_Zotero/integration-status.md", "Zotero integration status"),
                ("12_Zotero/library-health.md", "Zotero library health"),
            ]
        ),
        "",
        "## 今天先抓哪类检索问题",
        "",
        "- 想知道现在还值得补什么仓库、代码和方向：先看 watchlist，再看 repository ledger。",
        "- 想知道 Zotero 现在能不能稳稳接住新文献：先看 integration status 和 library health。",
        "- 想知道补回来的论文会落到哪里、下一步是先翻译还是先实验：回到论文索引、译文索引和文献阅读入口。",
        "",
        "## 按你今天的任务进",
        "",
        f"- 想先看当前持续跟踪的检索线索：{wikilink('11_Retrieval/oct-code-radar-watchlist.md', 'OCT code radar watchlist')} / {wikilink('11_Retrieval/oct-code-radar-repository-ledger.md', 'repository ledger')}",
        f"- 想先看这一轮可复用的检索策略和查询：{wikilink('11_Retrieval/oct-code-radar-query-library.md', 'query library')} / {wikilink('11_Retrieval/2026-04-15-retrieval.md', 'round5 retrieval 摘要')}",
        f"- 想知道 Zotero 当前接得稳不稳：{wikilink('12_Zotero/integration-status.md', 'Zotero integration status')} / {wikilink('12_Zotero/library-health.md', 'Zotero library health')}",
        f"- 想把候选文献接回当前阅读顺序：{wikilink(LITERATURE_READER_ENTRY_PATH, '文献阅读起步入口')} / {wikilink('02_Literature/Papers/_Index.md', '文献论文索引')}",
        f"- 想把已入库论文、译文和阅读笔记集中回找：{wikilink('02_Literature/Papers/_Index.md', '文献论文索引')} / {wikilink('06_Writing/translated-papers/_Index.md', '译文索引')}",
        f"- 想判断下一篇先补翻译还是先补实验验证：{wikilink('06_Writing/translated-papers/_Index.md', '译文索引')} / {wikilink(EXPERIMENT_READER_ENTRY_PATH, '实验验证起步入口')}",
        f"- 想把补文献决策接回当前主线和优先级：{wikilink(PROJECT_DECISION_READER_ENTRY_PATH, '项目推进与决策入口')}",
        "",
        "## 对应底层检索入口",
        "",
        *bullet_links(
            [
                ("11_Retrieval/_Index.md", "检索索引"),
                ("11_Retrieval/Codex Skills Retrieval.md", "Codex Skills Retrieval"),
                ("11_Retrieval/oct-code-radar-watchlist.md", "OCT code radar watchlist"),
                ("11_Retrieval/oct-code-radar-repository-ledger.md", "repository ledger"),
                ("11_Retrieval/oct-code-radar-query-library.md", "query library"),
                ("11_Retrieval/oct-code-radar-failure-pattern-log.md", "failure pattern log"),
                ("12_Zotero/integration-status.md", "Zotero integration status"),
                ("12_Zotero/library-health.md", "Zotero library health"),
                ("06_Writing/translation-workbench/_Index.md", "翻译工作台索引"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_project_decision_reader_entry() -> str:
    lines = [
        "# 项目推进与决策入口",
        "",
        "如果你今天不是单纯想读，而是想判断“现在最该推进什么、哪件事风险最大、下一步该怎么排”，先不要在进展笔记和任务页里来回翻。先把路线、决策、风险和本周动作放到同一屏里，推进会更稳。",
        "",
        "## 如果你只有 30 分钟",
        "",
        *bullet_links(
            [
                (PROGRESS_READER_ENTRY_PATH, "研究主线入口"),
                ("04_Progress/three-month-manuscript-track.md", "three-month-manuscript-track"),
                ("10_Tasks/_Index.md", "任务索引"),
            ]
        ),
        "",
        "## 今天先抓哪条推进线",
        "",
        "- 想知道大方向有没有跑偏：先看研究主线入口，再回到三个月稿件推进线。",
        "- 想知道现在最危险的不是哪件事没做，而是哪种判断还不稳：先看研究问题证据入口和核心结论入口。",
        "- 想知道今天具体先动哪一步：先看任务索引，再对照三个月稿件推进线决定今天的动作。",
        "",
        "## 按你今天的任务进",
        "",
        f"- 想快速回到当前主线和阶段位置：{wikilink(PROGRESS_READER_ENTRY_PATH, '研究主线入口')}",
        f"- 想先围着某个研究问题追证据，再决定要不要推进：{wikilink(PROGRESS_EVIDENCE_READER_ENTRY_PATH, '研究问题证据入口')}",
        f"- 想先看已经形成的判断，避免今天又重复打转：{wikilink(PROGRESS_CORE_CONCLUSION_GUIDE_PATH, '核心结论入口')}",
        f"- 想直接看当前稿件节奏和阶段推进：{wikilink('04_Progress/three-month-manuscript-track.md', 'three-month-manuscript-track')}",
        f"- 想把今天要动的任务压到一页：{wikilink('10_Tasks/_Index.md', '任务索引')} / {wikilink('10_Tasks/system-expansion-backlog.md', 'system-expansion-backlog')}",
        f"- 想直接看中文阅读版的未完成任务和下一步：{wikilink(ACTION_READER_ENTRY_PATH, '行动起步入口')}",
        f"- 想把执行规范、AI协作沉淀和日常流程一起理顺：{wikilink(EXECUTION_READER_ENTRY_PATH, '执行规范起步入口')}",
        f"- 想先判断还缺哪篇文献、从哪补和补回来怎么接：{wikilink(RETRIEVAL_READER_ENTRY_PATH, '检索与文献管理总览')}",
        f"- 想回头补系统原理和关键术语，再决定是否推进：{wikilink(SYSTEM_READER_ENTRY_PATH, 'OCT系统与原理起步入口')} / {wikilink(TERM_READER_ENTRY_PATH, '术语与问题起步入口')}",
        f"- 想把可写论断、图页和推进节奏接起来：{wikilink(WRITING_READER_ENTRY_PATH, '写作表达起步入口')} / {wikilink(FIGURE_READER_ENTRY_PATH, '图示表达起步入口')}",
        f"- 想回看关键讨论和历史判断脉络：{wikilink(CONVERSATION_READER_ENTRY_PATH, '高价值会话入口')}",
        "",
        "## 对应底层推进入口",
        "",
        *bullet_links(
            [
                ("04_Progress/three-month-manuscript-track.md", "three-month-manuscript-track"),
                ("10_Tasks/_Index.md", "任务索引"),
                ("10_Tasks/system-expansion-backlog.md", "system-expansion-backlog"),
                (PROGRESS_THEME_NAV_PATH, "研究推进主线导航"),
                (PROGRESS_EVIDENCE_NAV_PATH, "研究问题证据链导航"),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def build_master_index(notes: dict[str, Note]) -> str:
    top_folders = sorted({note.top_folder for note in notes.values()})
    lines = ["# 目录总索引", "", "## 顶层目录", ""]
    for folder in top_folders:
        count = len(descendants(notes, folder))
        lines.append(f"- {wikilink(f'{folder}/_Index.md', folder)} (`{count}`)")
    lines.append("")
    return "\n".join(lines)


def build_logic_note() -> str:
    return "\n".join(
        [
            "# 分类逻辑说明",
            "",
            "这套导航同时保留目录结构和问题导向入口：",
            "",
            "- 目录层负责稳定归档。",
            "- 阅读层负责按问题、主线和主题快速回找。",
            "- 证据链层负责把研究问题直接接到论文、实验、写作和会话。",
            "- 论文层优先按单篇 dossier 聚合 Zotero、原文、翻译和解析。",
            "",
        ]
    )


def build_health_note(notes: dict[str, Note]) -> str:
    total = len([note for note in notes.values() if not note.is_index])
    folders = len({note.parent_folder for note in notes.values()})
    return "\n".join(["# 知识库体检报告", "", f"- 笔记总数：`{total}`", f"- 涉及目录：`{folders}`", ""])


def build_reader_project_progress_index(notes: dict[str, Note]) -> str:
    lines = [
        "# 项目进展与管理索引",
        "",
        "## 阅读入口",
        "",
        *bullet_links(
            [
                (PROGRESS_READER_ENTRY_PATH, "研究主线入口"),
                (PROGRESS_EVIDENCE_READER_ENTRY_PATH, "研究问题证据入口"),
                (PROJECT_DECISION_READER_ENTRY_PATH, "项目推进与决策入口"),
                (PROGRESS_CORE_CONCLUSION_GUIDE_PATH, "核心结论入口"),
                (PROGRESS_KEY_PAPER_GUIDE_PATH, "关键论文档案入口"),
                (PROGRESS_FOUNDATION_PAPER_GUIDE_PATH, "方法奠基论文入口"),
                (PROGRESS_SYSTEM_PAPER_GUIDE_PATH, "系统专用化论文入口"),
                (PROGRESS_DECONV_PAPER_GUIDE_PATH, "反卷积主线论文入口"),
                (PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, "关键实验实例入口"),
                (PROGRESS_SUCCESS_EXPERIMENT_GUIDE_PATH, "验证成功样例入口"),
                (PROGRESS_FAILURE_EXPERIMENT_GUIDE_PATH, "失败与排障样例入口"),
                (PROGRESS_CALIBRATION_EXPERIMENT_GUIDE_PATH, "系统校准样例入口"),
                (CONVERSATION_READER_ENTRY_PATH, "高价值会话入口"),
                (EXPERIMENT_READER_ENTRY_PATH, "实验验证起步入口"),
                (RETRIEVAL_READER_ENTRY_PATH, "检索与文献管理总览"),
            ]
        ),
        "",
    ]
    direct = [
        note
        for note in direct_notes(notes, "13_阅读区/09_项目进展与管理")
        if note.rel_path
        not in {
            PROGRESS_READER_ENTRY_PATH,
            PROGRESS_EVIDENCE_READER_ENTRY_PATH,
            PROJECT_DECISION_READER_ENTRY_PATH,
            CONVERSATION_READER_ENTRY_PATH,
            RETRIEVAL_READER_ENTRY_PATH,
        }
    ]
    if direct:
        lines.extend(note_section("本层笔记", direct))
    return "\n".join(lines).rstrip() + "\n"


def build_specific_index(title: str, summary: str, note_paths: list[str], notes: dict[str, Note]) -> str:
    return cluster_note(title, summary, resolve_paths(notes, note_paths))


def build_attempt_folder_index(notes: dict[str, Note]) -> str:
    lines = [
        "# 工具与原型尝试索引",
        "",
        "## 先看主题总览",
        "",
        *bullet_links(
            [
                (ATTEMPT_PROTOTYPE_OVERVIEW_PATH, "原型路线总览"),
                (ATTEMPT_VAULT_PROTOTYPES_PATH, "Vault与论文流程原型索引"),
                (ATTEMPT_VALIDATION_PROTOTYPES_PATH, "验证表达与基线原型索引"),
                (ATTEMPT_CODEX_DIAGNOSTICS_PATH, "Codex App 线程排查索引"),
            ]
        ),
        "",
    ]
    direct = [note for note in direct_notes(notes, "15_尝试归档与索引/02_工具与原型尝试") if note.rel_path not in {ATTEMPT_PROTOTYPE_OVERVIEW_PATH, ATTEMPT_VAULT_PROTOTYPES_PATH, ATTEMPT_VALIDATION_PROTOTYPES_PATH, ATTEMPT_CODEX_DIAGNOSTICS_PATH}]
    if direct:
        lines.extend(note_section("本层尝试记录", direct))
    return "\n".join(lines).rstrip() + "\n"


def build_conversation_index(notes: dict[str, Note]) -> str:
    lines = [
        "# 会话索引",
        "",
        "## 主题入口",
        "",
        f"- {wikilink(CONVERSATION_THEME_NAV_PATH, '高价值会话主题导航')}",
        f"- {wikilink(CONVERSATION_SYSTEM_INDEX_PATH, '研究系统与知识库演进会话索引')}",
        f"- {wikilink(CONVERSATION_LEARNING_INDEX_PATH, 'OCT学习与逐篇文献会话索引')}",
        f"- {wikilink(CONVERSATION_DECONV_INDEX_PATH, '反卷积与验证会话索引')}",
        f"- {wikilink(CONVERSATION_TOOLING_INDEX_PATH, 'Codex与工具恢复会话索引')}",
        f"- {wikilink(CONVERSATION_CAREER_INDEX_PATH, '就业与行业观察会话索引')}",
        "",
    ]
    return "\n".join(lines)


def build_progress_index(notes: dict[str, Note]) -> str:
    items = descendants(notes, "04_Progress")
    lines = [
        "# 进展索引",
        "",
        "- 目录：`04_Progress`",
        f"- 笔记数：`{len(items)}`",
        "- 这里保留项目状态、决策、风险与进展判断；优先入口已经切成研究主线，而不是平铺文件名。",
        "",
        "## 先从主线进",
        "",
        *bullet_links(
            [
                (PROGRESS_THEME_NAV_PATH, "研究推进主线导航"),
                (PROGRESS_READER_ENTRY_PATH, "研究主线入口"),
                (PROGRESS_EVIDENCE_NAV_PATH, "研究问题证据链导航"),
                (PROGRESS_EVIDENCE_READER_ENTRY_PATH, "研究问题证据入口"),
                (PROGRESS_CORE_CONCLUSION_GUIDE_PATH, "核心结论入口"),
                (PROGRESS_KEY_PAPER_GUIDE_PATH, "关键论文档案入口"),
                (PROGRESS_FOUNDATION_PAPER_GUIDE_PATH, "方法奠基论文入口"),
                (PROGRESS_SYSTEM_PAPER_GUIDE_PATH, "系统专用化论文入口"),
                (PROGRESS_DECONV_PAPER_GUIDE_PATH, "反卷积主线论文入口"),
                (PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, "关键实验实例入口"),
                (PROGRESS_SUCCESS_EXPERIMENT_GUIDE_PATH, "验证成功样例入口"),
                (PROGRESS_FAILURE_EXPERIMENT_GUIDE_PATH, "失败与排障样例入口"),
                (PROGRESS_CALIBRATION_EXPERIMENT_GUIDE_PATH, "系统校准样例入口"),
                (PROGRESS_MANUSCRIPT_INDEX_PATH, "反卷积验证与稿件主线索引"),
                (PROGRESS_SPECTROMETER_INDEX_PATH, "OCT光谱仪系统专项索引"),
                (PROGRESS_PIPELINE_INDEX_PATH, "知识库与文献管线索引"),
                (PROGRESS_TRI_AGENT_INDEX_PATH, "Tri-Agent与控制平面索引"),
            ]
        ),
        "",
    ]
    direct = [
        note
        for note in direct_notes(notes, "04_Progress")
        if note.rel_path
        not in {
            PROGRESS_THEME_NAV_PATH,
            PROGRESS_EVIDENCE_NAV_PATH,
            PROGRESS_MANUSCRIPT_INDEX_PATH,
            PROGRESS_SPECTROMETER_INDEX_PATH,
            PROGRESS_PIPELINE_INDEX_PATH,
            PROGRESS_TRI_AGENT_INDEX_PATH,
            PROGRESS_CORE_CONCLUSION_GUIDE_PATH,
            PROGRESS_DECONV_CONCLUSION_GUIDE_PATH,
            PROGRESS_SYSTEM_CONCLUSION_GUIDE_PATH,
            PROGRESS_DELIVERY_CONCLUSION_GUIDE_PATH,
            PROGRESS_KEY_PAPER_GUIDE_PATH,
            PROGRESS_FOUNDATION_PAPER_GUIDE_PATH,
            PROGRESS_SYSTEM_PAPER_GUIDE_PATH,
            PROGRESS_DECONV_PAPER_GUIDE_PATH,
            PROGRESS_KEY_EXPERIMENT_GUIDE_PATH,
            PROGRESS_SUCCESS_EXPERIMENT_GUIDE_PATH,
            PROGRESS_FAILURE_EXPERIMENT_GUIDE_PATH,
            PROGRESS_CALIBRATION_EXPERIMENT_GUIDE_PATH,
            PROGRESS_DECONV_EVIDENCE_PATH,
            PROGRESS_SYSTEM_EVIDENCE_PATH,
            PROGRESS_DELIVERY_EVIDENCE_PATH,
        }
    ]
    if direct:
        lines.extend(note_section("时间与状态入口", direct))
    return "\n".join(lines).rstrip() + "\n"


def build_tasks_index(notes: dict[str, Note]) -> str:
    items = descendants(notes, "10_Tasks")
    lines = ["# 任务索引", "", "- 目录：`10_Tasks`", f"- 笔记数：`{len(items)}`", ""]
    primary = sorted(
        [
            note
            for note in items
            if not note.rel_path.startswith("10_Tasks/Tri-Agent/")
        ],
        key=lambda note: (note.title.lower(), note.rel_path.lower()),
    )
    if primary:
        lines.extend(note_section("核心任务入口", primary))
    tri_agent = [note for note in descendants(notes, "10_Tasks/Tri-Agent")]
    if tri_agent:
        lines.extend(note_section("Tri-Agent 协作任务", tri_agent))
    return "\n".join(lines).rstrip() + "\n"


def build_generated_files(notes: dict[str, Note]) -> dict[str, str]:
    directories = sorted({note.parent_folder for note in notes.values() if note.parent_folder})
    generated = {f"{folder}/_Index.md": build_folder_index(folder, notes) for folder in directories}
    generated.update(
        {
            "00_Home/知识库导航中心.md": build_home_navigation(notes),
            "00_Home/Home.md": build_home_landing(),
            "00_Home/目录总索引.md": build_master_index(notes),
            "00_Home/分类逻辑说明.md": build_logic_note(),
            "00_Home/知识库体检报告.md": build_health_note(notes),
            READER_START_ENTRY_PATH: build_reader_start_entry(),
            "13_阅读区/00_从这里开始/_Index.md": build_reader_start_index(notes),
            SYSTEM_READER_ENTRY_PATH: build_system_reader_entry(),
            "13_阅读区/01_OCT系统与原理/_Index.md": build_system_reader_index(notes),
            LITERATURE_READER_ENTRY_PATH: build_literature_reader_entry(),
            LITERATURE_BRIDGE_SHELF_PATH: build_literature_bridge_shelf(),
            LITERATURE_ROUTE_MAP_PATH: build_literature_route_map(),
            LITERATURE_DECONV_ROUTE_PATH: build_literature_deconv_route(),
            LITERATURE_SYSTEM_ROUTE_PATH: build_literature_system_route(),
            LITERATURE_BRIDGE_GUIDE_PATH: build_literature_bridge_guide(),
            LITERATURE_CHINESE_INDEX_PATH: build_literature_chinese_index(),
            "13_阅读区/02_文献阅读区/_Index.md": build_literature_reader_index(notes),
            EXPERIMENT_READER_ENTRY_PATH: build_experiment_reader_entry(),
            "13_阅读区/03_实验与评估/_Index.md": build_experiment_reader_index(notes),
            FIGURE_READER_ENTRY_PATH: build_figure_reader_entry(),
            "13_阅读区/04_图示与路线图/_Index.md": build_figure_reader_index(notes),
            WRITING_READER_ENTRY_PATH: build_writing_reader_entry(),
            "13_阅读区/05_写作与论文表达/_Index.md": build_writing_reader_index(notes),
            TERM_READER_ENTRY_PATH: build_term_reader_entry(),
            "13_阅读区/06_术语与问题/_Index.md": build_term_reader_index(notes),
            ACTION_READER_ENTRY_PATH: build_action_reader_entry(),
            "13_阅读区/07_未完成任务与下一步/_Index.md": build_action_reader_index(notes),
            EXECUTION_READER_ENTRY_PATH: build_execution_reader_entry(),
            "13_阅读区/08_日常规范与办事/_Index.md": build_execution_reader_index(notes),
            RETRIEVAL_READER_ENTRY_PATH: build_retrieval_reader_entry(),
            PROJECT_DECISION_READER_ENTRY_PATH: build_project_decision_reader_entry(),
            "02_Literature/Papers/_Index.md": build_papers_index(notes),
            "12_Zotero/04_Item-Backfills/_Index.md": build_zotero_index(notes),
            ATTEMPT_THEME_NAV_PATH: build_attempt_theme_navigation(notes),
            ATTEMPT_READER_ENTRY_PATH: build_attempt_reader_entry(),
            ATTEMPT_PROTOTYPE_OVERVIEW_PATH: "placeholder\n",
            ATTEMPT_VAULT_PROTOTYPES_PATH: build_specific_index("Vault与论文流程原型索引", "把与知识库结构、论文导入、阅读区组织相关的尝试收在一起。", ATTEMPT_VAULT_WORKFLOW_NOTES, notes),
            ATTEMPT_VALIDATION_PROTOTYPES_PATH: build_specific_index("验证表达与基线原型索引", "把 measured PSF、Gaussian baseline 和验证表达试验集中到一起。", ATTEMPT_VALIDATION_PROTOTYPE_NOTES, notes),
            ATTEMPT_CODEX_DIAGNOSTICS_PATH: build_specific_index("Codex App 线程排查索引", "收纳 Codex App 线程可见性、分页、pinned 持久化等排查记录。", ATTEMPT_CODEX_APP_NOTES, notes),
            CONVERSATION_THEME_NAV_PATH: build_conversation_theme_navigation(),
            CONVERSATION_READER_ENTRY_PATH: build_conversation_reader_entry(),
            CONVERSATION_SYSTEM_INDEX_PATH: build_specific_index("研究系统与知识库演进会话索引", "把 vault、Zotero、翻译交付和知识库治理相关会话放在一起。", CONVERSATION_SYSTEM_NOTES, notes),
            CONVERSATION_LEARNING_INDEX_PATH: build_specific_index("OCT学习与逐篇文献会话索引", "把 OCT 理论学习、逐篇文献梳理和读书式推进会话放在一起。", CONVERSATION_LEARNING_NOTES, notes),
            CONVERSATION_DECONV_INDEX_PATH: build_specific_index("反卷积与验证会话索引", "把 PSF、验证方案、Wiener / RL / blind RL 等主线会话收在一起。", CONVERSATION_DECONV_NOTES, notes),
            CONVERSATION_TOOLING_INDEX_PATH: build_specific_index("Codex与工具恢复会话索引", "把 Codex App、ECM、MATLAB、恢复与环境问题相关会话聚合起来。", CONVERSATION_TOOLING_NOTES, notes),
            CONVERSATION_CAREER_INDEX_PATH: build_specific_index("就业与行业观察会话索引", "把 OCT 就业、岗位、薪资和行业观察相关会话集中归档。", CONVERSATION_CAREER_NOTES, notes),
            PROGRESS_THEME_NAV_PATH: build_progress_theme_navigation(),
            PROGRESS_READER_ENTRY_PATH: build_progress_reader_entry(),
            PROGRESS_EVIDENCE_NAV_PATH: build_progress_evidence_navigation(),
            PROGRESS_EVIDENCE_READER_ENTRY_PATH: build_progress_evidence_reader_entry(),
            PROGRESS_CORE_CONCLUSION_GUIDE_PATH: build_core_conclusion_guide(notes),
            PROGRESS_DECONV_CONCLUSION_GUIDE_PATH: build_sectioned_note("反卷积结论入口", "把反卷积当前已经形成的主张、边界和争议点收成一条可回查的判断线。", PROGRESS_DECONV_CONCLUSION_GUIDE_SECTIONS, notes),
            PROGRESS_SYSTEM_CONCLUSION_GUIDE_PATH: build_sectioned_note("系统判断入口", "把 system-specific 当前判断、开放问题和关键讨论来源收成一条系统判断线。", PROGRESS_SYSTEM_CONCLUSION_GUIDE_SECTIONS, notes),
            PROGRESS_DELIVERY_CONCLUSION_GUIDE_PATH: build_sectioned_note("交付与治理结论入口", "把知识库治理、文献管线和交付策略当前已经形成的判断聚到一条交付与治理线。", PROGRESS_DELIVERY_CONCLUSION_GUIDE_SECTIONS, notes),
            PROGRESS_KEY_PAPER_GUIDE_PATH: build_key_paper_guide(notes),
            PROGRESS_FOUNDATION_PAPER_GUIDE_PATH: build_paper_line_guide("方法奠基论文入口", "把 OCT 成像原理、谱域 / swept-source 基线与早期关键论文收成一条方法奠基线，优先落到当前 workspace 已有论文笔记。", PROGRESS_FOUNDATION_PAPER_GUIDE_SECTIONS, notes),
            PROGRESS_SYSTEM_PAPER_GUIDE_PATH: build_paper_line_guide("系统专用化论文入口", "把系统实用化、高速谱域实现与工程化判断更相关的关键论文收成一条系统专用化线，优先落到当前 workspace 已有论文笔记。", PROGRESS_SYSTEM_PAPER_GUIDE_SECTIONS, notes),
            PROGRESS_DECONV_PAPER_GUIDE_PATH: build_paper_line_guide("反卷积主线论文入口", "把反卷积、超分辨和近年的综述收成一条主张与方法直接相关的论文主线，优先落到当前 workspace 已有论文笔记。", PROGRESS_DECONV_PAPER_GUIDE_SECTIONS, notes),
            PROGRESS_KEY_EXPERIMENT_GUIDE_PATH: build_key_experiment_guide(notes),
            PROGRESS_SUCCESS_EXPERIMENT_GUIDE_PATH: build_sectioned_note("验证成功样例入口", "把 formal verification、phantom 实例和收益判断收成一条更容易复查的正向验证线。", PROGRESS_SUCCESS_EXPERIMENT_GUIDE_SECTIONS, notes),
            PROGRESS_FAILURE_EXPERIMENT_GUIDE_PATH: build_sectioned_note("失败与排障样例入口", "把失败模式、raw-to-Bscan 调试和无真值约束放到一条负结果与排障链里，避免只记住最好看的案例。", PROGRESS_FAILURE_EXPERIMENT_GUIDE_SECTIONS, notes),
            PROGRESS_CALIBRATION_EXPERIMENT_GUIDE_PATH: build_sectioned_note("系统校准样例入口", "把光谱系统的证据采集、三窗口判断和像面/光路检查串成可回找的系统校准入口。", PROGRESS_CALIBRATION_EXPERIMENT_GUIDE_SECTIONS, notes),
            PROGRESS_MANUSCRIPT_INDEX_PATH: build_specific_index("反卷积验证与稿件主线索引", "把研究问题、验证边界、claim 与稿件推进相关记录串到一页。", PROGRESS_MANUSCRIPT_NOTES, notes),
            PROGRESS_SPECTROMETER_INDEX_PATH: build_specific_index("OCT光谱仪系统专项索引", "聚合 OCT 光谱仪 system-specific 模板、问题与决策图。", PROGRESS_SPECTROMETER_NOTES, notes),
            PROGRESS_PIPELINE_INDEX_PATH: build_specific_index("知识库与文献管线索引", "把 vault 架构、Zotero、翻译交付和 bridge 管线放到一条线里。", PROGRESS_PIPELINE_NOTES, notes),
            PROGRESS_TRI_AGENT_INDEX_PATH: build_specific_index("Tri-Agent与控制平面索引", "把 Tri-Agent 控制平面、任务总线和协作规则集中到一起。", PROGRESS_TRI_AGENT_NOTES, notes),
            PROGRESS_DECONV_EVIDENCE_PATH: build_sectioned_note("反卷积真实增益证据链", "把“反卷积到底有没有真实增益”这条问题线直接接到进展、实验、论文、写作和对话证据，并补上关键论文与关键实验实例入口。", PROGRESS_DECONV_EVIDENCE_SECTIONS + [("判断级入口", [PROGRESS_CORE_CONCLUSION_GUIDE_PATH, PROGRESS_DECONV_CONCLUSION_GUIDE_PATH]), ("对象级入口", [PROGRESS_KEY_PAPER_GUIDE_PATH, PROGRESS_FOUNDATION_PAPER_GUIDE_PATH, PROGRESS_SYSTEM_PAPER_GUIDE_PATH, PROGRESS_DECONV_PAPER_GUIDE_PATH, PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, PROGRESS_SUCCESS_EXPERIMENT_GUIDE_PATH, PROGRESS_FAILURE_EXPERIMENT_GUIDE_PATH, PROGRESS_CALIBRATION_EXPERIMENT_GUIDE_PATH])], notes),
            PROGRESS_SYSTEM_EVIDENCE_PATH: build_sectioned_note("OCT系统专用化证据链", "把 system-specific 判断从模板、实验清单、论文依据和讨论记录串成一条链，并补上关键论文与关键实验实例入口。", PROGRESS_SYSTEM_EVIDENCE_SECTIONS + [("判断级入口", [PROGRESS_CORE_CONCLUSION_GUIDE_PATH, PROGRESS_SYSTEM_CONCLUSION_GUIDE_PATH]), ("对象级入口", [PROGRESS_KEY_PAPER_GUIDE_PATH, PROGRESS_FOUNDATION_PAPER_GUIDE_PATH, PROGRESS_SYSTEM_PAPER_GUIDE_PATH, PROGRESS_DECONV_PAPER_GUIDE_PATH, PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, PROGRESS_SUCCESS_EXPERIMENT_GUIDE_PATH, PROGRESS_FAILURE_EXPERIMENT_GUIDE_PATH, PROGRESS_CALIBRATION_EXPERIMENT_GUIDE_PATH])], notes),
            PROGRESS_DELIVERY_EVIDENCE_PATH: build_sectioned_note("知识库持续交付证据链", "把 vault、Zotero、翻译交付和前台阅读入口放到同一条持续交付链上，并补上关键论文与关键实验实例入口。", PROGRESS_DELIVERY_EVIDENCE_SECTIONS + [("判断级入口", [PROGRESS_CORE_CONCLUSION_GUIDE_PATH, PROGRESS_DELIVERY_CONCLUSION_GUIDE_PATH]), ("对象级入口", [PROGRESS_KEY_PAPER_GUIDE_PATH, PROGRESS_FOUNDATION_PAPER_GUIDE_PATH, PROGRESS_SYSTEM_PAPER_GUIDE_PATH, PROGRESS_DECONV_PAPER_GUIDE_PATH, PROGRESS_KEY_EXPERIMENT_GUIDE_PATH, PROGRESS_SUCCESS_EXPERIMENT_GUIDE_PATH, PROGRESS_FAILURE_EXPERIMENT_GUIDE_PATH, PROGRESS_CALIBRATION_EXPERIMENT_GUIDE_PATH])], notes),
            "04_Progress/_Index.md": build_progress_index(notes),
            "10_Tasks/_Index.md": build_tasks_index(notes),
            "09_Conversations/_Index.md": build_conversation_index(notes),
            "13_阅读区/09_项目进展与管理/_Index.md": build_reader_project_progress_index(notes),
            "15_尝试归档与索引/02_工具与原型尝试/_Index.md": build_attempt_folder_index(notes),
        }
    )
    generated[ATTEMPT_PROTOTYPE_OVERVIEW_PATH] = "\n".join(
        [
            "# 原型路线总览",
            "",
            "## 三条原型路线",
            "",
            f"- {wikilink(ATTEMPT_VAULT_PROTOTYPES_PATH, 'Vault与论文流程原型索引')}",
            f"- {wikilink(ATTEMPT_VALIDATION_PROTOTYPES_PATH, '验证表达与基线原型索引')}",
            f"- {wikilink(ATTEMPT_CODEX_DIAGNOSTICS_PATH, 'Codex App 线程排查索引')}",
            "",
        ]
    )
    return generated


def generate_bundle(vault_root: Path, output_root: Path, run_label: str) -> Path:
    notes = scan_notes(vault_root)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = output_root / "vault-reorg" / f"{timestamp}-{run_label}"
    bundle_root = run_dir / "bundle"
    generated = build_generated_files(notes)
    for rel_path, content in generated.items():
        path = bundle_root / Path(rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    run_lines = [
        f"# {run_label}",
        "",
        f"- vault_root: `{vault_root}`",
        f"- generated_files: `{len(generated)}`",
        f"- source_notes: `{len([note for note in notes.values() if not note.is_index])}`",
        "",
    ]
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.md").write_text("\n".join(run_lines), encoding="utf-8")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild Obsidian navigation bundle.")
    parser.add_argument("--vault-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-label", default="obsidian-findability-reorg")
    args = parser.parse_args()
    run_dir = generate_bundle(args.vault_root, args.output_root, args.run_label)
    print(run_dir)


if __name__ == "__main__":
    main()
