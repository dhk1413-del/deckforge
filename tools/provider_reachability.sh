#!/usr/bin/env bash
# provider_reachability.sh —— 生图/文本 provider 可达性 + 代理模式一体探测
# 用法: bash tools/provider_reachability.sh [HTTP_PROXY]      默认 http://127.0.0.1:7897
# 判读要点：
#   · TUN 模式（nano 等）→ 直连即通，应用层**必须清空 HTTP_PROXY**（否则请求反而失败）
#   · HTTP 代理模式（Clash 7897）→ 需要 --proxy；国内 API 必须 --noproxy 绕过
set -u
PROXY="${1:-http://127.0.0.1:7897}"
line() { printf '%.0s─' $(seq 1 78); echo; }
verdict() {
  case "$1" in
    000) echo "❌ 不通" ;; 401|400|403) echo "✅ 已连通（仅缺 key/参数）" ;; 200) echo "✅ 完全通" ;; *) echo "⚠️ $1" ;;
  esac
}
probe() {
  local d=$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 --noproxy '*' "$2" 2>/dev/null)
  local p=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 --proxy "$PROXY" "$2" 2>/dev/null)
  printf '  %-30s 直连=%-4s 代理=%-4s %s\n' "$1" "${d:-000}" "${p:-000}" "$(verdict "${p:-000}")"
}

echo "探测时间: $(date '+%F %T')   注入的 HTTP 代理: $PROXY"
line
echo "【0】代理模式诊断（决定应用层该怎么配）"
PY=$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 --noproxy '*' "http://127.0.0.1:7897" 2>/dev/null)
echo "  Clash 端口 7897          : ${PY:-000} $([ "${PY:-000}" = 000 ] && echo '(未启动)' || echo '(活着 → HTTP 代理模式可用)')"
TUN=$(ifconfig 2>/dev/null | grep -A2 "^utun" | grep -c "inet 0.0.1.1")
DEF=$(netstat -rn -f inet 2>/dev/null | awk '$1=="default"{print $2" via "$NF; exit}')
DEFIF=$(netstat -rn -f inet 2>/dev/null | awk '$1=="default"{print $NF; exit}')
EGRESS=$(curl -s --max-time 10 --noproxy '*' https://ipinfo.io/json 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('ip'),d.get('country'),d.get('city'),(d.get('org') or '')[:32])" 2>/dev/null)
echo "  TUN 网卡(0.0.1.1)        : $([ "$TUN" -gt 0 ] && echo "有 $TUN 个" || echo '无')"
echo "  默认路由                 : ${DEF:-?}  (接口 $DEFIF)"
echo "  直连出口 IP              : ${EGRESS:-失败}"
case "$DEFIF" in
  utun*) echo "  → 判定: **TUN 模式生效**（默认路由在 utun）→ 应用层请清空 HTTP_PROXY/HTTPS_PROXY" ;;
  *)     echo "  → 判定: **TUN 未接管**（默认路由在 $DEFIF）→ 需在代理 App 里连接/开启 TUN；或改用 HTTP 代理模式" ;;
esac
line
echo "【1】境外模型（需字节出境）"
probe "OpenAI api（gpt-image）"  "https://api.openai.com/v1/models"
probe "OpenAI images 端点"      "https://api.openai.com/v1/images/generations"
probe "Gemini/GenAI api"        "https://generativelanguage.googleapis.com/v1beta/models"
probe "Google 主域"             "https://www.google.com/generate_204"
line
echo "【2】国内模型（应直连可达；调用时须绕过代理）"
probe "阿里百炼 Qwen-Image"      "https://dashscope.aliyuncs.com/api/v1/models"
probe "DeepSeek"                "https://api.deepseek.com/models"
line
echo "【3】OpenAI 图像端点实打（假 key，期望 401）"
curl -s --max-time 25 --proxy "$PROXY" -w '\n[[HTTP %{http_code}]]\n' \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer sk-DUMMY-TEST' \
  -d '{"model":"gpt-image-2","prompt":"ping","size":"1024x1024"}' \
  "https://api.openai.com/v1/images/generations" 2>/dev/null | head -c 320
line
