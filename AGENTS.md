# AGENTS.md — AI Agent 开发规则

本文件定义了 AI agent（如 Cascade、Cursor、Copilot 等）在本项目中进行开发时应遵循的规则与约定。

---

## 项目概述

**Paper Tracker** 是一个基于 GitHub Actions 的 arXiv 论文自动追踪系统。每 3 天自动检索指定方向的最新论文，通过 LLM 生成双语摘要，并通过邮件和 GitHub Pages 推送。

- **仓库**：`xuhaojun1/paper-tracker`
- **语言**：Python 3.10+
- **核心包**：`arxiv_tracker/`
- **CI/CD**：GitHub Actions（`.github/workflows/digest.yml`）
- **配置**：`config.yaml`（所有运行参数集中管理）

---

## 代码规范

### 通用
- 代码注释和文档使用**中文**（用户母语），变量名和函数名使用**英文**
- 保持现有代码风格：无 type hints 时保持一致，有 type hints 的模块继续使用
- 每个文件顶部保留 `# -*- coding: utf-8 -*-`（如已有）
- 不要删除现有注释，除非内容已过时或用户明确要求

### Python
- 依赖管理：`requirements.txt`，添加新依赖时注明最低版本（`>=`）
- 入口：`arxiv_tracker/cli.py`（Click CLI），`main.py` 为便捷入口
- 配置读取：统一通过 `config.yaml` + 环境变量，环境变量优先级高于配置文件
- LLM 调用：统一走 `arxiv_tracker/llm.py` 中的 `_chat_completions_request()`，不要引入新的 HTTP 调用方式
- 错误处理：用 `click.secho(..., fg="red/yellow")` 输出，关键流程需 try-except 兜底



## 配置与密钥

### 绝对禁止
- **不得在代码中硬编码任何 API Key、密码、邮箱地址**
- 不得将 `.env` 文件提交到 Git

### 密钥管理
- 所有密钥通过 GitHub Secrets 注入环境变量
- `config.yaml` 中用 `*_env` 字段指定环境变量名（如 `api_key_env: "OPENAI_COMPAT_API_KEY"`）
- 代码中通过 `os.getenv()` 读取，提供合理的缺失提示

### 环境变量优先级
```
环境变量 > config.yaml > 代码默认值
```

---

## Git 与版本控制

### Commit 规范
使用语义化前缀：
- `feat:` — 新功能
- `fix:` — 修复 bug
- `chore:` — 构建/CI/依赖/清理
- `docs:` — 文档变更
- `refactor:` — 重构（不改变行为）
- `style:` — 格式调整（不影响逻辑）

### 分支
- `main` 为唯一长期分支，GitHub Pages 从 `main` 的 `/docs` 部署
- 大功能开新分支，完成后 merge 到 `main`

### 自动提交（Actions）
- Actions 运行后自动提交 `docs/**`、`outputs/**`、`.state/**`

---

## GitHub Actions

### 工作流文件
- 唯一工作流：`.github/workflows/digest.yml`
- cron: `0 19 */3 * *`（每 3 天 UTC 19:00 = 北京时间次日 03:00）
- 支持 `workflow_dispatch` 手动触发（带发邮件开关）

### 修改注意
- 修改 cron 时确保与 `config.yaml` 中 `freshness.since_days` 匹配
- 新增 env 变量需同步更新 README 的 Secrets/Variables 表格
- 并发控制 `concurrency` 不要移除，防止重复执行

---

## 测试

- 本地测试：`python -m arxiv_tracker.cli run --config config.yaml --no-email --verbose`
- LLM 测试：确保 `OPENAI_COMPAT_API_KEY` 环境变量已设置
- 邮件测试：手动触发 Actions 并设 `send_email: true`

---

## 变更记录

所有有意义的变更需记录到 `CHANGELOG.md`，格式参照该文件中的现有条目。

---
