#!/usr/bin/env bash
# DeckForge 守护启动（脱离终端，关掉终端/退出 Hermes 也不会停）
#
# 用法：
#   bash server/start-lan.sh              # 127.0.0.1:8641（只本机，默认）
#   PORT=8640 bash server/start-lan.sh    # 换端口
#   HOST=0.0.0.0 bash server/start-lan.sh   # 显式开放局域网访问
#   bash server/stop-daemon.sh            # 停掉
#
# 说明：macOS 的 launchd LaunchAgent 读不了 ~/Documents（TCC 隐私保护），
#       所以这里必须创建新 session：某些 exec/PTY 会在会话结束时杀整个进程组，
#       单靠 nohup 仍会被带走。Python 的 start_new_session=True 使 uvicorn 不属于该组。
set -e
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8641}"
LOG_DIR="$ROOT/data/logs"
PID_FILE="$LOG_DIR/deckforge.pid"
mkdir -p "$LOG_DIR"

if curl -s -m 3 --noproxy '*' "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
  echo "== 服务已在运行：http://127.0.0.1:${PORT} =="
else
  # 端口可能还压在"上一次进程正在退出"的状态上，等它释放再起，避免抢端口失败。
  for _ in $(seq 1 20); do
    lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1 || break
    sleep 0.5
  done
  if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "!! 端口 ${PORT} 被占用（且健康检查不通过）：先 bash server/stop-daemon.sh 再重试"
    lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN | cat
    exit 1
  fi
  echo "== 启动 DeckForge（HOST=${HOST} PORT=${PORT}）=="
  DECKFORGE_ROOT="$ROOT" DECKFORGE_HOST="$HOST" DECKFORGE_PORT="$PORT" DECKFORGE_LOG="$LOG_DIR/server.log" \
    python3 - <<'PY'
import os
import subprocess

# run.sh 最终 exec uvicorn，因此 Popen 返回的就是实际 uvicorn PID；新 session 防止 PTY 清场连带终止服务。
proc = subprocess.Popen(
    ["bash", os.path.join(os.environ["DECKFORGE_ROOT"], "server", "run.sh")],
    stdin=subprocess.DEVNULL,
    stdout=open(os.environ["DECKFORGE_LOG"], "ab"),
    stderr=subprocess.STDOUT,
    start_new_session=True,
    env=os.environ.copy(),
)
with open(os.path.join(os.path.dirname(os.environ["DECKFORGE_LOG"]), "deckforge.pid"), "w") as f:
    f.write(str(proc.pid) + "\n")
PY
  for _ in $(seq 1 40); do
    curl -s -m 2 --noproxy '*' "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1 && break
    sleep 0.5
  done
fi

if curl -s -m 3 --noproxy '*' "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
  echo "== 已就绪（pid $(cat "$PID_FILE" 2>/dev/null || echo '?')，日志 data/logs/server.log）=="
  echo "   本机：http://127.0.0.1:${PORT}"
  for IF in en0 en1; do
    IP="$(ipconfig getifaddr "$IF" 2>/dev/null || true)"
    if [ -n "$IP" ]; then echo "   局域网：http://${IP}:${PORT}"; fi
  done
  exit 0
else
  echo "!! 启动失败，最后 20 行日志："
  tail -20 "$LOG_DIR/server.log" || true
  exit 1
fi
