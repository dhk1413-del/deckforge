"""`GET /slides` 的 native_status 汇报口径回归（纯函数、离线）。

历史 bug：把所有非 ready 的行都报成 stale → 刚生成、从未构建的页面在角标里显示「待按图片重建」。
本回归锁定：pending/failed/building 原样返回，只有 ready/legacy_overlay 才可能被判为 stale。
"""
import hashlib
import json
import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from server.app.pipeline import reported_native_status  # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("  %s %s%s" % ("✅" if ok else "❌", name, (" — " + detail) if detail else ""))


def main():
    tmp = tempfile.mkdtemp(prefix="df-status-test-")
    try:
        img = os.path.join(tmp, "1.png")
        with open(img, "wb") as f:
            f.write(b"fake-png-bytes")
        other = os.path.join(tmp, "2.png")
        with open(other, "wb") as f:
            f.write(b"different-bytes")
        sha = hashlib.sha256(open(img, "rb").read()).hexdigest()

        def row(status, scene=None, image=img):
            return dict(native_status=status, image_path=image,
                        native_scene_json=json.dumps(scene or {}, ensure_ascii=False))

        current = dict(version=2, source_image=dict(path=img, sha256=sha))

        print("[1] 从未构建 / 构建失败 / 构建中：原样返回，不伪装成「待重建」")
        check("pending → pending", reported_native_status(row("pending")) == "pending")
        check("空状态 → pending", reported_native_status(dict(native_status=None, image_path=img)) == "pending")
        check("failed → failed", reported_native_status(row("failed")) == "failed")
        check("building → building", reported_native_status(row("building")) == "building")

        print("[2] 已构建：按「场景是否仍然对得上当前图片」判定")
        check("ready + 场景匹配 → ready", reported_native_status(row("ready", current)) == "ready")
        check("ready + 场景 sha 不匹配 → stale",
              reported_native_status(row("ready", dict(version=2, source_image=dict(sha256="deadbeef")))) == "stale")
        check("ready + 旧版场景(version=1) → stale",
              reported_native_status(row("ready", dict(version=1, source_image=dict(sha256=sha)))) == "stale")
        check("ready + 无场景 → stale", reported_native_status(row("ready", {})) == "stale")
        check("ready + 图片换了 → stale", reported_native_status(row("ready", current, image=other)) == "stale")

        print("[3] 旧版叠字：不能再被称作原生可编辑")
        check("legacy_overlay → stale", reported_native_status(row("legacy_overlay", current)) == "stale")

        print("[4] 不抛异常（脏数据也不能让接口 500）")
        for bad in (dict(native_status="ready", image_path="/nope/missing.png", native_scene_json="{坏 json"),
                    dict(native_status="ready", image_path="", native_scene_json="null")):
            try:
                out = reported_native_status(bad)
                check("脏数据返回字符串：%s" % out, isinstance(out, str))
            except Exception as exc:                       # noqa: BLE001
                check("脏数据不抛异常", False, "%s: %s" % (type(exc).__name__, exc))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
