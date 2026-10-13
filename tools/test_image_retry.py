"""生图重试与链路切换回归（离线、不联网、不花钱）。

背景（真机事故）：到 api.guaihub.cc 的 TLS 连接被重置（`ConnectError: EOF occurred in violation of protocol`），
而 generate_image 只尝试一次 → 立刻返回失败 → 上层降级成本地兜底渲染（几何排版，效果很差）。
本回归锁定修复后的行为：瞬态错误重试 + 自动切换链路（代理↔直连），非瞬态错误不浪费重试。
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import httpx  # noqa: E402

from server.app import config, providers  # noqa: E402

PASS, FAIL = [], []
PROVIDER = dict(id="guaihub", label="GuaiHub", base_url="https://api.guaihub.cc/v1", key="sk-test",
                api_style="openai_compatible", needs_proxy=True, default_model="gpt-image-2",
                default_size="2K", unit_price_cny=None)


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("  %s %s%s" % ("✅" if ok else "❌", name, (" — " + detail) if detail else ""))


def transient(msg="EOF occurred in violation of protocol"):
    return httpx.ConnectError(msg)


def status_error(code):
    req = httpx.Request("POST", "https://api.guaihub.cc/v1/images/generations")
    return httpx.HTTPStatusError("HTTP %d" % code, request=req, response=httpx.Response(code, request=req))


class Harness:
    """把 provider 选择、网络调用、退避节奏全部替换成可控的假件。"""

    def __init__(self, script, provider=None, proxy_available=True, retry_extra=2):
        self.script = list(script)          # 每次调用依次抛出/返回
        self.calls = []                     # 记录 (use_proxy)
        self.provider = dict(provider or PROVIDER)
        self.proxy_available = proxy_available
        self.retry_extra = retry_extra
        self.saved = {}

    def __enter__(self):
        s = self.saved
        s["pick"] = providers.pick_image_provider
        s["call"] = providers._call_image_provider
        s["backoff"] = providers.RETRY_BACKOFF
        s["yaml"] = config.load_providers_yaml
        s["proxy_for"] = config.proxy_for
        providers.pick_image_provider = lambda: dict(self.provider)
        providers._call_image_provider = self._call
        providers.RETRY_BACKOFF = (0.0, 0.0)                          # 测试不真等
        config.load_providers_yaml = lambda: {"common": {"retry": self.retry_extra},
                                              "network": {"mode": "http_proxy", "http_proxy": "http://127.0.0.1:7897"}}
        config.proxy_for = lambda needs: ({"https://": "http://127.0.0.1:7897"} if needs and self.proxy_available else None)
        return self

    def __exit__(self, *exc):
        providers.pick_image_provider = self.saved["pick"]
        providers._call_image_provider = self.saved["call"]
        providers.RETRY_BACKOFF = self.saved["backoff"]
        config.load_providers_yaml = self.saved["yaml"]
        config.proxy_for = self.saved["proxy_for"]
        return False

    def _call(self, p, prompt, size, use_proxy):
        self.calls.append(bool(use_proxy))
        item = self.script.pop(0) if self.script else b"PNG"
        if isinstance(item, Exception):
            raise item
        return item


def main():
    print("[1] 首次瞬态失败 → 重试成功（不再一次失败就降级）")
    with Harness([transient(), b"IMG"]) as h:
        res = providers.generate_image("p", "2K")
    check("最终成功", res["ok"] and res["image_bytes"] == b"IMG")
    check("记录了尝试次数=2", res.get("attempts") == 2, str(res.get("attempts")))
    check("共调用 2 次 provider", len(h.calls) == 2, str(h.calls))

    print("[2] 链路切换：走代理失败 → 自动改直连")
    with Harness([transient("proxy reset"), b"IMG"]) as h:
        res = providers.generate_image("p", "2K")
    check("第一次走代理、第二次走直连", h.calls == [True, False], str(h.calls))
    check("成功并标记最终链路", res["ok"] and res.get("route") == "direct", str(res.get("route")))

    print("[3] 直连型 provider 失败 → 备选走代理（代理可用时）")
    with Harness([transient(), transient(), b"IMG"], provider={**PROVIDER, "needs_proxy": False}) as h:
        res = providers.generate_image("p", "2K")
    check("链路在直连/代理之间轮换", h.calls[:2] == [False, True], str(h.calls))
    check("第三次成功（代理链路被用上）", res["ok"] and res.get("attempts") == 3, str(res.get("attempts")))

    print("[4] 代理不可用时不把代理当备选（TUN/none 模式下别乱试）")
    with Harness([transient(), b"IMG"], provider={**PROVIDER, "needs_proxy": False}, proxy_available=False) as h:
        res = providers.generate_image("p", "2K")
    check("只走直连链路", all(c is False for c in h.calls), str(h.calls))

    print("[5] 非瞬态错误（401）不重试：重试只是白等")
    with Harness([status_error(401), b"IMG"]) as h:
        res = providers.generate_image("p", "2K")
    check("只调用 1 次", len(h.calls) == 1, str(len(h.calls)))
    check("返回失败且说明原因", not res["ok"] and "401" in res["message"], res["message"][:60])

    print("[6] 5xx / 429 属于瞬态，会重试")
    for code in (500, 429):
        with Harness([status_error(code), b"IMG"]) as h:
            res = providers.generate_image("p", "2K")
        check("HTTP %d 触发重试并最终成功" % code, res["ok"] and len(h.calls) == 2, str(len(h.calls)))

    print("[7] 全部失败：返回可读原因 + 尝试次数（交由上层降级）")
    with Harness([transient("reset-1"), transient("reset-2"), transient("reset-3")]) as h:
        res = providers.generate_image("p", "2K")
    check("ok=False", not res["ok"] and res["reason"] == "call_failed")
    check("已用满尝试次数", res.get("attempts") == 3 and len(h.calls) == 3, str(res.get("attempts")))
    check("message 说明尝试次数", "尝试 3 次仍失败" in res["message"], res["message"][:52])
    check("message 区分链路（代理/直连）", "代理" in res["message"] and "直连" in res["message"], res["message"][:80])

    print("[8] 重试次数读取 providers.yaml 的 common.retry")
    with Harness([transient(), transient(), transient(), b"IMG"], retry_extra=3) as h:
        res = providers.generate_image("p", "2K")
    check("retry=3 → 最多 4 次尝试", res["ok"] and res.get("attempts") == 4, str(res.get("attempts")))
    check("上限保护（不会无界重试）", providers._retry_config.__module__ == "server.app.providers")
    with Harness([transient()] * 9, retry_extra=99) as h:
        providers.generate_image("p", "2K")
    check("retry 配得再大也被夹到 4 次", len(h.calls) == 4, str(len(h.calls)))

    print("[9] 未配置 key：不重试、不报错，直接交给上层降级")
    saved = providers.pick_image_provider
    providers.pick_image_provider = lambda: None
    try:
        res = providers.generate_image("p", "2K")
    finally:
        providers.pick_image_provider = saved
    check("not_configured 且无尝试", res["reason"] == "not_configured" and res.get("attempts") is None)
    check("文案说明降级", "降级" in res["message"], res["message"][:40])

    print("[10] 链路顺序不自相矛盾（首选项永远是配置的那条）")
    check("needs_proxy=True → [代理, 直连]", providers._attempt_routes(True) == [True, False])
    print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
