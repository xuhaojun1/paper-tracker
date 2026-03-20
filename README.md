# Paper Tracker · 论文自动追踪与推送

![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=flat-square&logo=python)
[![License: MIT](https://img.shields.io/badge/License-MIT-black.svg?style=flat-square)](./LICENSE)

**每周自动检索 arXiv 论文 → LLM 重要度打分排序 → HTML 全文深度分析 → 邮件推送 + GitHub Pages 发布。**

当前追踪方向：
- **视频生成 / 世界模型**：`video generation`, `world model`
- **VLA**：`vision-language-action`, `VLA`
- **3D 重建**：`3D reconstruction`, `VGGT`, `3D Gaussian`

---

## 功能特性

- **大范围检索**：`cs.CV / cs.LG / cs.AI` 分类 + 关键词，每周检索 200 篇候选论文
- **LLM 重要度打分**：每篇论文 1-10 分评分（方法创新性 40% / 领域相关性 30% / 影响力 20% / 可复现性 10%），按分数降序排列，保留 Top 50
- **HTML 全文深度分析**：抓取 arXiv HTML 页面，提取 Method / Experiment 等章节，LLM 基于全文生成更高质量的结构化双语摘要
- **自动提取链接**：Abs / PDF / 代码仓库 / 项目页
- **邮件推送**：支持 QQ 邮箱 / Gmail（SMTP 465/SSL 或 587/STARTTLS）
- **GitHub Pages**：自动生成静态站点，带重要度徽章和评分理由
- **去重 + 新鲜度**：仅推送近 7 天且未发送过的论文
- **GitHub Actions 定时运行**：每周一自动执行（可自定义 cron）

---

## 仓库结构

```
arxiv_tracker/            # 核心 Python 包
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
│   ├── summary.py        #   摘要生成（双语结构化 + 全文版 + 启发式兜底）
│   └── translate.py      #   标题/摘要中文翻译
├── notify/               # 输出与通知
│   ├── mailer.py         #   SMTP 邮件发送
│   ├── email_template.py #   邮件 HTML 模板
│   ├── sitegen.py        #   GitHub Pages 静态站点生成
│   └── output.py         #   JSON/MD 文件输出
└── utils/                # 通用工具
    ├── state.py          #   去重状态管理
    └── logging.py        #   统一日志

docs/                     # GitHub Pages 站点输出（自动生成）
outputs/                  # 每次运行保存的 JSON/MD（自动生成）
.state/                   # 去重状态（seen.json，随仓库提交保存）
.github/workflows/        # digest.yml — 每周定时任务
config.yaml               # 全部配置（检索/LLM/邮件/站点/去重）
requirements.txt          # Python 依赖
```

---

## 快速部署

### 1) Clone 或 Fork

```bash
git clone https://github.com/xuhaojun1/paper-tracker.git
```

### 2) 配置 GitHub Secrets

> Settings → **Secrets and variables** → **Actions** → **Secrets**

| 名称 | 说明 |
|------|------|
| `OPENAI_COMPAT_API_KEY` | OpenAI 兼容 API Key（中转站 / DeepSeek / SiliconFlow） |
| `EMAIL_ADDR` | 邮箱地址（同时用作发件人、SMTP 用户名、收件人） |
| `SMTP_PASS` | 邮箱 SMTP 授权码（QQ 用授权码，Gmail 用应用专用密码） |

> SMTP 服务器等已在 `config.yaml` 中配置，**无需设置 Variables**。
> 如需分别指定发件人/收件人，可额外设置 `EMAIL_SENDER` / `EMAIL_TO` / `SMTP_USER`。

### 3) 启用 GitHub Pages

Settings → **Pages** → Source: **Deploy from a branch** → Branch: `main`, Folder: `/docs`

### 4) 运行

- **自动**：每周一 UTC 19:00（北京时间周二 03:00）自动运行
- **手动**：Actions → `paper-tracker-digest` → Run workflow（可选是否发邮件）

---

## 本地运行

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_COMPAT_API_KEY="your-key"
export EMAIL_ADDR="your@qq.com"
export SMTP_PASS="your-smtp-password"   # QQ 邮箱授权码

# 不发邮件测试
python -m arxiv_tracker.cli run --config config.yaml --no-email --verbose

# 完整运行（含邮件）
python -m arxiv_tracker.cli run --config config.yaml --site-dir docs --verbose
```

---

## git连接配置
```bash
git remote set-url origin git@github.com:xuhaojun1/paper-tracker.git
```

## 配置说明

所有配置在 `config.yaml` 中，主要字段：

| 区块 | 关键字段 | 说明 |
|------|---------|------|
| 检索 | `categories`, `keywords`, `logic` | arXiv 分类 + 关键词，AND/OR 组合 |
| LLM | `base_url`, `model`, `api_key_env` | 任意 OpenAI 兼容 API |
| 邮件 | `smtp_server`, `smtp_port`, `tls` | QQ / Gmail SMTP |
| 站点 | `dir`, `title`, `theme` | GitHub Pages 输出 |
| 筛选 | `filter.enabled`, `filter.top_k` | LLM 重要度打分，保留 Top K |
| HTML全文 | `scrape.html_fulltext` | 抓取论文全文供 LLM 深度分析 |
| 新鲜度 | `since_days`, `unique_only` | 时间窗 + 去重 |

## License

MIT — 详见 [LICENSE](./LICENSE)。
