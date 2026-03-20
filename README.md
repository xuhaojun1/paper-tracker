# Paper Tracker · 论文自动追踪与推送

![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=flat-square&logo=python)
[![License: MIT](https://img.shields.io/badge/License-MIT-black.svg?style=flat-square)](./LICENSE)

> 基于 [Arxiv-tracker](https://github.com/colorfulandcjy0806/Arxiv-tracker) 二次开发，感谢原作者。

**每 3 天自动检索 arXiv 论文 → LLM 双语总结 → 邮件推送 + GitHub Pages 发布。**

当前追踪方向：
- **视频生成 / 世界模型**：`video generation`, `world model`
- **VLA**：`vision-language-action`, `VLA`
- **3D 重建**：`3D reconstruction`, `VGGT`, `3D Gaussian`

---

## 功能特性

- **多关键词检索**：`cs.CV / cs.LG / cs.AI` 分类 + 关键词 AND/OR 组合
- **LLM 双语总结**：英文 + 中文一段式摘要（支持任意 OpenAI 兼容 API）
- **自动提取链接**：Abs / PDF / 代码仓库 / 项目页
- **邮件推送**：支持 QQ 邮箱 / Gmail（SMTP 465/SSL 或 587/STARTTLS）
- **GitHub Pages**：自动生成静态站点，历史归档
- **去重 + 新鲜度**：仅推送近 N 天且未发送过的论文
- **GitHub Actions 定时运行**：每 3 天自动执行（可自定义 cron）

---

## 仓库结构

```
arxiv_tracker/        # 核心 Python 包（检索、解析、摘要、邮件、站点生成）
docs/                 # GitHub Pages 站点输出（自动生成）
outputs/              # 每次运行保存的 JSON/MD（自动生成）
.state/               # 去重状态（seen.json，随仓库提交保存）
.github/workflows/    # digest.yml — 每 3 天定时任务
config.yaml           # 全部配置（检索/LLM/邮件/站点/去重）
requirements.txt      # Python 依赖
AGENTS.md             # AI agent 开发规则
CHANGELOG.md          # 版本记录
```

---

## 快速部署

### 1) Clone 或 Fork

```bash
git clone https://github.com/xuhaojun1/paper-tracker.git
```

### 2) 配置 GitHub Secrets & Variables

> Settings → **Secrets and variables** → **Actions**

**Secrets（必填）**

| 名称 | 说明 |
|------|------|
| `OPENAI_COMPAT_API_KEY` | OpenAI 兼容 API Key（中转站 / DeepSeek / SiliconFlow） |
| `SMTP_PASS` | 邮箱 SMTP 授权码（QQ 用授权码，Gmail 用应用专用密码） |

**Variables（必填）**

| 名称 | 说明 | 示例 |
|------|------|------|
| `EMAIL_TO` | 收件人（多个用 `,` 分隔） | `a@qq.com,b@gmail.com` |
| `EMAIL_SENDER` | 发件人邮箱 | `xxx@qq.com` |
| `SMTP_USER` | SMTP 用户名（通常 = 发件人） | `xxx@qq.com` |

**Variables（可选，用于切换邮件服务商）**

| 名称 | 默认值 | Gmail 设置 |
|------|--------|-----------|
| `SMTP_SERVER` | `smtp.qq.com` | `smtp.gmail.com` |
| `SMTP_PORT` | `465` | `465` |

### 3) 启用 GitHub Pages

Settings → **Pages** → Source: **Deploy from a branch** → Branch: `main`, Folder: `/docs`

### 4) 运行

- **自动**：每 3 天 UTC 19:00（北京时间次日 03:00）自动运行
- **手动**：Actions → `paper-tracker-digest` → Run workflow（可选是否发邮件）

---

## 本地运行

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_COMPAT_API_KEY="your-key"
export EMAIL_TO="your@email.com"
export EMAIL_SENDER="your@email.com"
export SMTP_USER="your@email.com"
export SMTP_PASS="your-smtp-password"

python -m arxiv_tracker.cli run --config config.yaml --site-dir docs --verbose
```

---

## 配置说明

所有配置在 `config.yaml` 中，主要字段：

| 区块 | 关键字段 | 说明 |
|------|---------|------|
| 检索 | `categories`, `keywords`, `logic` | arXiv 分类 + 关键词，AND/OR 组合 |
| LLM | `base_url`, `model`, `api_key_env` | 任意 OpenAI 兼容 API |
| 邮件 | `smtp_server`, `smtp_port`, `tls` | QQ / Gmail SMTP |
| 站点 | `dir`, `title`, `theme` | GitHub Pages 输出 |
| 新鲜度 | `since_days`, `unique_only` | 时间窗 + 去重 |

## License

MIT — 详见 [LICENSE](./LICENSE)。
