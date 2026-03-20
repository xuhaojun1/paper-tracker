# Changelog

所有有意义的变更记录在此文件中。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [0.3.1] - 2026-03-20

### 清理合并冲突 & 本地定时运行支持

**Added**
- `run_local.sh`：本地 tmux 定时运行脚本，支持自定义间隔/时间/邮件开关，自动加载 `.env`、激活 venv、运行后 git commit + push
- `.env.example`：环境变量模板文件

**Fixed**
- 清理 `CHANGELOG.md` / `README.md` / `cli.py` 中残留的合并冲突标记（`<<<<<<<` / `>>>>>>>` ）
- 删除重构后遗留的 14 个旧扁平文件（`client.py`、`llm.py`、`summarizer.py`、`scheduler.py`、`exporter.py` 等），它们已被 `search/`、`llm/`、`notify/`、`utils/` 子包替代
- 将 `mailer.py` 移入 `notify/` 子包（修复 `notify/__init__.py` 导入缺失）

**Refactored**
- `llm/prompts.py`：重写打分 prompt，明确描述三大研究方向（视频生成/世界模型、VLA、3D重建），按方向语义评分而非简单关键词匹配；删除旧 `build_two_stage_prompt`
- `llm/summary.py`：删除旧兼容函数 `call_llm_two_stage`（含 TL;DR 解析逻辑）；`build_two_stage_summary` 精简为 `build_summary`，移除冗余的 `tldr`/`full_md` 旧字段
- `llm/scoring.py`：删除旧兼容函数 `call_llm_filter_papers`
- `llm/__init__.py`：导出列表精简，移除 4 个已删除函数
- `pipeline.py`：`generate_summaries` 移除不再需要的 `lang`/`scope` 参数

**Changed**
- `digest.yml`：移除已废弃的 Cairo 系统依赖安装和 pycairo 构建工具步骤（PDF 导出功能已在 v0.3.0 移除）
- `requirements.txt`：移除 `schedule`（本地调度已删除）和 `xhtml2pdf`（PDF 导出已删除）
- `AGENTS.md`：修正 cron 描述为实际的每周一 `0 19 * * 1`；更新项目概述
- `README.md`：修复仓库结构描述；新增「服务器 tmux 定时运行」文档

---

## [0.3.0] - 2026-07-14

### 项目架构重构 & LLM 重要度打分 & 纯中文输出

**架构重构**
- 将 18 个扁平文件重构为 4 个子包：`search/`（论文搜索与获取）、`llm/`（LLM 交互层）、`notify/`（输出与通知）、`utils/`（通用工具）
- 原 `llm.py`（466 行）拆分为 5 个模块：`api_client.py`（HTTP 客户端）、`prompts.py`（prompt 模板）、`scoring.py`（打分）、`summary.py`（摘要）、`translate.py`（翻译）
- `pipeline.py` 解耦 Click 框架，改用 `utils/logging.py` 统一日志
- 去重状态管理提取到 `utils/state.py`
- 原 `summarizer.py` 合并入 `llm/summary.py`
- 原 `extrascrape.py` 重命名为 `search/scraper.py`

**Added**
- `search/html_fetcher.py`：arXiv HTML 全文抓取，提取 Abstract / Method / Experiment 等章节
- `llm/scoring.py`：LLM 重要度打分（1-10 分），评分维度：方法创新性 40% / 相关性 30% / 影响力 20% / 可复现性 10%
- `llm/prompts.py`：所有 prompt 模板独立管理，与 API 调用分离
- `utils/logging.py`：统一日志模块，替代 pipeline 中的 `click.echo`
- `config.yaml`：新增 `scrape.html_fulltext` / `scrape.html_fulltext_timeout` 配置项

**Changed**
- LLM 摘要输出从英中双语（8 字段 `*_en` / `*_zh`）改为**纯中文**（4 字段 `motivation` / `method` / `experiments` / `limitations`），减少 token 消耗和冗余
- `config.yaml`：`max_results` 50 → 200，`filter.top_k` 20 → 50，`freshness.since_days` 3 → 7
- `digest.yml`：cron 改为每周一 UTC 19:00（`0 19 * * 1`）
- 站点 / 邮件 / Markdown 输出全部适配纯中文字段 + 重要度评分徽章

**Removed**
- `scheduler.py`：本地定时调度（改用 GitHub Actions）
- `exporter.py`：MD → PDF 导出
- `--pdf` CLI 选项

**工作流变更**
- 旧流程：搜索 50 篇 → LLM 二值筛选 20 篇 → 英中双语摘要
- 新流程：搜索 200 篇 → LLM 打分排序保留 50 篇 → 抓取 HTML 全文 → 纯中文深度摘要

---

## [0.2.0] - 2026-03-19

### LLM 结构化摘要 & 输出优化

**Changed**
- `llm.py`：LLM 摘要改为结构化四维度分析（motivation / method / experiments / limitations），先生成英文再翻译中文，每维度严格 1-2 句，减少冗余
- `llm.py`：`max_tokens` 从 600 → 800，单次调用同时输出中英双语（之前每篇论文调 2 次 LLM，现在只调 1 次）
- `summarizer.py`：`build_two_stage_summary` 适配新的 8 字段结构，`heuristic_paragraphs` 兜底同步更新
- `output.py`：去掉 `[中文]` / `[English]` 重复区块，改为单个合并的「Structured Analysis / 结构化分析」区块
- `sitegen.py`：GitHub Pages 卡片渲染适配结构化四维度分析（默认展开）
- `email_template.py`：邮件 HTML 模板同步适配结构化分析
- `cli.py`：`lang="both"` 时只调用一次 summary，不再分 zh/en 重复调用
- Git remote 从 HTTPS 切换为 SSH（`git@github.com:xuhaojun1/paper-tracker.git`）
- `config.yaml`：邮箱地址从硬编码改为通过环境变量 `EMAIL_ADDR` 统一注入（避免公开仓库泄露邮箱）
- `cli.py`：支持 `EMAIL_ADDR` 环境变量同时作为 sender / smtp_user / to
- `digest.yml`：移除所有 Variables 引用，只需 3 个 Secrets（`OPENAI_COMPAT_API_KEY` / `EMAIL_ADDR` / `SMTP_PASS`）

**Added**
- `llm.py`：新增 `call_llm_filter_papers()` — LLM 预筛选，批量发送标题+摘要片段给 LLM 打分，只对相关论文生成详细摘要
- `config.yaml`：新增 `filter` 配置区块（`enabled` / `top_k` / `prompt`）

**Fixed**
- `output.py`：修复 `digest_en` / `digest_zh` 不渲染的 bug（旧代码只检查 `tldr` / `full_md`）
- `sitegen.py`：修复 History 列表显示已删除旧归档链接的 bug，增加自动清理超出 `keep_runs` 的旧文件
- `config.yaml`：`keep_runs` 从 1024 降到 30（约 3 个月）

**Removed**
- `docs/archive/` 中原仓库遗留的 252 个旧归档 HTML 文件（2025-08 ~ 2026-03-18），只保留自己生成的

---

## [0.1.0] - 2025-03-19

### 基于 Arxiv-tracker 的初始定制化版本

**Changed**
- 仓库重命名为 `paper-tracker`，远端指向 `xuhaojun1/paper-tracker`
- 搜索关键词更新为三个研究方向：
  - 视频生成 / 世界模型：`video generation`, `world model`
  - VLA：`vision-language-action`, `VLA`
  - 3D 重建：`3D reconstruction`, `VGGT`, `3D Gaussian`
- LLM 提供商切换为 OpenAI 兼容中转站（`api.agicto.cn`，模型 `gpt-5.4`）
- GitHub Actions cron 改为每 3 天运行一次（`0 19 */3 * *`）
- `freshness.since_days` 从 3650 改为 3，匹配 3 天运行周期
- 邮件推送新增 Gmail 支持（通过 `SMTP_SERVER` / `SMTP_PORT` 环境变量切换）
- `max_results` 从 30 提升到 50

**Added**
- `AGENTS.md` — AI agent 开发规则与项目约定
- `CHANGELOG.md` — 版本变更记录
- `.gitignore` 扩展（`.venv/`, `.env`, IDE 文件等）

**Removed**
- `arxiv_daily.yml`（与 `digest.yml` 功能重复）
- `test_sf.py`（临时测试文件）
- `README_EN.md`（合并到主 README）

**Fixed**
- `cli.py` 中 SMTP 服务器/端口支持环境变量覆盖，使 Gmail 配置生效

---

## [0.0.0] - 2025-08-22 (原项目)

> 以下为 fork 来源 [colorfulandcjy0806/Arxiv-tracker](https://github.com/colorfulandcjy0806/Arxiv-tracker) 的历史功能。

- 初版：arXiv 检索 → LLM 摘要/翻译 → 邮件/网页
- Freshness + 去重持久化
- OpenAI-Compatible LLM 支持（DeepSeek / SiliconFlow）
- 自动分页抓取
- 代码链接补全（HTML + PDF 兜底）
- 排除关键词功能


目前文件结构：
arxiv_tracker/
├── cli.py                # CLI 入口，参数解析与调度
├── pipeline.py           # 核心工作流管线（搜索→打分→全文→摘要→翻译）
├── config.py             # Settings 数据类 + YAML 加载
├── search/               # 论文搜索与获取
│   ├── query.py          #   arXiv 查询字符串构造
│   ├── client.py         #   arXiv API HTTP 请求 + 重试
│   ├── parser.py         #   Feed XML 解析
│   ├── scraper.py        #   代码链接补全（HTML页 + PDF兜底）
│   ├── html_fetcher.py   #   HTML 全文抓取 + 章节提取
│   └── extractors.py     #   URL / venue 提取工具
├── llm/                  # LLM 交互层
│   ├── api_client.py     #   OpenAI 兼容 HTTP 客户端
│   ├── prompts.py        #   所有 prompt 模板（打分/摘要/翻译）
│   ├── scoring.py        #   论文重要度打分
│   ├── summary.py        #   摘要生成（中文结构化 + 全文版 + 启发式兜底）
│   └── translate.py      #   标题/摘要中文翻译
├── notify/               # 输出与通知
│   ├── mailer.py         #   SMTP 邮件发送
│   ├── email_template.py #   邮件 HTML 模板
│   ├── sitegen.py        #   GitHub Pages 静态站点生成
│   └── output.py         #   JSON/MD 文件输出
└── utils/                # 通用工具
    ├── state.py          #   去重状态管理
    └── logging.py        #   统一日志