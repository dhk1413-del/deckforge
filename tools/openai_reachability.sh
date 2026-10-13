#!/usr/bin/env bash
# openai_reachability.sh —— OpenAI 官方 API 可达性探测（换节点后复跑此脚本即可）
# 用法: bash tools/openai_reachability.sh            # 直连 + 本机 Clash 代理各测一轮
#       PROXY=http://127.0.0.1:7897 bash tools/openai_reachability.sh
set -u
PROXY="${PROXY:-http://127.0.0.1:7897}"
HOSTS=("api.openai.com" "platform.openai.com")
PATHS=("/v1/models" "/v1/images/generations")

line() { printf '%.0s─' $(seq 1 74); echo; }

echo "探测时间: $(date '+%F %T %Z')"
echo "代理地址: $PROXY"
line

# 0) 代理端口是否活着
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 --noproxy '*' "http://127.0.0.1:7897" 2>/dev/null)
echo "[0] 本机代理端口 7897 : ${code:-000}  $([ "$code" = "000" ] && echo '← 未开启（Clash 没跑）' || echo '← 活着')"
line

# 1) 出口 IP / 地区（判断节点在哪个国家，OpenAI 不支持的地区会被拒）
echo "[1] 出口 IP 与地区"
for m in "direct" "proxy"; do
  if [ "$m" = "proxy" ]; then P="--proxy $PROXY"; else P="--noproxy *"; fi
  out=$(curl -s --max-time 12 $P "https://ipinfo.io/json" 2>/dev/null)
  ip=$(echo "$out"    | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('ip','?'),d.get('country','?'),d.get('city','?'),d.get('org','?')[:40])" 2>/dev/null)
  echo "    $m : ${ip:-（失败/超时）}"
done
line

# 2) 各家主机：直连 vs 代理，分别看 DNS / TCP / TLS / HTTP
echo "[2] 主机可达性（期望：直连=000，代理=401 正确；403/000=被拦）"
for h in "${HOSTS[@]}"; do
  d=$(curl -s -o /dev/null -w '%{http_code} dns=%{time_namelookup}s tls=%{time_appconnect}s total=%{time_total}s' --max-time 12 --noproxy '*' "https://$h/v1/models" 2>/dev/null)
  p=$(curl -s -o /dev/null -w '%{http_code} tls=%{time_appconnect}s total=%{time_total}s' --max-time 15 --proxy "$PROXY" "https://$h/v1/models" 2>/dev/null)
  echo "    $h"
  echo "        直连 : ${d:-000}"
  echo "        代理 : ${p:-000}"
done
line

# 3) 真正打图像端点（用假 key，401=通了且要鉴权；403=被风控/地区限制；404=路径不对）
echo "[3] 图像端点探测（假 key，期望 401）"
for u in "https://api.openai.com/v1/images/generations"; do
  body=$(curl -s --max-time 20 --proxy "$PROXY" -w '\n[[HTTP %{http_code}]]' \
        -H 'Content-Type: application/json' -H 'Authorization: Bearer sk-DUMMY-TEST' \
        -d '{"model":"gpt-image-1","prompt":"ping","size":"1024x1024"}' "$u" 2>/dev/null)
  echo "    $u"
  echo "$body" | head -c 400 | sed 's/^/        /'
done
line
echo "判读：代理下 api.openai.com/v1/models 返回 401 → 网络已通（只差真 key）；"
echo "      403/1020 → 节点 IP 被 Cloudflare 风控；000/timeout → 节点不通或被墙。"
echo "      再确认 ipinfo 的 country 不在 OpenAI 受限地区（CN/HK 等会被拒）。"
