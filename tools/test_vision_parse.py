#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视觉解析（Qwen-VL 等 OpenAI 兼容视觉模型）输出解析的离线回归测试。

跑法：.venv/bin/python tools/test_vision_parse.py
不联网、不花钱：只测 parse_vision_json() 的宽容度。

背景（真机实测到的缺陷）：某思考型视觉模型在 max_tokens=6000 时会返回
`finish_reason=length` 且 **content 为空字符串**，另一些情况下会把整个对象包在
markdown 里、或在 JSON 前后带解释、或被截断在字符串中间。原来的实现只做
`json.loads()`，一旦失败整次视觉解析就被丢掉、静默降级成「未做视觉解析」。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "server"))
from app.providers import parse_vision_json  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %s %s%s" % ("✅" if cond else "❌", name, (" — " + detail) if detail else ""))


GOOD = ('{"texts":[{"text":"项目概述","x":0.05,"y":0.07,"w":0.2,"h":0.09,"role":"title"},'
        '{"text":"面向高校校园零售场景","x":0.1,"y":0.31,"w":0.3,"h":0.05,"role":"body"}],'
        '"components":[{"type":"card","x":0.05,"y":0.28,"w":0.28,"h":0.3}],'
        '"chart_data":[{"title":"月度订单","labels":["第1月","第2月"],"series":[{"name":"订单量","values":[120,260]}]}],'
        '"warnings":[]}')

print("\n[1] 正常输出")
d = parse_vision_json(GOOD)
check("严格 JSON 直接解析", bool(d) and len(d["texts"]) == 2)
check("图表数据保留", bool(d) and d["chart_data"][0]["labels"] == ["第1月", "第2月"])

print("\n[2] markdown 代码围栏")
d = parse_vision_json("```json\n" + GOOD + "\n```")
check("围栏包裹仍可解析", bool(d) and len(d["texts"]) == 2)

print("\n[3] JSON 前后带解释文字")
d = parse_vision_json("好的，以下是分析结果：\n" + GOOD + "\n希望对你有帮助。")
check("裁到最外层 {} 后解析成功", bool(d) and len(d["texts"]) == 2)

print("\n[4] 被截断（数组元素写到一半）")
truncated = GOOD[: GOOD.rfind('{"type":"card"')]          # 断在 components 元素中间
d = parse_vision_json(truncated)
check("截断输出仍能救回已完整的部分", bool(d), "救回 texts=%s" % (len(d["texts"]) if d else None))
check("已完整的 texts 全部保留", bool(d) and len(d["texts"]) == 2)

print("\n[5] 截断在字符串中间")
d = parse_vision_json(GOOD[: GOOD.find("面向高校校园零售场景") + 6])
check("未闭合字符串被补全后仍可解析", bool(d), "texts=%s" % (len(d["texts"]) if d else None))

print("\n[6] 空输出（真机实测：预算被推理吃光 → content 为空）")
check("空字符串返回 None（由调用方走降级+重试）", parse_vision_json("") is None)
check("纯空白返回 None", parse_vision_json("   \n  ") is None)

print("\n[7] 完全不是 JSON")
check("散文输出返回 None", parse_vision_json("这张页面包含标题与四个卡片，未发现图表数据。") is None)

print("\n[8] 中文与转义引号不被破坏")
d = parse_vision_json('{"texts":[{"text":"他说：\\"数据是 37%\\"","x":0.1,"y":0.1,"w":0.2,"h":0.05,"role":"body"}],"chart_data":[]}')
check("转义引号原样保留", bool(d) and '数据是 37%' in d["texts"][0]["text"],
      d["texts"][0]["text"] if d else "")
d2 = parse_vision_json('{"texts":[{"text":"未闭合的中文说明","x":0.1')
check("中文截断可补齐", bool(d2) and d2["texts"][0]["text"] == "未闭合的中文说明")

print("\n[9] 图表数据归一化（真机实测的三种脏形状 → 唯一形状）")
from app.providers import normalize_chart_data  # noqa: E402

# P2 真机原样：series 里键名是 data 而不是 values，且有两个系列
p2_raw = [{"title": "各校区月度订单量对比", "labels": ["1月", "2月", "3月"],
           "series": [{"name": "试点校区一", "data": [800, 1200, 1600]},
                      {"name": "试点校区二", "data": [600, 950, 1300]}]}]
n = normalize_chart_data(p2_raw)
check("data 键名被识别为 values", bool(n) and n[0]["series"][0]["values"] == [800.0, 1200.0, 1600.0])
check("多系列全部保留", bool(n) and len(n[0]["series"]) == 2)
check("系列名保留", bool(n) and n[0]["series"][1]["name"] == "试点校区二")

# P6 真机原样：series 直接是数字数组
p6_raw = [{"title": "平均排队时长", "labels": ["优化前", "优化后"], "series": [8.5, 2.1]}]
n6 = normalize_chart_data(p6_raw)
check("裸数字数组被包成系列", bool(n6) and n6[0]["series"][0]["values"] == [8.5, 2.1])
check("长度与 labels 一致", bool(n6) and len(n6[0]["series"][0]["values"]) == len(n6[0]["labels"]))

print("\n[10] 归一化必须挡住「凑不出来」的数据")
check("labels 少于 2 个 → 丢弃", normalize_chart_data([{"labels": ["只有一个"], "series": [[1]]}]) == [])
check("长度对不上 → 丢弃", normalize_chart_data([{"labels": ["a", "b", "c"], "series": [[1, 2]]}]) == [])
check("非数字值 → 丢弃", normalize_chart_data([{"labels": ["a", "b"], "series": [["x", "y"]]}]) == [])
check("labels 与 values 同步截断到 8 条", (lambda r: len(r[0]["labels"]) == 8 and len(r[0]["series"][0]["values"]) == 8)(
    normalize_chart_data([{"labels": [str(i) for i in range(12)], "series": [list(range(12))]}])))
check("空输入安全", normalize_chart_data(None) == [] and normalize_chart_data("乱写的") == [])

print("\n" + "=" * 60)
print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
for x in FAIL:
    print("  -", x)
sys.exit(1 if FAIL else 0)
