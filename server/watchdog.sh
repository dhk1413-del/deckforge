#!/usr/bin/env bash
# SlideCraft 看门狗：每 60s 探活一次，挂了就用**同一个 HOST/PORT**重新拉起（脱离终端常驻）。
# 日志：data/logs/watchdog.log
# 启动：cd <仓库根> && nohup setsid bash server/watchdog.sh >/dev/null 2>&1 &
# 停止：pkill -f 'server/watchdog.sh'
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8641}"
LOG="$ROOT/data/logs/watchdog.log"
mkdir -p "$ROOT/data/logs"
echo "$(date -Is) watchdog 启动 (pid $$, ${HOST}:${PORT}, root=${ROOT})" >> "$LOG"
while true; do
  code=$(curl -s -m 5 --noproxy '*' -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/api/health" 2>/dev/null)
  if [ "$code" != "200" ]; then
    echo "$(date -Is) 健康检查=${code:-000} → 用 HOST=${HOST} PORT=${PORT} 重新拉起" >> "$LOG"
    HOST="$HOST" PORT="$PORT" bash "$ROOT/server/start-lan.sh" >> "$LOG" 2>&1
    sleep 8
    code2=$(curl -s -m 5 --noproxy '*' -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/api/health" 2>/dev/null)
    echo "$(date -Is) 重启后健康=${code2:-000}（pid 文件=$(cat "$ROOT/data/logs/deckforge.pid" 2>/dev/null || echo '?'))" >> "$LOG"
  fi
  sleep 60
done
