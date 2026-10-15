# SlideCraft 工作台 —— 仓库约定（coding agent 一律按这份来）

## 是什么

自托管「输入内容 → 一整套风格统一 PPT」的工作台。后端 FastAPI + SQLite(WAL)；前端 React 19 + TS + Tailwind v4（构建产物由后端托管）。
导出两类 PPTX：**图片版**（整页图铺底）与**原生可编辑版**（文本/形状/图表都是 PowerPoint 原生对象，PptxGenJS 生成）。

## 目录

| 路径 | 内容 |
|---|---|
| `server/app/` | `paths` `config` `db` `stylepacks` `providers` `render` `export_pptx` `pipeline` `main` |
| `server/pptx/render_native.mjs` | 原生可编辑 PPTX 渲染器（**唯一排版真源**） |
| `web/src/` | `pages/`（Wizard/Styles/Projects/Usage/Settings）、`components/`（`ProjectWorkbench` 等）、`hooks/`、`api.ts`、`types.ts` |
| `style-packs/` | 风格包（`styles/<名>/{style.md,prompt.md}`）与版式（`layouts/*.md`） |
| `ui-design/` | 设计令牌：**浅色为主**，底 `#F5F6FC`、白卡、主色 `#1E78FA` |
| `tools/` | `e2e_mvp.py`（零 key 端到端 34 项）、`test_native_render.py`、`test_vision_parse.py` |
| `docs/API.md` | 前后端接口契约（**改接口必须同步此文件**） |
| `config/providers.yaml` | 生图/文本/网络配置模板（key 由用户在设置页填，存 DB，不进仓库） |

## 铁律

1. **内容归 LLM、格式归代码**：渲染器与前端**不得写死业务文案**。任何文字与数值都必须来自该页真源（`title`/`outline`/`points`/`vision`）；取不到就少画一个元素，**不许编造**（含「项目 1/2/3」这类占位标签）。
2. **不伪造数据**：图表只画「视觉识别结果」或「要点原文里的同单位数值」；无可用数据时不画图表，并在页面上标注数据来源。
3. **零 key 可跑**：没有任何 API key 时，全流程走 `local_render` 本地兜底（成本 0），这条底线不能破。
4. 中文界面；数字用等宽 `num` 类；配色走 `ui-design/` 令牌（浅色为主）。
5. **不改** `web/dist/`（由 `npm run build` 生成）；**不提交密钥**。提交前必须跑门禁并做对应验证；
   本仓库当前流程是「验收通过后由负责 agent 提交，需要时推送到 GitHub」（推送前确认远端与提交内容，别把 `data/`、`web/dist/` 带进去）。

## 自检命令（每次改完都要跑，并把真实输出贴出来）

```bash
make verify        # 规范验收：7 套离线回归 + 前端构建 + 线上只读冒烟（一条命令，本仓无 pytest/CI）
make verify-fast   # 同上但跳过网络冒烟（不写库、不调模型、不花钱）
make lint          # 后端字节码编译 + 前端 tsc（改完随手跑）

# 需要单独跑某一套时：
#   .venv/bin/python tools/test_reskin_rebuild.py   # 换皮 B 口径（原文抽取/容量核算/重排）
#   .venv/bin/python tools/test_native_render.py    # 渲染器不得伪造内容与数据
#   .venv/bin/python tools/e2e_mvp.py               # 端到端（要求「零 key 状态」；已填 key 时口径不成立）
#     建议在隔离实例上跑（不碰正式库）：先 `DECKFORGE_DATA=/tmp/df-e2e PORT=8660 bash server/start-lan.sh`，
#     再 `DECKFORGE_DATA=/tmp/df-e2e DF_BASE=http://127.0.0.1:8660 .venv/bin/python tools/e2e_mvp.py`
#     覆盖：上传 → 梳理 → 页面确认 → **内容确认** → 生成(SSE) → **逐页核对** → 导出 → 账本（后两步是导出的硬前置）
```

## 环境

- 风格预览图：`style-packs/styles/<id>/previews/` 里放的就是各风格的真实样例页（随仓库公开）。
  若某台机器想用另一套图（例如不想公开的自制预览），放到同级的 `previews-local/`（已被 `.gitignore` 排除），服务端会**优先**用它：
  ```bash
  style_id=tech-deepblue
  mkdir -p "style-packs/styles/$style_id/previews-local/"
  cp /path/to/your/previews/* "style-packs/styles/$style_id/previews-local/"
  ```
- 服务常驻：bash server/start-lan.sh（:8641，脱离终端）；停：bash server/stop-daemon.sh
- **重启的正确姿势（踩过坑，务必照做）**：改完后端代码后，用
  `bash server/stop-daemon.sh && bash server/start-lan.sh`；
  **绝对不要**在 exec/终端会话里前台起服务（`bash server/run.sh` 直接跑）——实测会话结束时进程会被一起带走，
  用户的网页随即打不开（ERR_CONNECTION_REFUSED）。重启后用
  `ps -o pid,ppid -p $(cat data/logs/deckforge.pid)` 确认 **PPID=1**，并
  `curl -s --noproxy '*' http://127.0.0.1:8641/api/health` 确认 `ok=true`。
- **看门狗（服务掉了自动拉起）**：`server/watchdog.sh` 每 60s 探活，健康检查非 200 就用**当前 HOST/PORT**（默认 127.0.0.1:8641）重新拉起；日志 `data/logs/watchdog.log`。
  启动（macOS 没有 `setsid`，用新会话 spawn，别用 `nohup ... &`，会话结束会被带走）：
  ```bash
  python3 - <<'PY'
  import os, subprocess
  subprocess.Popen(["bash", "server/watchdog.sh"], cwd=os.getcwd(), stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
  PY
  # 停：pkill -f 'server/watchdog.sh'
  ```
  实测：手动 `stop-daemon.sh` 后 30 秒内被自动拉起。
- **改代码的分工**：由当前 agent **直接改**（用户 2026-10-14 明确：不必再委派 Codex CLI）。
  改动前先读相关文件与契约，改完必须跑 `make lint` / `make verify-fast`，涉及界面还要实机验证（截图或 DOM 断言）再交付。
  （历史背景：Codex CLI 在 `~/.npm-global/bin/codex`，非交互用法需要 `--sandbox workspace-write`；
  但当前流程不再依赖它，仅当用户临时要求时才用。）
- **首次自检前先装依赖**：干净检出上直接跑 `make verify` 会因缺 `.venv` 与 `server/pptx/node_modules`
  出现失败。先执行一次 `bash server/start-lan.sh`（它经 `server/run.sh` 装 Python 依赖与 PptxGenJS），
  再跑自检；`tools/verify_all.py` 已会在缺依赖时打印这条提示。
- 代理：**7897 已失效**，当前可用的是 `http://127.0.0.1:65532`（GitHub 推送走它）；
  GitHub 直连时通时断，推送一律带 `-c http.proxy=http://127.0.0.1:65532`。
- GitHub 推送凭据存在 macOS 钥匙串：`security find-generic-password -a dhk1413-del -s deckforge-github-token -w`
  （token 不落明文；撤销走 GitHub Settings → Applications）。
- `web/node_modules` 已存在，构建**不需要联网**
