---
name: md-to-pdf
description: 高质量本地 Markdown 转 PDF。使用 pandoc + 无头浏览器(Edge/Chrome)打印，支持中文文档、全边框表格、跨页重复表头、目录(TOC)、mermaid 离线渲染、KaTeX/MathML 公式。当用户要求"把 md 转成 pdf""导出 pdf""重新生成 pdf（表格无边框/mermaid 不显示）"时使用。
---

# md2pdf — Markdown → PDF 本地转换

## 用法

```bash
python c:/Users/admin/.copilot/skills/md-to-pdf/scripts/md2pdf.py input.md [-o output.pdf] [--toc-depth N] [--browser PATH] [--css extra.css] [--keep-html]
```

- 默认输出到输入文件同目录同名 `.pdf`
- `--keep-html`：保留中间 HTML（调试用），用于人工检查样式/mermaid
- `--browser`：指定 Chrome/Edge 可执行文件；脚本会自动在候选列表间回退（本机实测 Chrome 会挂起、Edge 正常，属已知现象）

## 管线原理

1. pandoc (GFM 扩展 pipe_tables/task_lists/footnotes) → standalone HTML5，自动 TOC
2. 内存注入 `assets/style.css`（A4、微软雅黑、**所有 th/td 强制 1px 实线边框**、thead 跨页重复、代码块/引用块样式）
3. 若含 mermaid：内联 `assets/mermaid.min.js`（v11 UMD，无网络依赖），在 DOMContentLoaded 后逐图 `render()` 替换为 SVG——必须等 DOM ready，否则 querySelectorAll 为空
4. Edge/Chrome `--headless=new --print-to-pdf`，独立临时 `--user-data-dir`（避免与已运行浏览器实例冲突挂起），`--virtual-time-budget=120000` 给足渲染时间

## 验证方法（交付前必做）

```python
import pdfplumber
with pdfplumber.open("out.pdf") as pdf:
    tables = sum(len(p.find_tables()) for p in pdf.pages)   # 应≈md中表格数
    err = [i+1 for i,p in enumerate(pdf.pages) if 'Syntax error' in (p.extract_text() or '')]  # 应为空
# 再用 pymupdf(fitz) get_pixmap(dpi=100) 抽样目录页+图表页存 PNG 目检
```

- pdfplumber 能 find_tables 即说明边框线被识别；控制台 FontBBox warning 可忽略
- mermaid 成功的标志：对应页面 curves/rects 数量多、且全文无 "Syntax error in text"

## 已知坑

- pandoc 输出的 mermaid 是 `<pre class="mermaid"><code>…</code></pre>`，注入脚本必须等 DOMContentLoaded 再取 code.textContent
- Chrome headless 在本机大文档会超时挂起 → 自动回退 Edge；Edge + 独立 profile 约 10s 完成 250 页文档
- PowerShell 打印中文易 GBK 报错，验证输出写 UTF-8 文件再读
- `view_image` 不渲染 SVG；集成浏览器 file:// PDF 可能 403（非受信任文件夹），用 fitz 转 PNG 看
