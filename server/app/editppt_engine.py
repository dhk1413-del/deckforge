"""把外部 skill `image-to-editable-ppt`（⭐2627, MIT）的精细重建能力接入平台。

「图片转可编辑」**只有这一条路**（2026-09-21 起）：内置引擎（`pipeline._editable_worker`
的 vision_absolute 本地渲染）已按要求下线，不再回退。
  · 本模块：分钟级/页 —— 驱动第三方 CLI 的状态机
    （prepare → 逐页 dispatch → page worker（headless Hermes）→ record → finalize），
    产物自带 validation.json（zip/关系/必需文字/资产来源全查）

实测对照（同一页，详见 skill §9.5）：文本框 14→45、文字覆盖 80%→100%、位置中位偏差 0.024→0.010。

设计要点：
  1. 平台只做**编排**，页面重建一律交给 headless Hermes（其契约要求"父代理不得写页面产物"）
  2. 内容真源用我们自己的视觉识别结果写成 `hermes_text_hints.json`（它文档里的 PaddleOCR 提示位）
     —— 文字不得改写，几何/字号按它的墨迹测量归一
  3. 全程只读外部输入，失败如实上报（不伪造成功），失败页保留 run 目录供排查
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import traceback
from typing import Any, Callable, Dict, List, Optional

from . import config, db, providers

DEFAULT_CLI = os.path.expanduser("~/.editppt-venv/bin/editppt")
DEFAULT_SKILL_DIR = os.path.expanduser(
    "~/Documents/skills-repos/image-to-editable-ppt-skill/skills/image-to-editable-ppt")
HERMES_CANDIDATES = [
    os.path.expanduser("~/Library/Application Support/cn.org.hermesagent.desktop/runtime/desktop-bin/hermes"),
    "/usr/local/bin/hermes", "/opt/homebrew/bin/hermes",
]
PAGE_WORKER_TIMEOUT = 1200     # 单页重建上限 20 分钟（实测约 5–13 分钟）
SETUP_TIMEOUT = 180

# 取消令牌：key = 项目 id。用户在界面上点「停止」后，正在跑的 page worker 会被终止，
# run 目录与已完成页全部保留 → 之后可以「断点续跑」。
CANCEL: Dict[str, bool] = {}


def request_cancel(key: str) -> None:
    CANCEL[key] = True


def clear_cancel(key: str) -> None:
    CANCEL.pop(key, None)


def is_cancelled(key: str) -> bool:
    return bool(CANCEL.get(key, False))


def cli_path() -> str:
    return db.setting_get("editppt.cli") or DEFAULT_CLI


def skill_dir() -> str:
    return db.setting_get("editppt.skill_dir") or DEFAULT_SKILL_DIR


def hermes_path() -> str:
    configured = db.setting_get("editppt.hermes")
    if configured:
        return configured
    for cand in HERMES_CANDIDATES:
        if os.path.exists(cand):
            return cand
    return "hermes"


def _env() -> Dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(cli_path()) + os.pathsep + env.get("PATH", "")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def available() -> Dict[str, Any]:
    """引擎是否可用（不联网、不跑模型，只看本机装没装）。"""
    cli, skill = cli_path(), skill_dir()
    hermes = hermes_path()
    info: Dict[str, Any] = dict(engine="editppt", cli=cli, skill_dir=skill, hermes=hermes)
    if not os.path.exists(cli):
        return dict(info, ok=False, reason="未安装 editppt CLI（%s）；安装方式见 skill §9.5" % cli)
    if not os.path.isdir(skill):
        return dict(info, ok=False, reason="未找到 skill 目录（%s）" % skill)
    if not os.path.exists(os.path.join(skill, "SKILL.md")):
        return dict(info, ok=False, reason="skill 目录缺少 SKILL.md（%s）" % skill)
    if not (os.path.exists(hermes) or shutil.which("hermes")):
        return dict(info, ok=False, reason="未找到 hermes CLI（无法派 page worker）")
    return dict(info, ok=True, reason="可用")


def _run(args: List[str], cwd: Optional[str] = None, timeout: int = SETUP_TIMEOUT) -> Dict[str, Any]:
    try:
        proc = subprocess.run([cli_path()] + args, cwd=cwd, env=_env(), timeout=timeout,
                              capture_output=True, text=True)
        return dict(ok=proc.returncode == 0, code=proc.returncode,
                    out=(proc.stdout or "")[-4000:], err=(proc.stderr or "")[-2000:])
    except subprocess.TimeoutExpired:
        return dict(ok=False, code=-1, out="", err="超时（%s 秒）" % timeout)
    except OSError as exc:
        return dict(ok=False, code=-1, out="", err="%s: %s" % (type(exc).__name__, exc))


def build_hints(blocks: List[Dict[str, Any]], ink_lines: List[Dict[str, Any]],
                img_w: int, img_h: int) -> Dict[str, Any]:
    """把「我们的视觉文字」+「它的墨迹几何/字号分组」合成 page worker 可用的提示。

    文字一律来自识别结果（不改写、不补位）；几何优先用墨迹测量，缺失才用归一化坐标换算；
    size_group 取自墨迹测量的分组（同级文字字号应当一致）。
    """
    groups = {}
    for line in ink_lines or []:
        box = line.get("box_px") or []
        if len(box) == 4:
            groups[tuple(round(v) for v in box)] = line.get("size_group")

    def nearest_group(box: List[int]) -> Optional[str]:
        if not groups:
            return None
        cx, cy = box[0] + box[2] / 2.0, box[1] + box[3] / 2.0
        best, best_d = None, 1e18
        for (gx, gy, gw, gh), grp in groups.items():
            dx, dy = cx - (gx + gw / 2.0), cy - (gy + gh / 2.0)
            d = dx * dx + dy * dy
            if d < best_d:
                best, best_d = grp, d
        return best if best_d <= (img_w * 0.06) ** 2 else None      # 距离过远就不硬套

    lines = []
    for b in blocks or []:
        box = [round(b["x"] * img_w), round(b["y"] * img_h), round(b["w"] * img_w), round(b["h"] * img_h)]
        ink_box = _match_ink_box(box, groups)
        lines.append(dict(text=b["text"], role=b.get("role") or "body",
                          box_px=[round(v) for v in ink_box] if ink_box else box,
                          font_pt=b.get("font_size_pt") or 0,
                          size_group=nearest_group(box)))
    return dict(source=dict(width=img_w, height=img_h),
                provider="deckforge-vision（等价于 PaddleOCR-VL 的内容感知提示）",
                note="文字内容必须与本文件一致，不得改写/编造；box_px 为源图像素；"
                     "同级 size_group 的文本请使用同一字号。",
                lines=lines)


def _match_ink_box(box: List[int], groups: Dict[tuple, Any]) -> Optional[List[int]]:
    """给视觉框找最近的一条墨迹测量框（中心距 < 框高的一半才算同一行）。"""
    if not groups:
        return None
    cx, cy = box[0] + box[2] / 2.0, box[1] + box[3] / 2.0
    best, best_d = None, 1e18
    for (gx, gy, gw, gh) in groups:
        dx, dy = cx - (gx + gw / 2.0), cy - (gy + gh / 2.0)
        d = dx * dx + dy * dy
        if d < best_d:
            best, best_d = [gx, gy, gw, gh], d
    return best if best_d <= (max(24, box[3]) * 1.2) ** 2 else None


def _page_dirs(run_dir: str) -> List[str]:
    """页面目录的**绝对路径**，按 page_NNN 排序。

    注意：`os.listdir` 给的是目录名，必须 join 回父目录——只返回名字会让上层拼出相对路径，
    在服务进程里（CWD 与 run 目录无关）直接 FileNotFoundError。2026-09-21 实际踩过。
    """
    pages = os.path.join(run_dir, "pages")
    if not os.path.isdir(pages):
        return []
    return sorted(os.path.join(pages, d) for d in os.listdir(pages) if d.startswith("page_"))


def _page_status(run_dir: str, page_id: str) -> str:
    """读它状态机里某页的状态（page_jobs.json）。读不到就返回空串。"""
    try:
        jobs = json.load(open(os.path.join(run_dir, "page_jobs.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    for page in jobs.get("pages") or []:
        if page.get("page_id") == page_id:
            return str(page.get("status") or "")
    return ""


def _page_recorded(run_dir: str, page_id: str) -> bool:
    """该页是否已通过校验并被 record（断点续跑时跳过它）。"""
    return _page_status(run_dir, page_id) in ("recorded", "accepted", "complete")


def _stored_page_nos(run_dir: str) -> List[int]:
    """读现场记录的页清单（prepare 时写入）。读不到就返回空列表。"""
    if not run_dir:
        return []
    try:
        data = json.load(open(os.path.join(run_dir, "deckforge_pages.json"), encoding="utf-8"))
        return [int(x) for x in data] if isinstance(data, list) else []
    except (OSError, ValueError, TypeError):
        return []


def run_status(project_id: str) -> Dict[str, Any]:
    """高精度转换的现场状态（给界面看）：已记录/总页数、每页状态、是否可续跑。"""
    run = _latest_incomplete_run(project_id) or _latest_run(project_id)
    if not run:
        return dict(has_run=False, resumable=False, recorded=0, total=0, pages=[], page_nos=[],
                    note="还没有高精度转换记录")
    pages: List[Dict[str, Any]] = []
    try:
        jobs = json.load(open(os.path.join(run, "page_jobs.json"), encoding="utf-8"))
        for p in jobs.get("pages") or []:
            pages.append(dict(page_id=p.get("page_id"), status=p.get("status")))
    except (OSError, ValueError):
        pass
    done = [p for p in pages if p["status"] in ("recorded", "accepted", "complete")]
    return dict(has_run=True, run_dir=run, run_name=os.path.basename(run), pages=pages,
                page_nos=_stored_page_nos(run), recorded=len(done), total=len(pages),
                resumable=0 < len(done) < len(pages), cancelled=is_cancelled(project_id),
                note="可继续上次进度（已完成 %d/%d 页）" % (len(done), len(pages)) if 0 < len(done) < len(pages)
                     else ("已全部完成，可重新转换以组装 deck" if pages and len(done) == len(pages) else ""))


def _latest_run(project_id: str) -> str:
    """该项目最近一次的 run 目录（不分是否完成）。"""
    root = os.path.join(config.FILES_DIR, "editppt")
    if not os.path.isdir(root):
        return ""
    candidates = sorted(d for d in os.listdir(root) if d.startswith(project_id + "-"))
    if not candidates:
        return ""
    base = os.path.join(root, candidates[-1])
    return _latest_run_dir(base) or base


def _latest_incomplete_run(project_id: str) -> str:
    """找该项目最近一次「未全部完成」的 run 目录（供断点续跑）。

    run 目录名形如 `p_xxx-20260921-021115`，其下还有 prepare 自建的一层；取最新一层。
    """
    root = os.path.join(config.FILES_DIR, "editppt")
    if not os.path.isdir(root):
        return ""
    candidates = sorted(d for d in os.listdir(root) if d.startswith(project_id + "-"))
    for name in reversed(candidates):
        base = os.path.join(root, name)
        run = _latest_run_dir(base) or base
        jobs_path = os.path.join(run, "page_jobs.json")
        if not os.path.exists(jobs_path):
            continue
        try:
            jobs = json.load(open(jobs_path, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        done = [p for p in jobs.get("pages") or [] if p.get("status") in ("recorded", "accepted", "complete")]
        total = len(jobs.get("pages") or [])
        if 0 < len(done) < total:                              # 有已完成页、但没全完成 → 可续跑
            return run
    return ""


def _log_page_error(page_dir: str, stage: str, exc: BaseException) -> None:
    """把逐页失败写进现场（生产上排查靠它，别只留一句人话）。"""
    try:
        with open(os.path.join(page_dir, "engine_error_%s.log" % stage), "w", encoding="utf-8") as fh:
            fh.write("%s: %s\n\n" % (type(exc).__name__, exc))
            traceback.print_exc(file=fh)
    except OSError:
        pass


def _validation_passed(page_dir: str, retries: int = 3, wait: float = 4.0) -> Dict[str, Any]:
    """读 validation.json 判断该页是否通过校验 —— **必须带重试**。

    2026-09-21 实测踩到：page worker 是 agent，它可能在退出前后仍在写这个文件；平台在
    worker 进程刚退出的那一瞬读到的还是旧的 `passed=false`，据此把整单判 failed
    （真实现场：几秒后文件已变成 `passed=true`，但作业已经报「N/M 页未通过校验」）。
    所以一次读到的结果不能定生死：未通过就等几秒再读，最多 retries 次。
    """
    last: Dict[str, Any] = dict(passed=False, reason="未生成 validation.json")
    for attempt in range(max(1, retries)):
        path = os.path.join(page_dir, "validation.json")
        if os.path.exists(path):
            try:
                data = json.load(open(path, encoding="utf-8"))
                if isinstance(data, dict):
                    last = data
                    if data.get("passed"):
                        return data
                else:
                    last = dict(passed=False, reason="validation.json 结构异常")
            except (OSError, ValueError) as exc:
                last = dict(passed=False, reason="validation.json 读取失败：%s" % exc)
        if attempt < retries - 1:
            time.sleep(wait)
    return last


def _worker_prompt(run_dir: str, page_id: str, page_dir: str) -> str:
    return (
        "你正在执行 image-to-editable-ppt skill 的 **page worker（单页重建）** 任务，请严格按该 skill 执行。\n\n"
        "1. 页面工作指令（必读）：%s/worker-prompt.md\n"
        "2. 权威契约与参考：%s/references/manifest-schema.md、page-decision-tree.md、cli-helper.md\n"
        "3. 内容真源（重要）：%s/hermes_text_hints.json —— **文字内容必须与它完全一致，不得改写、不得编造、"
        "不得增删文字**；几何参考其中的 box_px，字号参考 font_pt，同级 size_group 必须用同一字号。\n"
        "4. 交付物：%s/manifest.json，然后用 `editppt page build %s` 生成 page.pptx 与 preview.png，"
        "并让 `editppt page validate %s` 通过。**不要执行 run record / run finalize**（平台负责）。\n"
        "5. 完成后用中文简述：validate 结果、text_boxes 与 shapes 数量、遇到的问题与取舍。\n"
        % (page_dir, skill_dir(), page_dir, page_dir, page_dir, page_dir))


def _run_page_worker(page_dir: str, page_id: str, cancel_key: str = "") -> Dict[str, Any]:
    """派一个 headless Hermes 当 page worker 重建这一页。

    用 Popen + 轮询（而不是 `subprocess.run`）是为了能**中途取消**：用户点「停止」后
    最多 1 秒内终止子进程，现场（已完成页 + 该页状态）全部保留，便于断点续跑。
    """
    prompt = _worker_prompt(os.path.dirname(os.path.dirname(page_dir)), page_id, page_dir)
    cmd = [hermes_path(), "-z", prompt, "--skills", "image-to-editable-ppt", "--yolo"]
    started = time.time()
    try:
        proc = subprocess.Popen(cmd, env=_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except OSError as exc:
        return dict(ok=False, tail="%s: %s" % (type(exc).__name__, exc))
    try:
        while proc.poll() is None:
            if cancel_key and is_cancelled(cancel_key):
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return dict(ok=False, cancelled=True, tail="已按用户要求停止（现场保留，可继续）")
            if time.time() - started > PAGE_WORKER_TIMEOUT:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return dict(ok=False, tail="page worker 超时（%d 秒）" % PAGE_WORKER_TIMEOUT)
            time.sleep(1)
        out = proc.stdout.read() if proc.stdout else ""
        return dict(ok=proc.returncode == 0, tail=(out or "")[-1500:])
    finally:
        if proc.poll() is None:
            proc.kill()


def convert(project_id: str, page_nos: List[int],
            on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
            resume: bool = False, resume_run_dir: str = "", cancel_key: str = "",
            source_rows: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """把项目的指定页（必须是已渲染出页面图的页）用第三方引擎转成可编辑 deck。

    返回 dict(ok, deck, run_dir, pages, failures, note)。**同步阻塞**，调用方负责放到线程里。
    """
    def notify(**kw) -> None:
        if on_event:
            try:
                on_event(kw)
            except Exception:                                  # noqa: BLE001 —— 进度回调不能影响主流程
                pass

    state = available()
    if not state.get("ok"):
        return dict(ok=False, error=state.get("reason"), run_dir="")

    # 续跑时**以现场记录的页清单为准**：run 里的 page_001..N 是按 prepare 时的顺序映射的，
    # 若调用方这次勾选的页不同，index 对不上就会张冠李戴。
    stored = _stored_page_nos(resume_run_dir or _latest_incomplete_run(project_id)) if (
        resume or resume_run_dir) else []
    if stored:
        page_nos = stored

    rows = [dict(r) for r in db.q(
        "SELECT * FROM slides WHERE project_id=? AND page_no IN (%s) ORDER BY page_no"
        % ",".join("?" * len(page_nos)), (project_id, *page_nos))] if page_nos else []
    if source_rows is not None and not resume:
        rows = [dict(r) for r in source_rows]
    if not rows:
        return dict(ok=False, error="没有找到要转换的页面", run_dir="")

    resume_dir = resume_run_dir or (_latest_incomplete_run(project_id) if resume else '')
    manifest = os.path.join(resume_dir, 'deckforge_snapshot.json')
    if resume_dir:
        if os.path.isfile(manifest):
            with open(manifest, encoding='utf-8') as source:
                rows = json.load(source)
    elif all(row.get('current_version_id') and row.get('id') for row in rows):
        frozen_dir = os.path.join(config.FILES_DIR, 'editppt', db.uid('input'))
        os.makedirs(frozen_dir, exist_ok=False)
        for row in rows:
            if not row.get('current_version_id'):
                return dict(ok=False, error='当前页没有版本记录，无法绑定转换', run_dir='')
            row['export_version_number'] = next((i for i, v in enumerate(db.q(
                'SELECT id FROM slide_versions WHERE slide_id=? ORDER BY rowid', (row['id'],)), 1)
                if v['id'] == row['current_version_id']), None)
            path = row.get('image_path') or ''
            if not os.path.isfile(path):
                return dict(ok=False, error='转换输入图片缺失', run_dir='')
            dest = os.path.join(frozen_dir, str(row['page_no']) + os.path.splitext(path)[1])
            shutil.copyfile(path, dest)
            row['image_path'] = dest

    images: List[str] = []
    for r in rows:
        path = r.get("image_path") or ""
        if not path or not os.path.exists(path):
            return dict(ok=False, run_dir="", error="第 %s 页没有页面图，先「图片转可编辑」导入或先生成图片版"
                        % r.get("page_no"))
        images.append(path)

    run_root = os.path.join(config.FILES_DIR, "editppt")
    os.makedirs(run_root, exist_ok=True)
    resume_dir = resume_run_dir or (_latest_incomplete_run(project_id) if resume else "")
    if resume_dir and os.path.isdir(resume_dir):
        run_dir = resume_dir                                   # 断点续跑：复用现场，不重新 prepare
        notify(stage="resume", message="继续上次未完成的转换：%s" % os.path.basename(run_dir), done=0,
               total=len(rows))
    else:
        run_dir = os.path.join(run_root, "%s-%s" % (project_id, db.uid("run")))
        notify(stage="prepare", message="准备转换任务（%d 页）" % len(images), done=0, total=len(rows))
        prep = _run(["prepare"] + images + ["--out-root", run_dir], timeout=SETUP_TIMEOUT + 120 * len(images))
        if not prep["ok"]:
            return dict(ok=False, run_dir=run_dir, error="prepare 失败：%s" % (prep["err"] or prep["out"])[-400:])
        run_dir = _latest_run_dir(run_dir) or run_dir
        try:                                                   # 记下这次转的是哪些页（续跑要按同一顺序映射）
            json.dump(list(page_nos), open(os.path.join(run_dir, "deckforge_pages.json"), "w"))
        except OSError:
            pass
    if not resume_dir and all(row.get('current_version_id') and row.get('id') for row in rows):
        with open(os.path.join(run_dir, 'deckforge_snapshot.json'), 'w', encoding='utf-8') as target:
            json.dump(rows, target, ensure_ascii=False)
    dirs = _page_dirs(run_dir)
    if not dirs:
        return dict(ok=False, run_dir=run_dir, error="prepare 没有生成任何页面目录")

    failures: List[Dict[str, Any]] = []
    recorded: List[int] = []
    cancelled = False
    for idx, page_dir in enumerate(dirs):
        page_id = os.path.basename(page_dir)
        page_no = rows[idx]["page_no"] if idx < len(rows) else None
        if _page_recorded(run_dir, page_id):
            recorded.append(page_no)
            notify(stage="page_done", page=page_no, message="第 %s 页上次已完成，跳过" % page_no,
                   done=idx + 1, total=len(dirs))
            continue
        if cancel_key and is_cancelled(cancel_key):             # 每页开始前检查一次取消
            cancelled = True
            break
        # 上次可能停在 dispatched（被取消或中断）→ 先 reset 才能重新派发（它状态机的要求）
        if _page_status(run_dir, page_id) == "dispatched":
            _run(["run", "reset", run_dir, "--page", page_id, "--confirm-lost"])
        notify(stage="page", page=page_no, message="正在重建第 %s 页（%d/%d）" % (page_no, idx + 1, len(dirs)),
               done=idx, total=len(dirs))
        try:
            _prepare_page(run_dir, page_dir, rows[idx], notify)
        except Exception as exc:                                # noqa: BLE001
            _log_page_error(page_dir, "hints", exc)
            failures.append(dict(page_no=page_no, stage="hints", error="%s: %s" % (type(exc).__name__, exc)))
            continue

        worker = _run(["run", "dispatch", run_dir, "--page", page_id,
                       "--agent-id", "deckforge-%d" % (idx + 1),
                       "--prompt-file", os.path.join(page_dir, "worker-prompt.md")])
        if not worker["ok"]:
            failures.append(dict(page_no=page_no, stage="dispatch", error=(worker["err"] or worker["out"])[-300:]))
            continue

        agent = _run_page_worker(page_dir, page_id, cancel_key or "")
        if agent.get("cancelled"):
            cancelled = True
            failures.append(dict(page_no=page_no, stage="cancelled", error="已停止（现场保留，可继续）"))
            break
        agent_tail = agent.get("tail", "")
        check = _validation_passed(page_dir)
        if not check.get("passed"):
            failures.append(dict(page_no=page_no, stage="rebuild",
                                 error=str(check.get("reason") or check.get("errors") or "校验未通过")[:300]))
            continue

        rec = _run(["run", "record", run_dir, "--page", page_id, "--agent-id", "deckforge-%d" % (idx + 1)])
        if not rec["ok"]:                                   # worker 刚退出、页面产物还在落盘时重试一次
            time.sleep(5)
            rec = _run(["run", "record", run_dir, "--page", page_id, "--agent-id", "deckforge-%d" % (idx + 1)])
        if not rec["ok"]:
            failures.append(dict(page_no=page_no, stage="record", error=(rec["err"] or rec["out"])[-300:]))
            continue
        recorded.append(page_no)
        notify(stage="page_done", page=page_no, message="第 %s 页已重建并通过校验" % page_no,
               done=idx + 1, total=len(dirs))
        db.log_usage(project_id, page_no, "editable_hi", "editppt-skill", "manifest+build", "-", 0.0,
                     0, True, "第三方 skill 高精度重建（agent 逐页写 manifest）%s" % agent_tail[:80].replace("\n", " "))

    # 失败/取消**不再一票否决**：已完成并记录的页保住，如实报出剩余页，可继续（断点续跑）
    if cancelled:                                              # 用户主动停止：保留现场，不当失败处理
        return dict(ok=False, cancelled=True, run_dir=run_dir, pages=[r["page_no"] for r in rows],
                    recorded=recorded, failures=failures, partial=True,
                    error="已停止：已完成 %d/%d 页（现场保留，可点「继续转换」接着跑）" % (len(recorded), len(dirs)))
    if len(recorded) < len(dirs):
        return dict(ok=False, partial=True, run_dir=run_dir, pages=[r["page_no"] for r in rows],
                    recorded=recorded, failures=failures,
                    error="%d/%d 页未通过校验（已完成 %d 页已保留现场，可点「继续转换」重试剩余页）：%s"
                          % (len(dirs) - len(recorded), len(dirs), len(recorded), run_dir))
    if is_cancelled(cancel_key) if cancel_key else False:       # 全部记录的临界点被取消
        return dict(ok=False, cancelled=True, run_dir=run_dir, recorded=recorded, failures=failures, partial=True,
                    error="已停止（所有页已完成，可直接重新转换以组装 deck）")

    notify(stage="finalize", message="组装最终 deck", done=len(dirs), total=len(dirs))
    fin = _run(["run", "finalize", run_dir], timeout=SETUP_TIMEOUT)
    if not fin["ok"]:
        return dict(ok=False, run_dir=run_dir, failures=[dict(stage="finalize", error=fin["err"][-300:])],
                    error="finalize 失败：%s" % (fin["err"] or fin["out"])[-300:])
    decks = [os.path.join(run_dir, "final", f) for f in sorted(os.listdir(os.path.join(run_dir, "final")))
             if f.endswith(".pptx")]
    if not decks:
        return dict(ok=False, run_dir=run_dir, error="finalize 未产出 pptx")
    # 产物**发布到 exports/**，而不是留在 run 工作目录里：
    # 否则 run 目录永远不能清理（导出会指向工作目录），这是实际踩到的设计问题。
    published = _publish_deck(decks[-1])
    return dict(ok=True, deck=published, run_dir=run_dir, source_deck=decks[-1],
                pages=[r["page_no"] for r in rows], failures=[])


def _publish_deck(deck: str) -> str:
    """把最终 deck 复制到 exports/ 并返回新路径（复制失败则退回原路径，不假装成功）。"""
    try:
        out_dir = os.path.join(config.FILES_DIR, "exports")
        os.makedirs(out_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(deck))[0]
        name = "%s_editppt_%s.pptx" % (re.sub(r"[^\w\u4e00-\u9fff-]", "_", stem),
                                       db.uid("e"))
        dest = os.path.join(out_dir, name)
        shutil.copyfile(deck, dest)
        return dest
    except OSError:
        return deck


def _latest_run_dir(parent: str) -> Optional[str]:
    """`prepare --out-root X` 会在 X 下再建一层 run 目录，这里取最新的一层（没有就返回 X）。"""
    if not os.path.isdir(parent):
        return None
    subs = [os.path.join(parent, d) for d in os.listdir(parent) if os.path.isdir(os.path.join(parent, d))]
    return sorted(subs)[-1] if subs else parent


def _prepare_page(run_dir: str, page_dir: str, row: Dict[str, Any],
                  notify: Callable[..., None]) -> None:
    """生成 worker prompt、墨迹测量、以及内容真源 hints（缺一不可）。"""
    prompt_script = os.path.join(skill_dir(), "scripts", "build-page-worker-prompt.py")
    subprocess.run([os.path.join(os.path.dirname(cli_path()), "python3"),
                    prompt_script, run_dir, "--page", os.path.basename(page_dir),
                    "--out", os.path.join(page_dir, "worker-prompt.md")],
                   env=_env(), check=True, capture_output=True, text=True, timeout=120)
    _run(["page", "hints", page_dir])                            # 它的墨迹测量（几何 + size_group）

    img = row.get("image_path") or ""
    scene = json.loads(row.get("native_scene_json") or "{}") if row.get("native_scene_json") else {}
    vision = (scene.get("vision") or {})
    blocks = scene.get("blocks") or []
    if not blocks or not vision:
        res = providers.analyze_slide_with_qwen(img)
        if not res.get("ok"):
            raise RuntimeError("视觉识别失败，无法提供文字真源：%s" % str(res.get("message"))[:120])
        from .pipeline import blocks_from_vision
        blocks = blocks_from_vision(res["scene"], int(row.get("width") or 0), int(row.get("height") or 0))
    if not blocks:
        raise RuntimeError("视觉识别没有返回任何文字块")
    ink = []
    hints_path = os.path.join(page_dir, "text_hints.json")
    if os.path.exists(hints_path):
        ink = (json.load(open(hints_path, encoding="utf-8")).get("lines") or [])
    payload = build_hints(blocks, ink, int(row.get("width") or 1600), int(row.get("height") or 900))
    json.dump(payload, open(os.path.join(page_dir, "hermes_text_hints.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    notify(stage="hints", message="第 %s 页提示已就绪（%d 条文字）" % (row.get("page_no"), len(blocks)))
