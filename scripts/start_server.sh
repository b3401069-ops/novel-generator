#!/usr/bin/env bash
# 小說工坊 Novel Forge — 常駐啟動腳本
#
# 冪等設計：已在健康服務中就直接結束、不重複啟動；否則清掉殘留行程並
# 以 setsid 開新 session 完整脫離啟動（父行程退出時不會被 SIGHUP 帶走，
# 這是 WSL 一次性指令啟動背景服務會被回收的解法）。
#
# 用法：
#   bash scripts/start_server.sh          # 啟動（已在跑則跳過）
#   bash scripts/start_server.sh restart  # 強制重啟（套用 .env 變更）
#
# 這支腳本被 /etc/wsl.conf 的 [boot] command 與 Windows 登入排程共用，
# 所以務必保持冪等。

set -u

# 腳本所在目錄的上一層即專案根目錄（可從任何路徑呼叫）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
PORT="${PORT:-8012}"
LOG="$APP_DIR/server.log"

cd "$APP_DIR" || { echo "找不到專案目錄: $APP_DIR" >&2; exit 1; }

healthy() {
    curl -sf -o /dev/null "http://127.0.0.1:$PORT/health" 2>/dev/null
}

# restart 模式：先殺掉現有行程
if [ "${1:-}" = "restart" ]; then
    pkill -f "python3 main.py" 2>/dev/null
    sleep 2
fi

# 冪等：已健康就不動作
if healthy; then
    echo "server 已在 :$PORT 服務中"
    exit 0
fi

# 清掉任何殘留（沒在聽 port 但行程還在的情況）
pkill -f "python3 main.py" 2>/dev/null
sleep 1

# 完整脫離啟動：新 session + 關閉繼承的 FD，避免被父行程退出時的訊號帶走
setsid bash -c "exec python3 main.py >> '$LOG' 2>&1" < /dev/null > /dev/null 2>&1 &
disown 2>/dev/null || true

# 最多等 15 秒讓它綁定並健康
for _ in $(seq 1 15); do
    if healthy; then
        echo "server 已啟動於 :$PORT"
        exit 0
    fi
    sleep 1
done

echo "server 啟動後未通過健康檢查 — 請看 $LOG" >&2
exit 1
