# -*- coding: utf-8 -*-
"""粉笔练习 PDF -> 复盘 docx 一键流水线

用法：
    python fb_pipeline.py <input.pdf> [--title "标题"] [--out xxx.docx]

流程：
    1. fb_parse.py 解析 PDF -> <pdf>_parsed.json + <pdf>_imgs/
    2. 读取 JSON，按错因模板生成 docx
    3. 输出 <out>，并打印错题清单供人工补充解析

注意：错因分析和解析文字需要人工/AI 撰写，脚本只负责：
    - 结构化提取（题干、选项、答案、正误）
    - 统计（正确率、模块分布、错题列表）
    - docx 骨架（基本情况、错因分布占位、逐题题干表格、训练计划占位）
后续由 AI 填充 analysis/colloc 字段，或直接编辑生成的 docx。
"""
import argparse
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fb_docx_lib import Builder, NAVY, GREY, RED  # noqa: E402

TYPE_ORDER = ["资料分析", "数学运算", "逻辑判断", "图形推理", "类比推理", "定义判断",
              "言语理解", "常识判断", "待确认"]


def run_parser(pdf):
    py = sys.executable
    script = os.path.join(HERE, "fb_parse.py")
    r = subprocess.run([py, script, pdf], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        raise SystemExit("解析失败")
    out = os.path.splitext(pdf)[0] + "_parsed.json"
    with open(out, encoding="utf-8") as f:
        return json.load(f), out


def module_stats(questions):
    agg = {}
    for q in questions:
        t = q["type"]
        a = agg.setdefault(t, {"total": 0, "right": 0, "wrong": []})
        a["total"] += 1
        if q["right"]:
            a["right"] += 1
        else:
            a["wrong"].append(q["no"])
    ordered = []
    for t in TYPE_ORDER:
        if t in agg:
            ordered.append((t, agg.pop(t)))
    for t, v in agg.items():
        ordered.append((t, v))
    return ordered


def get_a(analyses, no):
    """JSON 的键是字符串，题号是 int，两种都兼容。"""
    return analyses.get(str(no)) or analyses.get(no) or {}


def build(data, title, out_path, analyses=None):
    analyses = analyses or {}
    b = Builder()
    stats = data["stats"]
    qs = data["questions"]
    wrong = [q for q in qs if q["right"] is False]
    mods = module_stats(qs)

    b.H(title, 0)
    b.P("粉笔智能组卷 %d 题 · 错题复盘 · 错因归类" % stats["total"], 12, False, GREY, after=14)

    # 一、基本情况
    b.H("一、基本情况", 1)
    rows = [
        ["项目", "内容"],
        ["来源", os.path.basename(data["file"])],
        ["题量", "%d 题（智能组卷，题型混合）" % stats["total"]],
        ["答对", "%d 题" % stats["right"]],
        ["答错", "%d 题（%s）" % (stats["wrong"], "、".join("Q%d" % n for n in stats["wrong_list"]) or "无")],
        ["正确率", "%d / %d = %.1f%%" % (stats["right"], stats["total"], stats["rate"])],
        ["模块分布", "、".join("%s %d 题" % (t, v["total"]) for t, v in mods)],
        ["错题分布", "、".join("%s %d 题" % (t, len(v["wrong"])) for t, v in mods if v["wrong"]) or "无"],
    ]
    b.TABLE(rows, widths=[3.4, 13.0])

    if wrong:
        b.P(
            "核心结论：本卷正确率 %.1f%%，错题 %d 道。错因分析见下。"
            % (stats["rate"], stats["wrong"]),
            10.5, True, RED, after=10,
        )
    else:
        b.P("本卷全对，无需复盘。", 10.5, True, RED, after=10)

    b.P(
        "按模块拆开看：" + "；".join(
            "%s %d/%d（%.0f%%）" % (t, v["right"], v["total"],
                                   v["right"] / v["total"] * 100)
            for t, v in mods
        ) + "。智能组卷题型随机，正确率不宜直接与套卷横向比较。",
        10.5, after=10,
    )

    # 二、错因分布
    b.H("二、错因分布", 1)
    dist = []
    for q in wrong:
        a = get_a(analyses, q["no"])
        dist.append([a.get("cause", "待补充"), "Q%d" % q["no"], a.get("note", "")])
    if dist:
        b.TABLE([["错因类型", "题号", "说明"]] + dist, widths=[5.0, 2.4, 9.0])
    else:
        b.P("无错题。", 10.5, after=6)

    # 三、逐题复盘
    b.H("三、逐题复盘", 1)
    if not wrong:
        b.P("本卷无错题。", 10.5)
    for q in wrong:
        a = get_a(analyses, q["no"])
        stem = q["stem"] + "\n\n" + "\n".join(
            "%s. %s" % (k, v) for k, v in sorted(q["options"].items())
        )
        b.QUESTION(
            str(q["no"]),
            a.get("tag", q["type"]),
            q["type"],
            stem,
            q["my"] or "（未作答）",
            q["answer"] or "（缺）",
            a.get("cause", "待补充"),
            a.get("analysis") or ["【待补充解析】"],
            a.get("colloc"),
        )

    # 四、做对但值得记录
    right_qs = [q for q in qs if q["right"] is True]
    if right_qs:
        b.H("四、做对但值得记录的题", 1)
        for q in right_qs:
            a = get_a(analyses, q["no"])
            if not a.get("note"):
                continue
            b.P("Q%d（%s，%s ✓）" % (q["no"], q["type"], q["my"]), 10.5, True, NAVY, after=3)
            b.P(a["note"], 10.5, indent=0.5, after=8)
        b.P("其余 %d 题答对，无特别记录。" % max(0, len(right_qs) - sum(
            1 for q in right_qs if get_a(analyses, q["no"]).get("note"))), 10.5, after=10)

    # 五、训练计划
    b.H("五、训练计划", 1)
    plans = analyses.get("_plan") or ["【待补充训练计划】"]
    for p in plans:
        b.NUM(p)

    b.P(
        "附：本复盘基于粉笔 App 导出的 PDF 自动解析生成。题干、选项、正确答案、用户答案均来自 PDF 文本层，未经 OCR。"
        "题型由规则推断，智能组卷题型随机，模块统计仅供参考。",
        9.5, False, GREY, after=0, before=12,
    )

    b.save(out_path)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--title", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--analyses", default=None, help="错因分析 JSON（可选）")
    args = ap.parse_args()

    data, jpath = run_parser(args.pdf)
    analyses = {}
    if args.analyses and os.path.exists(args.analyses):
        with open(args.analyses, encoding="utf-8") as f:
            analyses = json.load(f)

    title = args.title or os.path.splitext(os.path.basename(args.pdf))[0] + " · 复盘"
    out = args.out or os.path.splitext(args.pdf)[0] + "_复盘.docx"
    path = build(data, title, out, analyses)

    print("解析: %s" % jpath)
    print("输出: %s (%d B)" % (path, os.path.getsize(path)))
    st = data["stats"]
    print("正确率 %.1f%%（%d/%d），错题: %s"
          % (st["rate"], st["right"], st["total"],
             "、".join("Q%d" % n for n in st["wrong_list"]) or "无"))


if __name__ == "__main__":
    main()
