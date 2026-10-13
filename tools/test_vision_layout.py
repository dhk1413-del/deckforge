"""视觉识别 → 版面块的映射回归（离线、不联网、不花钱）。

锁定的都是本轮真机排障挖出来的坑：
- qwen3-vl-flash **无视"用 0-1 比例"的要求，返回源图像素**（x=32,w=300 对应 1200×675）→ 必须自适应归一化
- 脏块（空文本/宽高为 0/非数字）必须丢弃，绝不猜位置
- 图表数据可能藏在 components[].data 里（不只在顶层 chart_data）
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from server.app.pipeline import (  # noqa: E402
    blocks_from_vision, charts_from_vision, shapes_from_vision, title_and_points,
)

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("  %s %s%s" % ("✅" if ok else "❌", name, (" — " + detail) if detail else ""))


def main():
    print("[1] 坐标单位自适应（逐块判定）：像素 vs 比例 vs 两者混在一份返回里")
    px = dict(texts=[dict(text="标题", x=32, y=104, w=300, h=60, role="title")],
              components=[dict(type="chart", x=410, y=100, w=960, h=690)])
    b = blocks_from_vision(px, 1200, 675)[0]
    check("像素坐标 → 归一化（x≈0.027, w≈0.25）", abs(b["x"] - 0.0267) < 0.002 and abs(b["w"] - 0.25) < 0.002,
          "x=%.4f w=%.4f" % (b["x"], b["w"]))
    prop = dict(texts=[dict(text="标题", x=0.03, y=0.15, w=0.25, h=0.09, role="title")])
    b2 = blocks_from_vision(prop, 1200, 675)[0]
    check("比例坐标保持原值（x=0.03）", abs(b2["x"] - 0.03) < 1e-6 and abs(b2["w"] - 0.25) < 1e-6)
    mixed = dict(texts=[dict(text="像素块", x=32, y=104, w=300, h=60), dict(text="比例块", x=0.6, y=0.2, w=0.3, h=0.08)])
    got_mixed = blocks_from_vision(mixed, 1200, 675)
    check("同一份返回混着两种单位也能各自算对",
          len(got_mixed) == 2 and abs(got_mixed[0]["w"] - 0.25) < 0.002 and abs(got_mixed[1]["x"] - 0.6) < 1e-6,
          str([(g["text"], g["x"], g["w"]) for g in got_mixed]))
    check("缺图片尺寸时按比例处理（不炸）", len(blocks_from_vision(prop, 0, 0)) == 1)

    print("[2] 脏块丢弃（不猜位置）")
    dirty = dict(texts=[dict(text="", x=0.1, y=0.1, w=0.2, h=0.1), dict(text="  ", x=0.1, y=0.1, w=0.2, h=0.1),
                        dict(text="零宽", x=0.1, y=0.1, w=0, h=0.1), dict(text="零高", x=0.1, y=0.1, w=0.2, h=0),
                        dict(text="非数字", x="a", y="b", w="c", h="d"), dict(text="好块", x=0.1, y=0.2, w=0.3, h=0.08),
                        "不是字典"])
    got = blocks_from_vision(dirty, 1200, 675)
    check("只留下 1 个合法块", len(got) == 1 and got[0]["text"] == "好块", str([g["text"] for g in got]))

    print("[3] 越界裁剪到画布内")
    out = dict(texts=[dict(text="越界", x=0.9, y=0.9, w=0.5, h=0.5)])
    rect = blocks_from_vision(out, 1200, 675)[0]
    check("x+w ≤ 1 且 y+h ≤ 1", rect["x"] + rect["w"] <= 1.0001 and rect["y"] + rect["h"] <= 1.0001,
          str(rect))

    print("[4] 阅读顺序：先上后下，同行左到右")
    order = dict(texts=[dict(text="右下", x=0.6, y=0.5, w=0.2, h=0.08), dict(text="左上", x=0.1, y=0.1, w=0.2, h=0.08),
                        dict(text="右上", x=0.6, y=0.1, w=0.2, h=0.08)])
    check("顺序 = 左上/右上/右下",
          [x["text"] for x in blocks_from_vision(order, 1200, 675)] == ["左上", "右上", "右下"])

    print("[5] 标题与正文：不改写文字")
    blocks = blocks_from_vision(dict(texts=[
        dict(text="正文一", x=0.1, y=0.4, w=0.3, h=0.08, role="body"),
        dict(text="大标题", x=0.1, y=0.05, w=0.5, h=0.1, role="title")]), 1200, 675)
    title, points = title_and_points(blocks)
    check("优先 role=title", title == "大标题" and points == ["正文一"], "%r %s" % (title, points))
    blocks2 = blocks_from_vision(dict(texts=[
        dict(text="上面这行", x=0.1, y=0.05, w=0.3, h=0.08, role="body"),
        dict(text="下面这行", x=0.1, y=0.4, w=0.3, h=0.08, role="body")]), 1200, 675)
    t2, p2 = title_and_points(blocks2)
    check("无 title 时取最上块", t2 == "上面这行" and p2 == ["下面这行"])
    check("空块 → 空标题", title_and_points([]) == ("", []))

    print("[6] 形状区域：只留 card/shape/chart，同样归一化")
    shapes = shapes_from_vision(dict(components=[
        dict(type="card", x=410, y=100, w=400, h=300), dict(type="icon", x=10, y=10, w=50, h=50),
        dict(type="chart", x=0.5, y=0.1, w=0.4, h=0.6)]), 1200, 675)
    check("card 与 chart 保留、icon 丢弃", [s["type"] for s in shapes] == ["card", "chart"], str([s["type"] for s in shapes]))
    check("card 归一化正确", abs(shapes[0]["x"] - 0.3417) < 0.002 and abs(shapes[0]["w"] - 0.3333) < 0.002)

    print("[7] 图表抽取：顶层 chart_data 与 components[].data 都要")
    charts = charts_from_vision(dict(
        chart_data=[dict(title="顶层", labels=["1月", "2月"], series=[dict(name="A", values=[1, 2])])],
        components=[dict(type="chart", x=0, y=0, w=1, h=1,
                         data=dict(title="组件里", labels=["3月", "4月"],
                                   series=[dict(name="B", data=[3, 4])]))]))
    check("两组图表都抽到", len(charts) == 2, str([c["title"] for c in charts]))
    check("组件里的 data 被归一成 values", charts[1]["series"][0]["values"] == [3.0, 4.0], str(charts[1]["series"]))
    check("无图表时返回空列表", charts_from_vision({}) == [])
    print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
