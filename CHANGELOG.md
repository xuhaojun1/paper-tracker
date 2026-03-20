# Changelog

所有有意义的变更记录在此文件中。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [0.3.0] - 2026-07-14

### LLM 重要度打分 & HTML 全文深度分析 & 架构重构

**Added**
- `html_fetcher.py`：新增 arXiv HTML 全文抓取模块，自动提取 Abstract / Introduction / Method / Experiment / Conclusion 等关键章节
- `pipeline.py`：新增工作流管线模块，将核心逻辑从 `cli.py` 拆分为独立的阶段函数（`fetch_papers` → `augment_links` → `score_and_filter` → `fetch_html_content` → `generate_summaries` → `translate_items`）
- `llm.py`：新增 `call_llm_score_papers()` — LLM 重要度打分（1-10 分），评分维度：方法创新性 40% / 领域相关性 30% / 影响力与泛化性 20% / 可复现性 10%；分批处理避免 token 溢出；返回分数 + 评分理由
- `llm.py`：新增 `call_llm_rich_summary()` — 基于 HTML 全文章节的高质量结构化双语摘要（比纯 abstract 版本更具体，包含方法细节、benchmark 数据等）
- `config.yaml`：新增 `scrape.html_fulltext` / `scrape.html_fulltext_timeout` 配置项，控制 HTML 全文抓取
- `sitegen.py` / `email_template.py` / `output.py`：论文卡片新增重要度评分徽章（颜色按分数区分：红/橙/黄/灰）和评分理由展示

**Changed**
- `cli.py`：重构为轻量级调度层，核心工作流逻辑移至 `pipeline.py`（cli.py 行数从 537 → ~350）
- `llm.py`：原 `call_llm_filter_papers()` 改为基于 `call_llm_score_papers()` 的兼容包装，不再使用二值筛选
- `config.yaml`：`max_results` 从 50 → 200（扩大搜索范围）
- `config.yaml`：`filter.top_k` 从 20 → 50（打分后保留 50 篇最重要论文）
- `config.yaml`：`freshness.since_days` 从 3 → 7（匹配一周运行周期）
- `digest.yml`：cron 从 `*/3 天` 改为**每周一** UTC 19:00（`0 19 * * 1`）
- `README.md`：更新功能描述、仓库结构、配置说明，反映新的打分和全文分析功能

**工作流变更**
- 旧流程：关键词搜索 50 篇 → LLM 二值筛选 20 篇 → 纯 abstract 摘要
- 新流程：关键词搜索 200 篇 → LLM 打分排序保留 50 篇 → 抓取 HTML 全文 → 基于全文的深度摘要

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
├── cli.py              # CLI 入口，参数解析与调度
├── pipeline.py         # 核心工作流管线（搜索→打分→全文→摘要→翻译）
├── html_fetcher.py     # arXiv HTML 全文抓取与章节提取
├── client.py           # arXiv API HTTP 请求
├── config.py           # Settings 数据类
├── query.py            # 搜索查询字符串构造
├── parser.py           # Feed XML 解析
├── llm.py              # LLM 调用（打分/摘要/翻译，统一 OpenAI 兼容通道）
├── summarizer.py       # 摘要生成策略（LLM / heuristic）
├── mailer.py           # SMTP 邮件发送
├── email_template.py   # 邮件 HTML 模板渲染
├── sitegen.py          # GitHub Pages 静态站点生成
├── output.py           # JSON/MD 文件输出
├── exporter.py         # MD → PDF 导出
├── extractors.py       # 链接提取（摘要/comments 中的 URL）
├── extrascrape.py      # 代码链接补全（HTML 页 + PDF 首页兜底）
└── scheduler.py        # 本地定时调度（非 Actions 场景）