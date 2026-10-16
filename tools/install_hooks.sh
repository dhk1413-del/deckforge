#!/usr/bin/env bash
# 启用仓库自带的 git 钩子（密钥门禁）。每个克隆执行一次即可。
# 为什么需要这一步：`.git/hooks` 不进版本库，所以钩子放在 `.githooks/`，
# 用 core.hooksPath 指过去（该配置只写本机 .git/config，不污染仓库内容）。
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit .githooks/pre-push 2>/dev/null || true
echo "已启用密钥门禁：core.hooksPath=$(git config core.hooksPath)"
echo "  pre-commit → tools/check_no_secrets.py --staged   （提交前拦）"
echo "  pre-push   → tools/check_no_secrets.py --range    （上传 GitHub 前拦）"
