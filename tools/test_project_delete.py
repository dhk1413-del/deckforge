# -*- coding: utf-8 -*-
"""删除项目回归（离线、零成本、不联网、不写生产库）。

覆盖：
  D1 不存在 → 404
  D2 有任务在跑（jobs.status=queued/running/cancelling）→ 409，且什么都不动
  D3 原稿缩略图后台构建中 → 409（否则删除后会被构建线程重建出孤儿目录）
  D4 正常删除：DB 记录（projects/slides/slide_versions/jobs/exports/operation_*）清空
  D5 磁盘清理：项目目录、导出件与其快照目录、精细重建现场（含冻结输入 input_*）
  D6 用量账本保留：删项目不抹账，ledger 项目名回退「已删除项目」
  D7 越界保护：DB 里指向 data/files 之外的路径绝不跟着删
  D8 路由已注册：DELETE /api/projects/{pid}

用法：.venv/bin/python tools/test_project_delete.py
"""
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SANDBOX = tempfile.mkdtemp(prefix="deckforge-project-delete-")
os.environ["DECKFORGE_DATA"] = SANDBOX                     # 必须在导入 server.app 之前
sys.path.insert(0, ROOT)

from fastapi import HTTPException                                       # noqa: E402
from server.app import config, db, operations, pipeline, source_pages   # noqa: E402
from server.app import main as app_main                                 # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %s %s%s" % ("✓" if cond else "✗", name, ("  —— " + detail) if detail and not cond else ""))


def raises(status, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except HTTPException as exc:
        return exc.status_code == status, exc.detail
    return False, "没有抛 HTTPException"


def write(path, data=b"x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def seed(pid="p_deltest01"):
    """造一个"什么都有"的项目：页面、版本、终态任务、导出件、转换现场、账本记录。"""
    db.insert("projects", dict(id=pid, title="待删项目", source_type="markdown", status="done",
                               created_at=db.now(), updated_at=db.now()))
    db.insert("usage_log", dict(id="u_keep", ts=db.now(), project_id=pid, page_no=1, action="generate",
                                provider="local_render", model="local", size="2K", cny=0.0,
                                latency_ms=120, ok=1, detail="P1"))
    db.insert("slides", dict(id="s_del1", project_id=pid, page_no=1, title="第一页", status="done", created_at=db.now()))
    db.insert("slides", dict(id="s_del2", project_id=pid, page_no=2, title="第二页", status="done", created_at=db.now()))
    db.insert("slide_versions", dict(id="v_del1", slide_id="s_del1", snapshot_json="{}", created_at=db.now()))
    db.insert("jobs", dict(id="j_done", project_id=pid, kind="generate", status="done", pages_json="{}"))
    db.insert("operation_quotes", dict(id="q_del1", project_id=pid, fingerprint="fp", body_json="{}"))
    db.insert("operation_submissions", dict(id="k_del1", project_id=pid, fingerprint="fp", quote_json="{}",
                                            job_id="j_done", created_at=db.now()))

    project_dir = os.path.join(config.FILES_DIR, pid)
    write(os.path.join(project_dir, "source.md"), "原稿".encode())
    write(os.path.join(project_dir, "pages", "p01.png"))
    export_dir = os.path.join(config.FILES_DIR, "exports", "e_del1")
    write(os.path.join(export_dir, "待删项目_image_e_del1.pptx"))
    db.insert("exports", dict(id="e_del1", project_id=pid, kind="image", path=os.path.join(export_dir, "待删项目_image_e_del1.pptx"),
                              pages=2, created_at=db.now()))

    run_dir = os.path.join(config.FILES_DIR, "editppt", pid + "-run_x")
    frozen = os.path.join(config.FILES_DIR, "editppt", "input_frozen1")
    write(os.path.join(frozen, "1.png"))
    with open(write(os.path.join(run_dir, "sub", "deckforge_snapshot.json"), b""), "w", encoding="utf-8") as handle:
        json.dump([dict(id="s_del1", project_id=pid, page_no=1, image_path=os.path.join(frozen, "1.png"))], handle)

    outside = write(os.path.join(SANDBOX, "outside", "外部文件.pptx"))          # 不在 data/files 下
    db.insert("exports", dict(id="e_outside", project_id=pid, kind="image", path=outside, pages=1, created_at=db.now()))
    pipeline.JOBS["j_mem"] = dict(id="j_mem", project_id=pid, kind="generate", status="done")
    return dict(project_dir=project_dir, export_dir=export_dir, run_dir=run_dir, frozen=frozen, outside=outside)


def main():
    db.init_db()
    pid = "p_deltest01"
    print("[D1] 不存在的项目")
    ok, detail = raises(404, app_main.delete_project, "p_nope")
    check("404 且给出可读信息", ok, str(detail))

    print("[D2/D3] 守卫：任务在跑 / 缩略图后台构建中")
    files = seed(pid)
    db.insert("jobs", dict(id="j_live", project_id=pid, kind="beautify", status="running", pages_json="{}"))
    ok, detail = raises(409, app_main.delete_project, pid)
    check("有运行中任务 → 409", ok, str(detail))
    check("409 时项目记录仍在", db.q1("SELECT id FROM projects WHERE id=?", (pid,)) is not None)
    check("409 时磁盘文件仍在", os.path.isdir(files["project_dir"]) and os.path.isdir(files["run_dir"]))
    db.x("UPDATE jobs SET status='done' WHERE id='j_live'")
    source_pages._running.add(pid)
    try:
        ok, detail = raises(409, app_main.delete_project, pid)
        check("缩略图后台构建中 → 409", ok, str(detail))
    finally:
        source_pages._running.discard(pid)
    check("source_pages.is_running 对外可查", source_pages.is_running(pid) is False)

    print("[D4/D5/D6/D7] 正常删除")
    result = app_main.delete_project(pid)
    check("返回 ok + 项目名", result["ok"] is True and result["title"] == "待删项目")
    deleted = result["deleted"]
    check("projects/slides/slide_versions/jobs/exports 记录清空",
          deleted["projects"] == 1 and deleted["slides"] == 2 and deleted["slide_versions"] == 1
          and deleted["jobs"] == 2 and deleted["exports"] == 2,
          json.dumps(deleted, ensure_ascii=False))
    check("幂等提交与报价记录清空",
          deleted["operation_submissions"] == 1 and deleted["operation_quotes"] == 1)
    check("库里真的没有了",
          not db.q("SELECT id FROM projects WHERE id=?", (pid,))
          and not db.q("SELECT id FROM slides WHERE project_id=?", (pid,))
          and not db.q("SELECT id FROM slide_versions WHERE slide_id IN ('s_del1','s_del2')")
          and not db.q("SELECT id FROM jobs WHERE project_id=?", (pid,))
          and not db.q("SELECT id FROM exports WHERE project_id=?", (pid,)))
    check("内存作业登记也清掉", "j_mem" not in pipeline.JOBS)
    check("项目目录删除", not os.path.exists(files["project_dir"]) and result["files"]["project_dir"] == 1)
    check("导出件与其快照目录删除",
          not os.path.exists(files["export_dir"]) and result["files"]["export_files"] == 1
          and result["files"]["export_dirs"] == 1)
    check("精细重建现场与冻结输入删除",
          not os.path.exists(files["run_dir"]) and not os.path.exists(files["frozen"])
          and result["files"]["editppt_runs"] == 1 and result["files"]["frozen_inputs"] == 1)
    check("账本记录保留（删项目不抹账）",
          result["usage_log_kept"] == 1 and db.q1("SELECT id FROM usage_log WHERE id='u_keep'") is not None)
    ledger = operations.ledger(pid)
    check("删除后账本仍可读且项目名回退「已删除项目」",
          ledger["title"] == "已删除项目" and len(ledger["items"]) == 1)
    check("越界保护：data/files 之外的路径没被动过", os.path.isfile(files["outside"]))
    ok, detail = raises(404, app_main.delete_project, pid)
    check("重复删除 → 404", ok, str(detail))
    check("列表里不再出现该项目", all(item["id"] != pid for item in app_main.list_projects()["items"]))

    print("[D8] 路由注册")
    routes = [r for r in app_main.app.routes if getattr(r, "path", "") == "/api/projects/{pid}"]
    check("DELETE /api/projects/{pid} 已注册",
          any("DELETE" in (getattr(r, "methods", set()) or set()) for r in routes),
          ", ".join("%s %s" % (sorted(getattr(r, "methods", []) or []), r.path) for r in routes))


if __name__ == "__main__":
    try:
        main()
    finally:
        shutil.rmtree(SANDBOX, ignore_errors=True)
    print("\n通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：" + "；".join(FAIL))
    sys.exit(1 if FAIL else 0)
