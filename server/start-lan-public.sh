#!/usr/bin/env bash
# DeckForge 局域网访问启动器 —— 绑定 0.0.0.0（本机 + 同网段其它设备都能开）
#
# 与 start-lan.sh 的唯一区别：把默认监听地址从 127.0.0.1 改成 0.0.0.0。
# 其余行为完全一致（脱离终端常驻、端口占用检查、健康检查、日志到 data/logs/server.log）。
# 停止仍然是：bash server/stop-daemon.sh（两个脚本共用同一个 pid 文件）。
#
# ⚠️ 平台没有登录鉴权：开放到 0.0.0.0 后，同网段任何人都能改设置（含 API key）、
#    跑生图花你的钱。仅在可信网络（家庭/自己的局域网）使用；公共/公司网络请改用
#    bash server/start-lan.sh（默认只监听本机 127.0.0.1）。
#
# 用法：
#   bash server/start-lan-public.sh              # 0.0.0.0:8641
#   PORT=8640 bash server/start-lan-public.sh    # 换端口
#   bash server/stop-daemon.sh                   # 停止
set -e
cd "$(dirname "$0")/.."

export HOST="0.0.0.0"
export PORT="${PORT:-8641}"

# 尽力打印可用的访问地址：真实局域网 IPv4（排除回环、link-local 与 Docker/虚拟网桥 172.16-31）
ADDRS="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+\.' \
         | grep -vE '^(127|169\.254)\.' | grep -vE '^172\.(1[6-9]|2[0-9]|3[01])\.' \
         | sed "s|^|http://|; s|$|:${PORT}|" | tr '\n' ' ')"
echo "== DeckForge 局域网模式：HOST=${HOST} PORT=${PORT} =="
echo "   本机：http://127.0.0.1:${PORT}"
[ -n "$ADDRS" ] && echo "   局域网：${ADDRS}"
echo "   （其它设备需已放行防火墙入站 TCP ${PORT}；改网络后 IP 可能变化）"

exec bash server/start-lan.sh "$@"
