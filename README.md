# 粉笔练习 PDF 复盘

把粉笔 App 导出的练习 PDF 变成可执行的复盘文档：自动解析 → 错因分析 → 生成 docx → 归档。

## 快速开始

```bash
# 1. 解析 PDF
python scripts/fb_parse.py "D:/Download/快速智能练习.pdf"

# 2. 写错因分析（手动/AI），存成 analyses.json

# 3. 生成 docx
python scripts/fb_pipeline.py "D:/Download/快速智能练习.pdf" \
  --analyses analyses.json \
  --out "复盘.docx"

# 4. 可选：归档
node scripts/fb_archive.js "D:/Download/快速智能练习_parsed.json"
```

## 环境

```bash
pip install pymupdf python-docx
```

## 这个 skill 解决什么问题

粉笔导出的 PDF 有完整文本层，不需要 OCR。真正的工作量在**错因分析**——解析器只能告诉你错了哪几道，不能告诉你为什么错。

所以本 skill 的重心是：

- `scripts/` 负责机械劳动（切题、判对错、统计、排版）
- `references/` 负责分析质量（错因分类体系、写法规范）
- `samples/` 提供两个真实的分析 JSON 作参照

## 使用流程

1. 用户发来粉笔 PDF → 运行 `fb_parse.py`
2. 看解析结果（正确率、错题列表、模块分布）
3. 逐题读题干和选项，写 `analyses.json`
4. 运行 `fb_pipeline.py` 生成 docx
5. 交付 + 可选归档

写分析前先读 `references/analysis-writing.md`，否则容易写成「A 不对，B 对」这种没信息量的东西。

## 核心约定

**锚点优先。** 每道错题的解析必须指出题干里的锚（分号对举、转折词、定义句、惯用搭配），而不是凭语感解释。

**colloc 记「词 + 对象」。** 不记释义。`经久不息 → 只配掌声、欢呼` 有用；`经久不息 → 形容持续很长时间` 没用。

**错因归类要具体。** 用 `references/cause-taxonomy.md` 的编号格式，不写「理解错误」「粗心」。

**训练计划要有数量、时间、验收标准。** 不写「加强积累」。

## 已知限制

- 只处理粉笔导出的**带文本层** PDF。扫描件、拍照版不支持。
- 资料分析题的图表解析器读不出数值，需要打开 `_imgs/` 看图。
- 题型识别是启发式规则，智能组卷题型随机时可能判错，生成后看一眼「模块分布」。
- 图形推理题的选项是图片，解析器只能标出题型，无法判对错逻辑。
