"""「图片转可编辑」第 1 段（page_import）离线回归：三源渲染、缓存自愈、slips 登记。

零成本、不调模型、不碰真实库（临时 DB + 临时 FILES_DIR）。
"""
import os
import shutil
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from server.app import config, db, page_import  # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("  %s %s%s" % ("✅" if ok else "❌", name, (" — " + detail) if detail else ""))


def make_pdf(path, pages=3):
    import fitz
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=960, height=540)
        page.insert_text((60, 120), "page %d" % (i + 1), fontsize=44)
    doc.save(path)
    doc.close()


def make_png(path, color=(30, 120, 250)):
    from PIL import Image
    Image.new("RGB", (800, 450), color).save(path, "PNG")


def main():
    root = tempfile.mkdtemp(prefix="df-page-import-test-")
    original_files, original_db = config.FILES_DIR, db.DB_PATH
    config.FILES_DIR = root
    db.DB_PATH = os.path.join(root, "test.db")
    db._INITIALIZED = False
    try:
        pid = "p_import"
        os.makedirs(os.path.join(root, pid), exist_ok=True)
        db.insert("projects", dict(id=pid, title="导入测试", source_type="pdf", intake_mode="doc",
                                   status="draft", created_at=db.now(), updated_at=db.now()))

        print("[1] 不支持的格式被拒")
        txt = os.path.join(root, "note.txt")
        open(txt, "w").close()
        try:
            page_import.render_pages(pid, [txt])
            check("非 PDF/图片/pptx 被拒绝", False)
        except ValueError as exc:
            check("非 PDF/图片/pptx 被拒绝", "不支持的原稿格式" in str(exc))
        check("空来源被拒", _raises(lambda: page_import.render_pages(pid, [])))

        print("[2] 图片：一张 = 一页，统一到 1600 宽")
        img1 = os.path.join(root, "a.png")
        make_png(img1)
        st = page_import.render_pages(pid, [img1])
        check("渲染出 1 页", st["ready"] and st["page_count"] == 1)
        check("宽度统一为 1600", st["pages"][0]["width"] == 1600, str(st["pages"][0]))
        check("比例保持（800x450 → 1600x900）", st["pages"][0]["height"] == 900)
        check("页图文件真的存在", os.path.isfile(page_import.page_image(pid, 1)))

        print("[3] 多张图片按顺序拼接")
        img2 = os.path.join(root, "b.png")
        make_png(img2, (255, 120, 30))
        st2 = page_import.render_pages(pid, [img1, img2])
        check("两张图 → 2 页", st2["page_count"] == 2)
        check("页码连续 1/2", [p["page_no"] for p in st2["pages"]] == [1, 2])

        print("[4] PDF 逐页渲染")
        pdf = os.path.join(root, "deck.pdf")
        make_pdf(pdf, pages=3)
        st3 = page_import.render_pages(pid, [pdf])
        check("3 页 PDF → 3 页图", st3["page_count"] == 3, str(st3.get("renderer")))
        check("渲染器记录为 PyMuPDF", "PyMuPDF" in (st3.get("renderer") or ""))

        print("[5] 缓存：同源重复调用不重渲")
        again = page_import.render_pages(pid, [pdf])
        check("命中缓存（generated_at 未变）", again.get("generated_at") == st3.get("generated_at"))

        print("[6] 缓存自愈：页图缺失 → 判定不可用并重渲")
        os.unlink(page_import.page_image(pid, 2))
        check("缺页图 → cache_usable False", not page_import.cache_usable(pid, again, [_src(pdf)]))
        check("接口不宣称 ready", page_import.response(pid)["ready"] is False)
        healed = page_import.render_pages(pid, [pdf])
        check("重渲后文件补齐", page_import.files_intact(pid, healed["pages"]))

        print("[7] 来源变更 → 旧页图作废")
        make_pdf(pdf, pages=1)
        changed = page_import.render_pages(pid, [pdf])
        check("指纹变了 → 重渲（1 页）", changed["page_count"] == 1)

        print("[8] 登记成 slides 行（既有「导出图片版 / 转可编辑」据此工作）")
        written = page_import.register_slides(pid, changed)
        row = db.q1("SELECT * FROM slides WHERE project_id=? AND page_no=1", (pid,))
        check("写入 1 行", written == 1 and row is not None)
        assert row is not None                     # 断言失败即用例失败，下面直接取字段
        check("image_path 指向原页图", (row["image_path"] or "").endswith("pages/p01.png"))
        check("provider 标记为 import", row["provider"] == "import")
        db.update("slides", row["id"], dict(editable=1, native_status="ready",
                                            native_scene_json='{"version":2}'))
        page_import.register_slides(pid, changed)
        row2 = db.q1("SELECT * FROM slides WHERE project_id=? AND page_no=1", (pid,))
        assert row2 is not None
        check("幂等：不新增行", len(db.q("SELECT id FROM slides WHERE project_id=?", (pid,))) == 1)
        check("保留已转可编辑成果", row2["editable"] == 1 and row2["native_status"] == "ready")

        print("[9] 清理")
        page_import.clear(pid)
        check("clear 后无状态且不宣称 ready", page_import.response(pid)["ready"] is False
              and not os.path.isdir(page_import._pages_dir(pid)))
    finally:
        config.FILES_DIR = original_files
        db.DB_PATH = original_db
        db._INITIALIZED = False
        shutil.rmtree(root, ignore_errors=True)
    print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
    return 1 if FAIL else 0


def _src(path):
    return page_import._source_info(path)


def _raises(fn):
    try:
        fn()
        return False
    except Exception:
        return True


if __name__ == "__main__":
    sys.exit(main())
