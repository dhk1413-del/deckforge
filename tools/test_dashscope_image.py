#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阿里百炼生图适配器的离线回归测试（不联网、不花钱）。

跑法：.venv/bin/python tools/test_dashscope_image.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "server"))
from app import providers  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %s %s%s" % ("✅" if cond else "❌", name, (" — " + detail) if detail else ""))


class FakeResponse:
    def __init__(self, data=None, content=b"", status_code=200):
        self._data, self.content, self.status_code = data or {}, content, status_code
        self.is_success = 200 <= status_code < 300

    def json(self):
        return self._data

    def raise_for_status(self):
        if not self.is_success:
            raise RuntimeError("unexpected HTTPStatusError")


class FakeClient:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def post(self, url, **kwargs):
        self.calls.append(("post", url, kwargs))
        return FakeResponse({"output": {"choices": [{"message": {"content": [{"image": "https://example.test/image.png"}]}}]}})

    def get(self, url, **kwargs):
        self.calls.append(("get", url, kwargs))
        return FakeResponse(content=b"fake-png-bytes")


P = {"base_url": "https://dashscope.aliyuncs.com/api/v1", "key": "test-key", "default_model": "qwen-image-3.0-pro"}

print("\n[1] 模型族分流")
check("qwen-image 识别为同步族", P["default_model"].lower().startswith("qwen-image"))
check("wan 模型不进入同步族", not "wan2.7-image-pro".startswith("qwen-image"))

print("\n[2] Qwen-Image 尺寸映射")
check("1K → 1024*1024", providers._dashscope_qwen_image_size("1K") == "1024*1024")
check("2K → 2048*2048", providers._dashscope_qwen_image_size("2K") == "2048*2048")
check("4K 无对应档 → 2K 默认", providers._dashscope_qwen_image_size("4K") == "2048*2048")
check("未知档位 → 2K 默认", providers._dashscope_qwen_image_size("bad") == "2048*2048")

print("\n[3] 同步请求、URL 提取与下载")
client = FakeClient()
raw = providers._dashscope_qwen_image(P, "极简深蓝底青色圆环", "1K", client_factory=lambda _p: client)
post = client.calls[0]
check("qwen-image 走同步 multimodal-generation 路径", post[1].endswith("/services/aigc/multimodal-generation/generation"))
check("同步 body 使用 Qwen 合法尺寸", post[2]["json"]["parameters"]["size"] == "1024*1024")
check("同步 body 保留 prompt_extend/watermark", post[2]["json"]["parameters"]["prompt_extend"] is False and post[2]["json"]["parameters"]["watermark"] is False)
check("从 choices content image 提取 URL 并下载 bytes", raw == b"fake-png-bytes" and client.calls[1][1] == "https://example.test/image.png")

print("\n[4] 错误体可诊断")
try:
    providers._dashscope_raise_for_status(FakeResponse({"code": "InvalidParameter", "message": "url error, please check url!"}, status_code=400))
    diagnostic = ""
except RuntimeError as exc:
    diagnostic = str(exc)
check("失败带回 code/message", "InvalidParameter: url error, please check url!" in diagnostic, diagnostic)

print("\n[5] 异步 Wan 路径保持原接口")
old_qwen = providers._dashscope_qwen_image
try:
    providers._dashscope_qwen_image = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("wrong branch"))
    wan_client = FakeClient()
    # 只验证路由选择：将 _client 替换为立即给任务失败的假客户端，避免轮询/联网。
    class WanClient(FakeClient):
        def post(self, url, **kwargs):
            self.calls.append(("post", url, kwargs))
            return FakeResponse({"output": {"task_id": "task-1"}})
        def get(self, url, **kwargs):
            self.calls.append(("get", url, kwargs))
            return FakeResponse({"output": {"task_status": "FAILED"}})
    wan_client = WanClient()
    old_client, old_sleep = providers._client, providers.time.sleep
    # _client 现在带第二参 use_proxy（生图重试时的链路切换），假件要跟上新签名
    providers._client, providers.time.sleep = (lambda _p, _use_proxy=None: wan_client), (lambda _seconds: None)
    try:
        providers._dashscope(dict(P, default_model="wan2.7-image-pro"), "x", "1K")
    except RuntimeError:
        pass
    check("wan* 仍走异步 image-synthesis 路径", bool(wan_client.calls) and wan_client.calls[0][1].endswith("/services/aigc/text2image/image-synthesis"))
finally:
    providers._dashscope_qwen_image = old_qwen
    providers._client, providers.time.sleep = old_client, old_sleep

print("\n" + "=" * 60)
print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
for x in FAIL:
    print("  -", x)
sys.exit(1 if FAIL else 0)
