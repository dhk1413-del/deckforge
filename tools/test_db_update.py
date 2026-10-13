"""`db.update()` 的列自适应回归（离线）。

真机踩到：`update()` 无条件写 `updated_at`，而 **exports 表没有这一列** →
任何对 exports 的更新都抛 `no such column: updated_at`（我在迁移高精度产物时被它拦住）。
另外 `update()` 之前对"没有任何字段"的调用也会拼出非法 SQL。
"""
import os
import shutil
import sqlite3
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from server.app import config, db  # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("  %s %s%s" % ("✅" if ok else "❌", name, (" — " + detail) if detail else ""))


def main():
    tmp = tempfile.mkdtemp(prefix="db-update-test-")
    orig_db, orig_files, orig_init = db.DB_PATH, config.FILES_DIR, db._INITIALIZED
    db.DB_PATH = os.path.join(tmp, "t.db")
    config.FILES_DIR = tmp
    db._INITIALIZED = False
    db._COLUMNS_CACHE.clear()
    try:
        print("[1] 没有 updated_at 列的表（exports）也必须能更新")
        db.insert("exports", dict(id="e1", project_id="p1", kind="editable_hi", path="/tmp/a.pptx",
                                  pages=1, created_at=db.now()))
        try:
            db.update("exports", "e1", dict(path="/tmp/b.pptx", size_bytes=123))
            check("更新成功（以前一律抛 no such column: updated_at）", True)
        except sqlite3.OperationalError as exc:
            check("更新成功（以前一律抛 no such column: updated_at）", False, str(exc))
        row = db.q1("SELECT * FROM exports WHERE id='e1'")
        check("字段真的写进去了", row["path"] == "/tmp/b.pptx" and row["size_bytes"] == 123)
        check("没有凭空多出 updated_at 列", "updated_at" not in db.table_columns("exports"))

        print("[2] 有 updated_at 列的表（slides）仍然自动写时间戳")
        db.insert("slides", dict(id="s1", project_id="p1", page_no=1, status="pending",
                                 created_at=db.now(), updated_at="2000-01-01T00:00:00"))
        db.update("slides", "s1", dict(status="done"))
        row = db.q1("SELECT * FROM slides WHERE id='s1'")
        check("业务字段更新成功", row["status"] == "done")
        check("updated_at 自动刷新（不再是旧值）", row["updated_at"] != "2000-01-01T00:00:00", row["updated_at"])

        print("[3] 边界：列探测与空更新")
        check("table_columns 能列出真实列",
              {"id", "project_id", "kind", "path", "pages"} <= db.table_columns("exports"))
        check("table_columns 对未知表返回空集（不抛异常）", db.table_columns("不存在的表") == set())
        try:
            db.update("exports", "e1", {})                     # 空更新不该拼出非法 SQL
            check("空更新不抛异常（以前会拼出 `SET  WHERE`）", True)
        except sqlite3.OperationalError as exc:
            check("空更新不抛异常（以前会拼出 `SET  WHERE`）", False, str(exc))
    finally:
        db.DB_PATH, config.FILES_DIR, db._INITIALIZED = orig_db, orig_files, orig_init
        db._COLUMNS_CACHE.clear()
        shutil.rmtree(tmp, ignore_errors=True)
    print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
