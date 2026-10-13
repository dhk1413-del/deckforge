"""`editppt_engine._validation_passed()` 的读取时序回归（纯函数、离线、几秒内跑完）。

历史 bug（2026-09-21 真实现场）：page worker 是 agent，退出前后仍在写 `validation.json`；
平台在它退出的**那一瞬**读到的还是旧的 `passed=false` → 整单报「1/1 页未通过校验」并 failed，
而几秒后同一文件已是 `passed=true`。修法：未通过时重试（默认 3 次 × 4s）。

本回归锁定三件事：
  ① 短暂窗口内的「旧的 false → 变 true」必须被重试捞到（否则又会误判整单失败）
  ② 超出重试窗口仍判失败（不能无限等）
  ③ 始终不通过 / 文件缺失 / 非法 JSON 一律判失败，且不抛异常（绝不假绿）
"""
import json
import os
import sys
import tempfile
import threading
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from server.app.editppt_engine import _validation_passed  # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("  %s %s%s" % ("✅" if ok else "❌", name, (" — " + detail) if detail else ""))


def page_with(state, rewrite_after=None):
    """建一个 page 目录：先放 `state`；rewrite_after 秒后改成 passed=true（模拟 worker 收尾写入）。"""
    page = os.path.join(tempfile.mkdtemp(prefix="df-valrace-"), "page_001")
    os.makedirs(page)
    json.dump(state, open(os.path.join(page, "validation.json"), "w", encoding="utf-8"))
    if rewrite_after is not None:
        def later():
            time.sleep(rewrite_after)
            json.dump({"passed": True}, open(os.path.join(page, "validation.json"), "w", encoding="utf-8"))
        threading.Thread(target=later, daemon=True).start()
    return page


def main():
    print("[1] 窗口内翻盘：旧的 false → 3s 后变 true，必须重试捞到（默认 3 次 × 4s）")
    t0 = time.time()
    res = _validation_passed(page_with({"passed": False}, rewrite_after=3))
    check("3s 后写通过 → 判通过", res.get("passed") is True, "耗时 %.1fs" % (time.time() - t0))

    print("[2] 边界：越晚写好越久，但仍在窗口内（第 2、3 次尝试）")
    res = _validation_passed(page_with({"passed": False}, rewrite_after=6))
    check("6s 后写通过 → 判通过", res.get("passed") is True)

    print("[3] 超出重试窗口：不许无限等，如实判失败")
    t0 = time.time()
    res = _validation_passed(page_with({"passed": False}, rewrite_after=30))
    check("30s 后才写通过 → 判失败（窗口已过）", not res.get("passed"), "耗时 %.1fs" % (time.time() - t0))

    print("[4] 真失败 / 缺文件 / 坏 JSON：一律判失败且不抛异常（不假绿）")
    res = _validation_passed(page_with({"passed": False}))
    check("始终 false → 判失败", res.get("passed") is False)

    empty = os.path.join(tempfile.mkdtemp(prefix="df-valrace-"), "page_001")
    os.makedirs(empty)
    res = _validation_passed(empty)
    check("没有 validation.json → 判失败并给出原因",
          res.get("passed") is False and "未生成" in str(res.get("reason")), str(res.get("reason"))[:40])

    broken = os.path.join(tempfile.mkdtemp(prefix="df-valrace-"), "page_001")
    os.makedirs(broken)
    open(os.path.join(broken, "validation.json"), "w", encoding="utf-8").write("{oops")
    try:
        res = _validation_passed(broken)
        check("非法 JSON → 判失败且不抛异常", res.get("passed") is False, str(res.get("reason"))[:60])
    except Exception as exc:                                    # noqa: BLE001
        check("非法 JSON → 判失败且不抛异常", False, "%s: %s" % (type(exc).__name__, exc))

    print("\n" + "=" * 60)
    print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
