# 贡献指南

## 报告问题

**题型误判**是最常见的问题。报告时请附上：

1. PDF 文件（或能复现问题的最小片段）
2. 期望的题型 vs 实际判出的题型
3. 题干最后 60 个字（题型规则主要看尾部问法）

如果 PDF 不方便公开，可以用 `fb_dump.py` 的方式导出纯文本行贴出来：

```python
import pymupdf
doc = pymupdf.open("xxx.pdf")
for pno, page in enumerate(doc):
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            txt = "".join(s["text"] for s in ln["spans"]).strip()
            if txt:
                print("%d\t%.1f\t%.1f\t%s" % (pno + 1, ln["bbox"][0], ln["bbox"][1], txt))
```

## 改进题型规则

`scripts/fb_parse.py` 的 `guess_type(stem, opts, n_img)` 是唯一需要改的地方。改之前请确认：

- 新规则不会抢走已有规则的题（优先级顺序有意义）
- 资料分析必须排在片段阅读之前
- 只看 `stem[-60:]` 而不是整个题干，避免材料段干扰

改完跑一遍回归，用自己手头的粉笔 PDF 至少测两份（一份智能组卷、一份专项练习），确认：

- 题型判断没有退化
- 正确率统计与粉笔 App 显示一致
- 生成的 docx 没有残留 `【待补充】` 或字面 `**`

## 改进分析质量

`references/` 下的两个文档是纯知识，欢迎补充：

- `cause-taxonomy.md` — 新增错因时保持编号格式，每条必须配「改法」
- `analysis-writing.md` — 补充好的/差的对照示例

**不要**在 taxonomy 里加「理解错误」「粗心」这类无法落地的归类。

## 代码风格

- Python：无第三方格式化工具要求，保持与现有代码一致（4 空格缩进，中文注释）
- 注释写「为什么」不写「是什么」
- 新增 docx 方法时记得走 `add_rich()`，否则 `**加粗**` 不生效

## 提交

```bash
git checkout -b fix/题型误判-语句排序
git commit -m "fix: 语句排序被误判为逻辑填空"
git push origin fix/题型误判-语句排序
```

开 PR 时说明：改了哪个规则、影响了哪些题、回归结果如何。
