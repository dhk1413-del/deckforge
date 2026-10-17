# -*- coding: utf-8 -*-
"""供应商面板侧用量回归（离线、零成本、不联网、不写生产库）。

覆盖：
  P1 USD 面板：累计美分 → 美元/人民币（按面板汇率），不限量上限识别
  P2 CNY 面板：total_usage 即人民币分；有限额度 → 上限/剩余
  P3 TOKENS 面板：不折算货币，只报原始累计
  P4 故障降级：401 / 超时 / 404 / 非 JSON → ok:false + 中文原因，不抛 5xx
  P5 无 key：完全不发请求；错误可读
  P6 缓存：60 秒内复用（不重复打面板），refresh=true 强制重查；失败结果也短缓存
  P7 快照增量：累计值只增不减时算出差额，并落库
  P8 密钥红线：key 不出现在返回结构/字符串里；只有计费请求带 Authorization
  P9 路由已注册 & 只对 `usage_api: new_api` 的供应商生效

用法：.venv/bin/python tools/test_provider_usage.py
"""
import json
import os
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SANDBOX = tempfile.mkdtemp(prefix="deckforge-provider-usage-")
os.environ["DECKFORGE_DATA"] = SANDBOX                  # 必须在导入 server.app 之前
sys.path.insert(0, ROOT)

import httpx                                            # noqa: E402
from server.app import config, db, provider_usage as pu   # noqa: E402

PASS, FAIL = [], []
KEY = "test-provider-usage-token-0001"   # 非真实密钥；只为断言 Authorization 头，且不能长得像真 key


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %s %s%s" % ("✓" if cond else "✗", name, ("  —— " + detail) if detail and not cond else ""))


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=None):
        self.status_code = status_code
        self._body = body
        self.text = text if text is not None else json.dumps(body)

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body


class FakeHTTP:
    """按 URL 片段路由的假 httpx.Client；同时记录所有请求，便于断言「有没有联网」。"""
    routes = {}
    calls = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, headers=None, timeout=None):
        FakeHTTP.calls.append(dict(url=url, headers=headers or {}, timeout=timeout))
        for fragment, value in FakeHTTP.routes.items():
            if fragment in url:
                if isinstance(value, Exception):
                    raise value
                return value
        raise AssertionError("未预期的请求：" + url)


STATUS_USD = FakeResponse(200, {"data": dict(quota_display_type="USD", usd_exchange_rate=7.3,
                                             quota_per_unit=500000)})
STATUS_CNY = FakeResponse(200, {"data": dict(quota_display_type="CNY", usd_exchange_rate=7.3)})


def route(usage_total=120.0, status=STATUS_USD, subscription=None, usage_override=None):
    FakeHTTP.routes = {
        "/api/status": status,
        "/v1/dashboard/billing/subscription": subscription or FakeResponse(200, dict(hard_limit_usd=1e8)),
        "/v1/dashboard/billing/usage": usage_override or FakeResponse(200, dict(object="list", total_usage=usage_total)),
    }


def reset():
    pu._CACHE.clear()
    pu._STATUS_CACHE.clear()
    FakeHTTP.calls.clear()
    FakeHTTP.routes = {}
    db.x("DELETE FROM provider_usage")


def run_summary(refresh=False):
    with patch.object(pu.httpx, "Client", FakeHTTP):
        return pu.summary(refresh=refresh)


def item_of(out):
    return out["items"][0]


def main():
    db.init_db()
    db.setting_set("key:guaihub", KEY)
    reset()

    print("[P1] USD 面板：累计 120 美分 = $1.20 ≈ ¥8.76（面板汇率 7.3）")
    route(usage_total=120.0)
    item = item_of(run_summary())
    check("查询成功", item["ok"] is True, item.get("error", ""))
    check("币种取面板 quota_display_type", item["currency"] == "USD")
    check("原值保留", item["total_usage"] == 120.0)
    check("美元 = 累计/100", item["used_usd"] == 1.2, str(item["used_usd"]))
    check("人民币按面板汇率折算", item["used_cny"] == 8.76, str(item["used_cny"]))
    check("面板不限量（1e8）识别为 unlimited", item["unlimited"] is True and item["limit_usd"] is None)
    check("首次查询无增量", item["first_snapshot"] is True and item["delta"] is None)
    check("三条计费请求都发了", len(FakeHTTP.calls) == 3, str([c["url"].rsplit("/", 1)[-1] for c in FakeHTTP.calls]))
    usage_call = next(c for c in FakeHTTP.calls if "billing/usage" in c["url"])
    status_call = next(c for c in FakeHTTP.calls if c["url"].endswith("/api/status"))
    check("计费请求带 Bearer", usage_call["headers"].get("Authorization") == "Bearer " + KEY)
    check("公开 status 请求不带密钥", "Authorization" not in status_call["headers"])
    dumped = json.dumps(item, ensure_ascii=False)
    check("返回结构里绝不含 key", KEY not in dumped)
    check("查询耗时字段可用", isinstance(item["duration_ms"], int) and item["duration_ms"] >= 0)

    print("[P2] CNY 面板 + 有限额度：800 分 = ¥8.00，上限 $50")
    reset()
    route(usage_total=800.0, status=STATUS_CNY,
          subscription=FakeResponse(200, dict(hard_limit_usd=50)))
    item = item_of(run_summary())
    check("币种 CNY", item["currency"] == "CNY")
    check("人民币 = 累计/100", item["used_cny"] == 8.0, str(item["used_cny"]))
    check("美元按汇率反算", item["used_usd"] == round(8.0 / 7.3, 6), str(item["used_usd"]))
    check("有限额度不当成无限", item["unlimited"] is False and item["limit_usd"] == 50.0)
    check("剩余额度 = 上限 - 已用", item["limit_remaining_usd"] == round(50.0 - 8.0 / 7.3, 6))

    print("[P3] TOKENS 面板：不折算货币")
    reset()
    route(usage_total=12345.0, status=FakeResponse(200, {"data": dict(quota_display_type="TOKENS")}))
    item = item_of(run_summary())
    check("币种 TOKENS", item["currency"] == "TOKENS")
    check("不编造美元/人民币金额", item["used_usd"] is None and item["used_cny"] is None)
    check("原始累计仍可读", item["total_usage"] == 12345.0)

    print("[P4] 故障降级：401 / 超时 / 404 / 非 JSON")
    for label, bad, expect in [
        ("401", FakeResponse(401, {"error": {"message": "Unauthorized"}}), "401"),
        ("超时", httpx.ConnectTimeout("boom"), "超时"),
        ("404", FakeResponse(404, {}), "404"),
        ("非 JSON", FakeResponse(200, None, text="<html>oops</html>"), "JSON"),
    ]:
        reset()
        route(usage_override=bad)
        item = item_of(run_summary())
        check("%s → ok:false 且原因可读" % label, item["ok"] is False and expect in item["error"],
              str(item.get("error")))

    print("[P5] 无 key：一个请求都不发")
    reset()
    route()
    with patch.object(db, "setting_get", side_effect=lambda k, default="": "" if k == "key:guaihub" else default), \
            patch.object(config, "_load_env", return_value={}):
        out = run_summary()
    item = item_of(out)
    check("无 key 时如实报错", item["ok"] is False and "key" in item["error"], str(item.get("error")))
    check("无 key 时不联网", FakeHTTP.calls == [], str(FakeHTTP.calls))

    print("[P6] 缓存与快照增量")
    reset()
    route(usage_total=120.0)
    first = item_of(run_summary())
    calls_after_first = len(FakeHTTP.calls)
    second = item_of(run_summary())
    check("60 秒内命中缓存", second["cached"] is True and len(FakeHTTP.calls) == calls_after_first)
    check("缓存返回同一累计值", second["total_usage"] == first["total_usage"])
    route(usage_total=125.0)
    third = item_of(run_summary(refresh=True))
    check("refresh=true 强制重查", third["cached"] is False and len(FakeHTTP.calls) > calls_after_first)
    check("累计只增时算出差额 +$0.05",
          third["delta"] is not None and third["delta"]["total_usage"] == 5.0
          and third["delta"]["used_usd"] == 0.05 and third["delta"]["previous_total"] == 120.0,
          json.dumps(third.get("delta"), ensure_ascii=False))
    rows = db.q("SELECT * FROM provider_usage ORDER BY rowid")
    check("每次成功查询落一条快照", len(rows) == 2, "%d 条" % len(rows))
    check("快照里也不含 key", KEY not in (rows[-1]["raw_json"] or ""))

    print("[P7] 失败结果短缓存 + 路由与开关")
    reset()
    route(usage_override=FakeResponse(500, {}))
    item_of(run_summary())
    failure_calls = len(FakeHTTP.calls)
    item_of(run_summary())
    check("失败结果 20 秒内不重复打面板", len(FakeHTTP.calls) == failure_calls)
    check("失败不落快照", db.q1("SELECT COUNT(*) AS n FROM provider_usage")["n"] == 0)
    from server.app import main as app_main
    paths = [getattr(r, "path", "") for r in app_main.app.routes]
    check("GET /api/provider-usage 已注册", "/api/provider-usage" in paths)
    providers_meta = {p["id"]: p for p in config.image_providers(with_keys=True)}
    check("guaihub 打开 usage_api 开关", providers_meta.get("guaihub", {}).get("usage_api") == "new_api")
    reset()
    route()
    with patch.object(config, "image_providers", side_effect=lambda with_keys=False: [
            dict(p, usage_api="") for p in providers_meta.values()]):
        out = run_summary()
    check("未开启开关的供应商不参与", out["items"] == [] and FakeHTTP.calls == [])


if __name__ == "__main__":
    try:
        main()
    finally:
        shutil.rmtree(SANDBOX, ignore_errors=True)
    print("\n通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：" + "；".join(FAIL))
    sys.exit(1 if FAIL else 0)
