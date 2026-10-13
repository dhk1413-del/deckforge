#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c2pa_check.py —— AI 图片来源取证：从 PNG 的 caBX 块（C2PA 内容凭证）反查生成模型/厂商。

用法：
    python3 c2pa_check.py <图片.png ...>
    python3 c2pa_check.py <文件.pptx>          # 也支持直接查 PPTX/DOCX/XLSX 内嵌媒体
依赖：cbor2（可选，缺失时退化为字符串提取）
"""
import sys, os, struct, zipfile

SIG = [b"gpt-image", b"OpenAI Media Service", b"Seedream", b"Doubao", b"ByteDance",
       b"Google", b"Gemini", b"Nano Banana", b"Qwen", b"wanx", b"Kolors", b"FLUX", b"ComfyUI",
       b"SynthID", b"Midjourney"]


def find_cabx(data: bytes):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    i = 8
    while i + 8 <= len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        if typ == b"caBX":
            return data[i + 8:i + 8 + ln]
        i += 12 + ln
        if typ == b"IEND":
            break
    return None


def report(name, data):
    blob = find_cabx(data)
    print("── %s" % name)
    if not blob:
        hits = [s.decode() for s in SIG if s in data]
        print("   无 caBX（C2PA）块；文本签名命中: %s" % (hits or "无"))
        return
    print("   ✅ 发现 C2PA 清单，caBX 块 %s 字节" % format(len(blob), ","))
    try:
        import cbor2
    except ImportError:
        for s in SIG:
            if s in blob:
                k = blob.find(s)
                print("   （无 cbor2）%s: %r" % (s.decode(), blob[max(0, k - 30):k + 80]))
        return
    for off in range(0, min(len(blob), 6000)):
        try:
            obj = cbor2.loads(blob[off:])
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        keys = {(k.decode("utf-8", "replace") if isinstance(k, bytes) else str(k)) for k in obj}
        if keys & {"actions", "claim_generator_info", "assertions"}:
            def walk(o, ind=1):
                pad = "   " * ind
                if isinstance(o, dict):
                    for k, v in o.items():
                        k = k.decode("utf-8", "replace") if isinstance(k, bytes) else str(k)
                        if k == "icon":
                            continue
                        if isinstance(v, (dict, list)):
                            print("%s%s:" % (pad, k)); walk(v, ind + 1)
                        else:
                            print("%s%s = %s" % (pad, k, (v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v))[:120]))
                elif isinstance(o, list):
                    for n, v in enumerate(o[:8]):
                        if isinstance(v, (dict, list)):
                            print("%s[%d]" % (pad, n)); walk(v, ind + 1)
                        else:
                            print("%s[%d] %s" % (pad, n, str(v)[:120]))
            walk(obj)
            return


def main(paths):
    for p in paths:
        if not os.path.exists(p):
            print("── %s: 不存在" % p); continue
        if p.lower().endswith((".pptx", ".docx", ".xlsx")):
            z = zipfile.ZipFile(p)
            media = [n for n in z.namelist() if "/media/" in n]
            print("== %s 内嵌媒体 %d 个 ==" % (os.path.basename(p), len(media)))
            for n in media:
                report("%s::%s" % (os.path.basename(p), n), z.read(n))
        else:
            report(os.path.basename(p), open(p, "rb").read())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
    else:
        main(sys.argv[1:])
