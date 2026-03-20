# Changelog

所有有意义的变更记录在此文件中。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

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
├── cli.py              # CLI 入口，所有子命令
├── client.py           # arXiv API HTTP 请求
├── config.py           # Settings 数据类
├── query.py            # 搜索查询字符串构造
├── parser.py           # Feed XML 解析
├── llm.py              # LLM 调用（统一 OpenAI 兼容通道）
├── summarizer.py       # 摘要生成策略（LLM / heuristic）
├── mailer.py           # SMTP 邮件发送
├── email_template.py   # 邮件 HTML 模板渲染
├── sitegen.py          # GitHub Pages 静态站点生成
├── output.py           # JSON/MD 文件输出
├── exporter.py         # MD → PDF 导出
├── extractors.py       # 链接提取（摘要/comments 中的 URL）
├── extrascrape.py      # 代码链接补全（HTML 页 + PDF 首页兜底）
└── scheduler.py        # 本地定时调度（非 Actions 场景）