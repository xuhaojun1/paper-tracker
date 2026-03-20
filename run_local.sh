#!/usr/bin/env bash
# ============================================================
# run_local.sh — 本地定时运行 Paper Tracker
#
# 用法：
#   1) 先确保 .env 文件已配置（参考 .env.example）
#   2) tmux new -s paper-tracker
#   3) bash run_local.sh              # 默认每周一 03:00 运行
#   4) Ctrl+B D 脱离 tmux
#
# 参数：
#   INTERVAL_DAYS   两次运行间隔天数（默认 7）
#   RUN_HOUR        每天几点检查是否该运行（24h，默认 3 = 凌晨3点）
#   SEND_EMAIL      是否发邮件（true/false，默认 true）
#   RUN_NOW         启动后是否立即运行一次（true/false，默认 false）
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── 可配置参数 ──
INTERVAL_DAYS="${INTERVAL_DAYS:-7}"
RUN_HOUR="${RUN_HOUR:-3}"
SEND_EMAIL="${SEND_EMAIL:-true}"
RUN_NOW="${RUN_NOW:-false}"
VENV_DIR="${VENV_DIR:-.venv}"

# ── 加载 .env ──
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
    echo "[run_local] 已加载 .env"
else
    echo "[run_local] 警告：未找到 .env 文件，请确保环境变量已设置"
fi

# ── 激活虚拟环境 ──
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
    echo "[run_local] 已激活虚拟环境: $VENV_DIR"
else
    echo "[run_local] 警告：未找到虚拟环境 $VENV_DIR，使用系统 Python"
fi

# ── 运行一次 tracker ──
run_once() {
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    echo "=========================================="
    echo "[run_local] 开始运行 @ $timestamp"
    echo "=========================================="

    local extra_flags="--verbose --site-dir docs"
    if [ "$SEND_EMAIL" != "true" ]; then
        extra_flags="$extra_flags --no-email"
    fi

    python -m arxiv_tracker.cli run \
        --config config.yaml \
        $extra_flags \
        || echo "[run_local] 运行出错，将在下次周期重试"

    # 自动提交生成的文件（如果在 git 仓库中）
    if git rev-parse --is-inside-work-tree &>/dev/null; then
        if git diff --quiet docs/ outputs/ .state/ 2>/dev/null; then
            echo "[run_local] 无文件变更，跳过提交"
        else
            git add docs/ outputs/ .state/ 2>/dev/null || true
            git commit -m "chore: update digest, site & dedup state (local)" 2>/dev/null || true
            git push origin main 2>/dev/null && echo "[run_local] 已推送到远端" \
                || echo "[run_local] 推送失败（可能无网络），下次重试"
        fi
    fi

    echo "[run_local] 本次运行完成 @ $(date '+%Y-%m-%d %H:%M:%S')"
}

# ── 主循环 ──
echo "[run_local] Paper Tracker 本地定时模式"
echo "[run_local] 间隔: ${INTERVAL_DAYS} 天 | 运行时间: 每天 ${RUN_HOUR}:00 检查"
echo "[run_local] 发邮件: $SEND_EMAIL | 立即运行: $RUN_NOW"
echo "[run_local] PID: $$"
echo ""

LAST_RUN_FILE="$SCRIPT_DIR/.state/.last_local_run"
mkdir -p "$SCRIPT_DIR/.state"

# 如果指定了立即运行
if [ "$RUN_NOW" = "true" ]; then
    run_once
    date +%s > "$LAST_RUN_FILE"
fi

while true; do
    current_hour=$(date +%H | sed 's/^0//')
    current_ts=$(date +%s)

    # 读取上次运行时间
    last_run_ts=0
    if [ -f "$LAST_RUN_FILE" ]; then
        last_run_ts=$(cat "$LAST_RUN_FILE" 2>/dev/null || echo 0)
    fi

    interval_secs=$((INTERVAL_DAYS * 86400))
    elapsed=$((current_ts - last_run_ts))

    # 到达指定小时 且 距上次运行已超过间隔
    if [ "$current_hour" -eq "$RUN_HOUR" ] && [ "$elapsed" -ge "$interval_secs" ]; then
        run_once
        date +%s > "$LAST_RUN_FILE"
        # 运行完后睡 1 小时，避免同一小时内重复触发
        sleep 3600
    else
        # 每 10 分钟检查一次
        next_check="$(date -d '+10 minutes' '+%H:%M' 2>/dev/null || date -v+10M '+%H:%M' 2>/dev/null || echo '10min later')"
        echo -ne "\r[run_local] 等待中... 上次运行: $([ $last_run_ts -gt 0 ] && date -d @$last_run_ts '+%m-%d %H:%M' 2>/dev/null || echo '从未') | 下次检查: $next_check  "
        sleep 600
    fi
done
