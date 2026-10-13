"""原稿 PPTX 缩略图：缓存与失败降级的离线回归。"""
import os
import shutil
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from server.app import config, source_pages  # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("  %s %s%s" % ("✅" if ok else "❌", name, (" — " + detail) if detail else ""))


def main():
    root = tempfile.mkdtemp(prefix="df-source-pages-test-")
    original = config.FILES_DIR
    config.FILES_DIR = root
    try:
        print("[1] 无 PPTX 不生成")
        try:
            source_pages.build_pages("p_no_pptx", os.path.join(root, "source.txt"))
            check("非 PPTX 被拒绝", False)
        except ValueError:
            check("非 PPTX 被拒绝", True)

        print("[2] 已缓存不重转")
        pid = "p_cached"
        d = os.path.join(root, pid, "source-pages")
        os.makedirs(d)
        with open(os.path.join(d, "p01.png"), "wb") as f:
            f.write(b"cached")
        source_pages._write_status(pid, {"page_count": 1, "ready": True, "generating": False,
                                         "pages": [{"page_no": 1, "width": 420, "height": 237}]})
        missing = os.path.join(root, pid, "source.pptx")
        got = source_pages.build_pages(pid, missing)
        check("命中缓存时不需要原稿或 soffice", got.get("ready") and got.get("page_count") == 1)
        api = source_pages.response(pid)
        check("缓存响应给出缩略图 URL 和尺寸", api["pages"][0]["thumb_url"].endswith("/p01.png") and api["pages"][0]["width"] == 420)

        print("[3] 失败降级")
        fail_pid = "p_failed"
        with open(os.path.join(root, "fake.pptx"), "wb") as f:
            f.write(b"not a presentation")
        started = source_pages.start(fail_pid, os.path.join(root, "fake.pptx"))
        check("可登记后台任务", started)
        original_pdf = source_pages._pdf_from_pptx
        source_pages._pdf_from_pptx = lambda _path: (_ for _ in ()).throw(RuntimeError("测试转换器故障"))
        try:
            import asyncio
            from unittest.mock import patch
            async def offline_thread(fn, *args, **kwargs):
                return fn(*args, **kwargs)
            with patch("asyncio.to_thread", side_effect=offline_thread):
                asyncio.run(source_pages.build_background(fail_pid, os.path.join(root, "fake.pptx")))
        finally:
            source_pages._pdf_from_pptx = original_pdf
        failed = source_pages.response(fail_pid)
        check("转换异常写成可用降级状态", not failed["ready"] and not failed["generating"] and bool(failed.get("error")))

        # 历史 bug：状态说 ready、缩略图文件却缺失 → start() 只看状态位就拒绝重建，缓存永不修复
        print("[4] 缓存自愈：状态 ready 但缩略图缺失必须要求重建")
        pid_broken = "p_broken"
        d2 = os.path.join(root, pid_broken, "source-pages")
        os.makedirs(d2)
        with open(os.path.join(d2, "p01.png"), "wb") as f:
            f.write(b"only-one")
        two_pages = [{"page_no": 1, "width": 420, "height": 237}, {"page_no": 2, "width": 420, "height": 237}]
        source_pages._write_status(pid_broken, {"page_count": 2, "ready": True, "generating": False, "pages": two_pages})
        # 真实次序：客户端先 GET 状态（此时状态位说 ready、文件却缺一张）
        broken = source_pages.response(pid_broken)
        check("接口不再假报 ready 且给出原因", broken["ready"] is False and bool(broken.get("error")), broken.get("error", ""))
        check("缺一张缩略图 → 判定缓存不可用",
              not source_pages._cache_usable(pid_broken, source_pages._read_status(pid_broken), ""))
        check("start() 要求重建（不能秒回 ready）", source_pages.start(pid_broken, "") is True)
        source_pages._running.discard(pid_broken)          # 清理后台登记，便于后续断言

        with open(os.path.join(d2, "p02.png"), "wb") as f:
            f.write(b"second")
        source_pages._write_status(pid_broken, {"page_count": 2, "ready": True, "generating": False, "pages": two_pages})
        check("补齐后命中缓存（start() 不再重建）", source_pages.start(pid_broken, "") is False)
        source_pages._running.discard(pid_broken)
        check("接口恢复 ready", source_pages.response(pid_broken)["ready"] is True)

        print("[5] 原稿变更（指纹不同）→ 缓存作废")
        pptx = os.path.join(root, "fingerprint.pptx")
        with open(pptx, "wb") as f:
            f.write(b"v1")
        status_v1 = {"page_count": 2, "ready": True, "generating": False, "pages": two_pages,
                     "source": source_pages._source_info(pptx)}
        source_pages._write_status(pid_broken, status_v1)
        check("同一份原稿 → 可复用", source_pages._cache_usable(pid_broken, status_v1, pptx))
        with open(pptx, "wb") as f:
            f.write(b"v2-longer-content")
        check("原稿变了 → 不可复用（需重转）", not source_pages._cache_usable(pid_broken, status_v1, pptx))
    finally:
        config.FILES_DIR = original
        shutil.rmtree(root, ignore_errors=True)
    print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
