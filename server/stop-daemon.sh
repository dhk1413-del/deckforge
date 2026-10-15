#!/usr/bin/env bash
# 停掉 SlideCraft 守护进程（start-lan.sh 新 session 启动的 uvicorn PID）
set -e
cd "$(dirname "$0")/.."
LOG_DIR="$(pwd)/data/logs"
PID_FILE="$LOG_DIR/deckforge.pid"
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  PID="$(cat "$PID_FILE")"
  kill "$PID"
  # 等待 uvicorn 真正退出再返回；否则紧接着 start-lan.sh 可能把仍能响应健康检查的旧进程误认成新服务。
  for _ in $(seq 1 40); do
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.25
  done
  if kill -0 "$PID" 2>/dev/null; then
    # 正在收尾的生成作业会拖住 uvicorn 关闭（实测：TERM 后 10 秒仍未退）。
    # 这里升级为 SIGKILL，否则 start-lan.sh 会把旧进程误认成新服务。
    echo "pid $PID 10 秒未退出（可能在收尾作业），升级 SIGKILL" >&2
    kill -9 "$PID" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$PID" 2>/dev/null || break
      sleep 0.25
    done
  fi
  if kill -0 "$PID" 2>/dev/null; then
    echo "未能停止 pid $PID（连 SIGKILL 都没用，请手动检查）" >&2
    exit 1
  fi
  echo "已停止 pid $PID"
else
  pkill -f "uvicorn app.main:app" && echo "已停止（按进程名匹配）" || echo "没有在跑的服务"
fi
rm -f "$PID_FILE"
