# -*- coding: utf-8 -*-
"""供应商面板侧用量：New API 兼容计费接口（当前用于 GuaiHub）。

## 为什么能接

GuaiHub 是 **New API** 面板，它的 OpenAI 兼容计费接口用**同一个 sk- key** 就能查，不需要面板登录态：

    GET {root}/api/status                         （公开）quota_display_type / usd_exchange_rate
    GET {root}/v1/dashboard/billing/usage         → {"object":"list","total_usage":115.0}
    GET {root}/v1/dashboard/billing/subscription  → hard_limit_usd（不限量时面板给 1e8）

## 口径（2026-10-17 实测，别当成日期区间）

  · usage 是**累计**值：`start_date/end_date` 被服务端忽略，换区间返回同一个数；因此只报
    「累计 + 自上次快照的增量」，绝不编造「本期用量」。
  · `total_usage` 单位 = 面板展示货币的 0.01（`quota_display_type=USD` 时就是美分）。
  · 面板的令牌统计开关（DisplayTokenStatEnabled）不对外暴露：开启时是该 **key** 累计，
    关闭时是**整个账号**累计。界面如实说明两种可能，不猜。
  · 汇率用面板自己给的 `usd_exchange_rate` 折算，不自己编汇率。

密钥只在本模块内用于请求头，绝不写日志、不进返回值。
"""
import json
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import httpx

from . import config, db, providers

CACHE_SECONDS = 60          # 正常结果缓存：用量是累计值，1 分钟内重复查没有意义
FAIL_CACHE_SECONDS = 20     # 失败缓存：网络抖动时别让每次刷新都卡一遍
USAGE_TIMEOUT = 8.0
AUX_TIMEOUT = 5.0
UNLIMITED_THRESHOLD = 1e8   # New API 对「不限量」令牌/账号直接填 1e8

_LOCK = threading.Lock()
_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


class _QueryError(Exception):
    """查询失败（已转成中文、已脱敏，可直接展示给用户）。"""


def _float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _money(total: Optional[float], display: str,
           rate: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    """把面板的 `total_usage` 归一到美元/人民币；未知币种（tokens）返回 (None, None)。"""
    if total is None:
        return None, None
    if display == "CNY":
        cny = total / 100.0
        return (round(cny / rate, 6) if rate else None), round(cny, 6)
    if display == "TOKENS":
        return None, None
    usd = total / 100.0                                  # 面板默认：0.01 美元 / 单位
    return round(usd, 6), (round(usd * rate, 6) if rate else None)


def _root(base_url: str) -> str:
    root = (base_url or "").rstrip("/")
    return root[:-3] if root.endswith("/v1") else root


def _get_json(client: httpx.Client, url: str, key: Optional[str],
              timeout: float) -> Dict[str, Any]:
    headers = {"Authorization": "Bearer " + key} if key else {}
    try:
        response = client.get(url, headers=headers, timeout=timeout)
    except httpx.TimeoutException:
        raise _QueryError("查询超时：供应商面板没有在 %d 秒内响应（网络不通或面板繁忙）" % int(timeout))
    except httpx.HTTPError as exc:
        raise _QueryError("网络错误：%s" % type(exc).__name__)
    if response.status_code == 401:
        raise _QueryError("鉴权失败（HTTP 401）：这个 key 无权查询计费接口，或 key 已失效")
    if response.status_code == 404:
        raise _QueryError("该供应商没有计量费接口（HTTP 404），无法查询面板用量")
    if response.status_code >= 400:
        raise _QueryError("供应商面板返回 HTTP %d" % response.status_code)
    try:
        body = response.json()
    except ValueError:
        raise _QueryError("供应商面板返回的不是 JSON，无法解析用量")
    if not isinstance(body, dict):
        raise _QueryError("供应商面板返回结构异常（不是对象）")
    if isinstance(body.get("error"), dict):
        message = str(body["error"].get("message") or "供应商面板返回错误")
        raise _QueryError("供应商面板报错：%s" % message[:120])
    return body


def _quiet(future: Future) -> Dict[str, Any]:
    """可选请求：失败就返回空字典（不影响主结论，也不把异常甩给上层）。"""
    try:
        body = future.result()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


def _previous_snapshot(provider_id: str, currency: str) -> Optional[Dict[str, Any]]:
    row = db.q1("SELECT * FROM provider_usage WHERE provider_id=? AND currency=? ORDER BY rowid DESC LIMIT 1",
                (provider_id, currency))
    return dict(row) if row else None


def _delta(current_total: float, display: str, rate: Optional[float],
           previous: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """与上次成功快照比较；没有上次记录（或旧记录没有数值）时返回 None。"""
    if not previous or previous.get("total_usage") is None:
        return None
    previous_total = _float(previous.get("total_usage"))
    if previous_total is None:
        return None
    change = round(float(current_total) - previous_total, 6)
    change_usd, change_cny = _money(change, display, rate)
    return dict(total_usage=change, used_usd=change_usd, used_cny=change_cny,
                previous_ts=previous.get("ts"), previous_total=previous_total)


def _snapshot(provider_id: str, display: str, total: float, rate: Optional[float],
              used_usd: Optional[float], used_cny: Optional[float],
              raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """记录一次成功快照，并返回与上一次快照的差额（首次查询返回 None）。"""
    delta = _delta(total, display, rate, _previous_snapshot(provider_id, display))
    try:
        db.insert("provider_usage", dict(id=db.uid("pu"), provider_id=provider_id, ts=db.now(),
                                         total_usage=total, currency=display,
                                         used_usd=used_usd, used_cny=used_cny,
                                         raw_json=json.dumps(raw, ensure_ascii=False)[:4000]))
    except Exception:                                    # 快照落库失败不影响本次展示
        pass
    return delta


def _probe(provider: Dict[str, Any]) -> Dict[str, Any]:
    """查一次面板（状态 → 用量 → 订阅）。同步、可能耗时 3~10 秒。"""
    root = _root(provider.get("base_url", ""))
    key = provider.get("key") or ""
    started = time.monotonic()
    if not root:
        raise _QueryError("未配置 API Base URL，无法查询面板用量")
    if not key:
        raise _QueryError("未配置 API key，无法查询面板用量")

    kwargs = providers._client_kwargs(bool(provider.get("needs_proxy")), USAGE_TIMEOUT)
    with httpx.Client(**kwargs) as client:
        # 三个请求互不依赖，并行发：串行实测要 12 秒，并行后最坏约 8 秒。
        with ThreadPoolExecutor(max_workers=3) as pool:
            status_future = pool.submit(_get_json, client, root + "/api/status", None, AUX_TIMEOUT)
            usage_future = pool.submit(_get_json, client, root + "/v1/dashboard/billing/usage", key, USAGE_TIMEOUT)
            subscription_future = pool.submit(
                _get_json, client, root + "/v1/dashboard/billing/subscription", key, AUX_TIMEOUT)
            status_body = _quiet(status_future)              # 公开接口：拿币种/汇率；失败也继续
            raw_usage = usage_future.result()                # 主结论：必需
            subscription = _quiet(subscription_future)       # 上限只是补充信息
        status = status_body.get("data") if isinstance(status_body.get("data"), dict) else status_body
        total = _float(raw_usage.get("total_usage"))
        if total is None:
            raise _QueryError("供应商没有返回 total_usage，无法确定已用额度")

    display = str(status.get("quota_display_type") or "USD").upper()
    rate = _float(status.get("usd_exchange_rate"))
    used_usd, used_cny = _money(total, display, rate)
    hard_limit = _float(subscription.get("hard_limit_usd"))
    unlimited = hard_limit is None or hard_limit >= UNLIMITED_THRESHOLD
    limit_usd = None if unlimited else hard_limit
    delta = _snapshot(provider["id"], display, total, rate, used_usd, used_cny,
                      dict(status=status, usage=raw_usage, subscription=subscription))
    return dict(
        provider_id=provider["id"], label=provider.get("label") or provider["id"],
        ok=True, cached=False, currency=display, total_usage=total,
        used_usd=used_usd, used_cny=used_cny, exchange_rate=rate,
        unlimited=unlimited, limit_usd=limit_usd,
        limit_remaining_usd=(round(limit_usd - used_usd, 6) if limit_usd is not None and used_usd is not None else None),
        quota_per_unit=_float(status.get("quota_per_unit")),
        fetched_at=db.now(), duration_ms=int((time.monotonic() - started) * 1000), error="",
        scope_note="累计值（面板忽略日期范围）；若面板开启令牌统计则为该 key 累计，否则为该账号累计",
        delta=delta,
        first_snapshot=delta is None,
    )


def _error_item(provider: Dict[str, Any], error: str, started: float) -> Dict[str, Any]:
    return dict(provider_id=provider["id"], label=provider.get("label") or provider["id"],
                ok=False, cached=False, currency="", total_usage=None, used_usd=None, used_cny=None,
                exchange_rate=None, unlimited=None, limit_usd=None, limit_remaining_usd=None,
                quota_per_unit=None, fetched_at=db.now(),
                duration_ms=int((time.monotonic() - started) * 1000), error=error,
                scope_note="", delta=None, first_snapshot=True)


def _cached(provider: Dict[str, Any], refresh: bool) -> Dict[str, Any]:
    pid = provider["id"]
    now = time.monotonic()
    with _LOCK:
        hit = _CACHE.get(pid)
        if hit and not refresh:
            ttl = CACHE_SECONDS if hit[1].get("ok") else FAIL_CACHE_SECONDS
            if now - hit[0] < ttl:
                return dict(hit[1], cached=True)
        started = time.monotonic()
        try:
            item = _probe(provider)
        except _QueryError as exc:
            item = _error_item(provider, str(exc), started)
        except Exception as exc:                        # 任何意外都降级成可读错误，绝不让统计页 500
            item = _error_item(provider, "查询失败：%s" % type(exc).__name__, started)
        _CACHE[pid] = (time.monotonic(), item)
        return item


def summary(refresh: bool = False) -> Dict[str, Any]:
    """所有「支持用量查询」的供应商（providers.yaml 里 `usage_api: new_api`）。"""
    items: List[Dict[str, Any]] = []
    for provider in config.image_providers(with_keys=True):
        if (provider.get("usage_api") or "") != "new_api":
            continue
        items.append(_cached(provider, refresh))
    return dict(items=items, fetched_at=db.now(), cache_seconds=CACHE_SECONDS,
                note="供应商侧累计用量来自面板的 OpenAI 兼容计费接口（New API）；与本地账本是两个口径，不可直接相等。")
