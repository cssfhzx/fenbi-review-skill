# -*- coding: utf-8 -*-
"""粉笔「快速智能练习」PDF -> 结构化 JSON

用法:
    python fb_parse.py <input.pdf> [output.json]

输出字段:
    questions[]: no / page / type / stem / options{A..D} / my / answer / right / images[]
    materials[]: page / text / images[]     （资料分析的材料段与图表）
    stats:       total / right / wrong / rate / wrong_list
"""
import re
import os
import sys
import json

sys.stdout.reconfigure(encoding="utf-8")
import pymupdf

FOOT_PAT = re.compile(r"^第\s*\d+\s*页[，,]\s*共\s*\d+\s*页$")
FOOT_MARK = "本试卷由粉笔用户"
QNUM = re.compile(r"^(\d+)\.$")
ANS_R = re.compile(r"^正确答案\s*[：:]\s*([A-D])$")
ANS_M = re.compile(r"^你的答案\s*[：:]\s*([A-D])$")
OPT = re.compile(r"^([A-D])[.．、]\s*(.*)$")


def collect_lines(doc):
    raw = []
    for pno, page in enumerate(doc):
        d = page.get_text("dict")
        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue
            for ln in b.get("lines", []):
                txt = "".join(s["text"] for s in ln["spans"]).strip()
                if not txt:
                    continue
                x0, y0, x1, y1 = ln["bbox"]
                raw.append({
                    "page": pno + 1,
                    "y": round(y0, 1),
                    "x": round(x0, 1),
                    "sz": round(ln["spans"][0]["size"], 1),
                    "t": txt,
                })

    # 动态识别页眉/页脚：只认页面顶部/底部的重复行（按 y 坐标），不按出现次数
    # 页眉：y < 60pt；页脚：y > 页高 - 60pt
    heights = {}
    for pno, page in enumerate(doc):
        heights[pno + 1] = page.rect.height

    pages_by_text = {}
    for r in raw:
        t = r["t"]
        h = heights.get(r["page"], 842)
        at_edge = (r["y"] < 60) or (r["y"] > h - 60)
        if not at_edge:
            continue
        pages_by_text.setdefault(t, set()).add(r["page"])
    chrome = {t for t, ps in pages_by_text.items() if len(ps) >= 3 and len(t) < 60}

    out = []
    for r in raw:
        t = r["t"]
        if t in chrome or FOOT_PAT.match(t) or FOOT_MARK in t:
            continue
        out.append(r)
    out.sort(key=lambda r: (r["page"], r["y"], r["x"]))
    return out


def collect_images(doc, imgdir):
    os.makedirs(imgdir, exist_ok=True)
    out = []
    for pno, page in enumerate(doc):
        for idx, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            try:
                base = doc.extract_image(xref)
            except Exception:
                continue
            w, h = base["width"], base["height"]
            if w < 60 or h < 60:
                continue
            fn = os.path.join(imgdir, "p%d_%d_%dx%d.%s" % (pno + 1, idx, w, h, base["ext"]))
            if not os.path.exists(fn):
                open(fn, "wb").write(base["image"])
            rects = page.get_image_rects(xref)
            bb = rects[0] if rects else None
            out.append({
                "page": pno + 1,
                "file": fn,
                "w": w,
                "h": h,
                "y": round(bb.y0, 1) if bb else None,
                "x": round(bb.x0, 1) if bb else None,
            })
    return out


def group_options(opt_lines):
    """同一 y 上的 A/B/C/D 是同一行选项，按 x 排序拆开。"""
    rows = []
    for ln in opt_lines:
        if rows and abs(ln["y"] - rows[-1][0]["y"]) <= 4:
            rows[-1].append(ln)
        else:
            rows.append([ln])
    opts = {}
    for row in rows:
        for ln in sorted(row, key=lambda r: r["x"]):
            m = OPT.match(ln["t"])
            if not m:
                continue
            key, val = m.group(1), m.group(2).strip()
            if key in opts and val:
                opts[key] = (opts[key] + " " + val).strip()
            elif key not in opts:
                opts[key] = val
    return opts


def split_block(block_lines):
    ans = mine = None
    body = []
    for ln in block_lines:
        t = ln["t"]
        m = ANS_R.match(t)
        if m:
            ans = m.group(1)
            continue
        m = ANS_M.match(t)
        if m:
            mine = m.group(1)
            continue
        body.append(ln)

    first_opt = None
    for i, ln in enumerate(body):
        if OPT.match(ln["t"]):
            first_opt = i
            break

    if first_opt is None:
        return "\n".join(l["t"] for l in body), {}, "", []

    stem_lines = body[:first_opt]
    tail = body[first_opt:]
    opt_lines = [l for l in tail if OPT.match(l["t"])]
    extra = [l for l in tail if not OPT.match(l["t"])]

    stem = "\n".join(l["t"] for l in stem_lines)
    opts = group_options(opt_lines)
    extra_txt = "\n".join(l["t"] for l in extra)
    return stem, opts, extra_txt, extra


def guess_type(stem, opts, n_img):
    s = stem.replace("\n", "").replace("\xa0", "")
    empty_opts = (not opts) or all(not (v or "").strip() for v in opts.values())
    # 图形推理：题干极短、选项为空或纯图片
    if len(s) < 30 and empty_opts:
        return "图形推理"
    # 语句排序
    if re.search(r"[①②③④⑤⑥]", s) and re.search(r"排列|语序|顺序", s):
        return "语句排序"
    # 逻辑填空：「依次填入」或「填入画横线」（两空及以上）/「填入划横线」
    if ("依次填入" in s and ("横线" in s or "划线" in s)) or "填入画横线" in s or "填入划横线" in s:
        return "逻辑填空"
    # 语句填空：单空，填一句
    if re.search(r"填入.*最恰当的一句", s):
        return "语句填空"
    # 标题填入
    if "标题" in s:
        return "标题填入"
    # 资料分析强信号（先于片段阅读：资料题常带「说法正确/推出」等问法）
    STRONG = ("根据资料", "上述资料", "根据以下资料", "根据所给资料", "表1", "图1",
              "同比", "同比增长", "占比", "比重", "百分点", "年均", "平均每家",
              "约占", "约为")
    if any(k in s for k in STRONG):
        return "资料分析"
    # 片段阅读按问法细分（题干结尾的问法句）
    tail = s[-60:]
    if re.search(r"意在说明|意图|想要说明|意在强调|旨在", tail):
        return "片段阅读-意图判断"
    if re.search(r"主要讲述|主要介绍|主要说明|主要谈论|主要讨论|主要阐述|主旨|概括最准确|重在说明|中心|解答了|回答了", tail):
        return "片段阅读-中心理解"
    if re.search(r"说法错误|说法正确|判断错误|判断正确|理解正确|理解错误|理解不准确|理解准确"
                 r"|符合文意|不符合|无法推出|可以推出|能够推出|得到支持|未提及|没有提及|未涉及|细节", tail):
        return "片段阅读-细节判断"
    if re.search(r"接下来|下文", tail):
        return "语句表达-下文推断"
    # 资料分析弱信号（「根据这段文字」太泛，片段阅读也常用，已移除）
    for k in ("根据以上文段", "根据以下材料", "根据以下图表", "下降了", "上升了"):
        if k in s:
            return "资料分析"
    # 逻辑判断
    for k in ("需要补充的前提", "最能削弱", "最能加强", "由此可以推出", "如果为真",
              "最能质疑", "最能解释", "结论成立", "前提是", "以下哪项", "假设"):
        if k in s:
            return "逻辑判断"
    # 类比推理
    if len(s) < 40 and re.search(r"[：:]", s):
        return "类比推理"
    # 数学运算
    if re.search(r"\d", s) and re.search(r"(多少|几人|几天|小时|人数|效率|完成|千米|问)", s):
        return "数学运算"
    if n_img:
        return "图形推理"
    return "待确认"


def main():
    if len(sys.argv) < 2:
        print("usage: python fb_parse.py <input.pdf> [output.json]")
        sys.exit(1)
    pdf = sys.argv[1]
    out_json = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(pdf)[0] + "_parsed.json"
    imgdir = os.path.splitext(pdf)[0] + "_imgs"

    doc = pymupdf.open(pdf)
    lines = collect_lines(doc)
    images = collect_images(doc, imgdir)
    npages = doc.page_count
    doc.close()

    # 按题号切段
    segs, cur, pre = [], None, []
    for ln in lines:
        m = QNUM.match(ln["t"])
        if m and ln["x"] < 62:
            if cur:
                segs.append(cur)
            cur = {"no": int(m.group(1)), "page": ln["page"], "lines": []}
        elif cur is not None:
            cur["lines"].append(ln)
        else:
            pre.append(ln)
    if cur:
        segs.append(cur)

    questions = []
    materials = []
    if pre:
        materials.append({
            "page": pre[0]["page"],
            "text": "\n".join(l["t"] for l in pre),
            "images": [i["file"] for i in images if i["page"] == pre[0]["page"]],
        })

    for seg in segs:
        stem, opts, extra_txt, extra = split_block(seg["lines"])
        qimg = [i["file"] for i in images if i["page"] == seg["page"]]
        if extra_txt:
            materials.append({"page": seg["page"], "text": extra_txt, "images": []})
        ans = mine = None
        for ln in seg["lines"]:
            m = ANS_R.match(ln["t"])
            if m:
                ans = m.group(1)
            m = ANS_M.match(ln["t"])
            if m:
                mine = m.group(1)
        questions.append({
            "no": seg["no"],
            "page": seg["page"],
            "type": guess_type(stem, opts, len(qimg)),
            "stem": stem,
            "options": opts,
            "my": mine,
            "answer": ans,
            "right": (mine == ans) if (mine and ans) else None,
            "images": qimg,
        })

    wrong = [q["no"] for q in questions if q["right"] is False]
    total = len(questions)
    nright = sum(1 for q in questions if q["right"] is True)
    result = {
        "file": os.path.abspath(pdf),
        "pages": npages,
        "questions": questions,
        "materials": materials,
        "stats": {
            "total": total,
            "right": nright,
            "wrong": len(wrong),
            "rate": round(nright / total * 100, 1) if total else 0,
            "wrong_list": wrong,
        },
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("解析完成: %s" % out_json)
    print("共 %d 页 / %d 题，答对 %d，答错 %d，正确率 %.1f%%"
          % (npages, total, nright, len(wrong), result["stats"]["rate"]))
    for q in questions:
        flag = "√" if q["right"] else ("×" if q["right"] is False else "?")
        print("  Q%-3d [%-6s] %s  我=%s 正=%s  %s"
              % (q["no"], q["type"], flag, q["my"], q["answer"], q["stem"][:34].replace("\n", "")))


if __name__ == "__main__":
    main()
