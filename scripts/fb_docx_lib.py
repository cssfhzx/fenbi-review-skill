# -*- coding: utf-8 -*-
"""粉笔练习 -> 复盘 docx 生成器（模板：逻辑填空实战训练（二/三）格式）"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

FONT = "微软雅黑"
NAVY = RGBColor(0x1F, 0x3B, 0x5C)
GREY = RGBColor(0x59, 0x59, 0x59)
RED = RGBColor(0xB0, 0x2A, 0x2A)
BLUE = RGBColor(0x1A, 0x4D, 0x7A)


def new_doc():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.left_margin = Cm(2.2)
    sec.right_margin = Cm(2.2)
    sec.top_margin = Cm(2.0)
    sec.bottom_margin = Cm(2.0)
    return doc


def set_font(run, size=10.5, bold=False, color=None, name=FONT):
    run.font.name = name
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    for k in ("w:eastAsia", "w:ascii", "w:hAnsi"):
        rFonts.set(qn(k), name)
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


import re


def add_rich(par, text, size=10.5, bold=False, color=None, name=FONT):
    """把 **xx** 解析成加粗 run，其余正常。"""
    parts = re.split(r"\*\*(.+?)\*\*", text)
    for i, seg in enumerate(parts):
        if not seg:
            continue
        is_bold = bold or (i % 2 == 1)
        set_font(par.add_run(seg), size, is_bold, color, name)


class Builder:
    def __init__(self):
        self.doc = new_doc()

    def H(self, text, level=1):
        p = self.doc.add_heading("", level=level)
        size = {0: 24, 1: 16, 2: 13}.get(level, 12)
        set_font(p.add_run(text), size, True, NAVY)
        p.paragraph_format.space_before = Pt(14 if level <= 1 else 10)
        p.paragraph_format.space_after = Pt(8)
        return p

    def P(self, text, size=10.5, bold=False, color=None, indent=0.0, after=5, before=0):
        par = self.doc.add_paragraph()
        add_rich(par, text, size, bold, color)
        pf = par.paragraph_format
        pf.space_after = Pt(after)
        pf.space_before = Pt(before)
        pf.line_spacing = 1.45
        if indent:
            pf.left_indent = Cm(indent)
        return par

    def BULLET(self, text, size=10.5):
        par = self.doc.add_paragraph(style="List Bullet")
        add_rich(par, text, size)
        par.paragraph_format.space_after = Pt(3)
        par.paragraph_format.line_spacing = 1.4
        return par

    def NUM(self, text, size=10.5):
        par = self.doc.add_paragraph(style="List Number")
        add_rich(par, text, size)
        par.paragraph_format.space_after = Pt(4)
        par.paragraph_format.line_spacing = 1.4
        return par

    def TABLE(self, rows, widths=None, header=True, size=9.5):
        t = self.doc.add_table(rows=0, cols=len(rows[0]))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, row in enumerate(rows):
            cells = t.add_row().cells
            for j, val in enumerate(row):
                cells[j].text = ""
                par = cells[j].paragraphs[0]
                set_font(par.add_run(str(val)), size, bold=(header and i == 0))
                par.paragraph_format.space_after = Pt(2)
                par.paragraph_format.space_before = Pt(2)
                par.paragraph_format.line_spacing = 1.25
        if widths:
            for row in t.rows:
                for j, w in enumerate(widths):
                    row.cells[j].width = Cm(w)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)
        return t

    def COLLOC(self, lines):
        for line in lines:
            par = self.doc.add_paragraph()
            add_rich(par, "　" + line, 10.0, False, BLUE)
            pf = par.paragraph_format
            pf.space_after = Pt(2)
            pf.line_spacing = 1.35
            pf.left_indent = Cm(0.6)

    def QUESTION(self, no, tag, qtype, stem, mine, right, cause, analysis, colloc=None):
        self.H("Q%s　%s" % (no, tag), 2)
        self.TABLE(
            [
                ["项目", "内容"],
                ["题型", qtype],
                ["题干", stem],
                ["我的答案", mine],
                ["正确答案", right],
                ["错因", cause],
            ],
            widths=[2.4, 14.0],
        )
        self.P("解析", 10.5, True, NAVY, after=3)
        for a in analysis:
            self.BULLET(a)
        if colloc:
            self.P("要点", 10.5, True, NAVY, after=2, before=4)
            self.COLLOC(colloc)

    def save(self, path):
        self.doc.save(path)
        return path
