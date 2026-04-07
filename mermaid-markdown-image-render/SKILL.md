---
name: mermaid-markdown-image-render
description: 基于 Mermaid + Markdown(JavaScript) 将流程图、时序图、状态转移图等渲染为 PNG/SVG/PDF 图片，适用于文档自动制图和流程可视化。
compatibility:
  tools: ["read_file", "create_directory", "create_file", "run_in_terminal"]
---

# mermaid-markdown-image-render

## 目的

把 Mermaid 图表渲染能力封装为独立 skill，支持从 Markdown 中批量提取 mermaid 代码块，或直接渲染 .mmd/.mermaid 文件，并输出图片文件。

## 目录结构

```text
mermaid-markdown-image-render/
├── SKILL.md
├── package.json
├── scripts/
│   └── render_mermaid_from_markdown.js
└── examples/
    └── diagrams.md
```

## 支持图表类型

只要 Mermaid 语法支持，即可渲染。常见类型包括：
- flowchart（流程图）
- sequenceDiagram（时序图）
- stateDiagram-v2（状态转移图）
- classDiagram、erDiagram、journey、gantt 等

## 技术栈

- Mermaid CLI：`@mermaid-js/mermaid-cli`
- Markdown 解析：Node.js 脚本通过正则提取 ` ```mermaid ... ``` ` 代码块
- 输出格式：PNG / SVG / PDF

## 使用方式

先安装依赖：

```bash
$env:PUPPETEER_SKIP_DOWNLOAD="true"
npm install
```

说明：
- 上述方式会跳过 Chromium 下载，使用本机浏览器执行渲染。
- Windows 可使用本 skill 自带的 `puppeteer-config.edge.windows.json` 指向 Edge。

渲染 Markdown 中的全部 Mermaid 代码块：

```bash
node scripts/render_mermaid_from_markdown.js \
  --input examples/diagrams.md \
  --output-dir output \
  --format png \
  --prefix demo \
  --puppeteer-config puppeteer-config.edge.windows.json
```

渲染单个 Mermaid 文件：

```bash
node scripts/render_mermaid_from_markdown.js \
  --input your_diagram.mmd \
  --output-dir output \
  --format svg \
  --prefix single
```

## 参数说明

- `--input`：输入文件路径（相对于 skill 目录）
- `--output-dir`：输出目录（默认 `output`）
- `--format`：`png|svg|pdf`（默认 `png`）
- `--prefix`：输出文件名前缀（默认 `diagram`）
- `--scale`：渲染倍数（默认 `2`）
- `--background`：背景色（默认 `transparent`）
- `--puppeteer-config`：Puppeteer 配置文件路径（可选，用于指定浏览器）

## 输出约定

- Markdown 输入：按顺序输出 `prefix_1.xxx`、`prefix_2.xxx`...
- Mermaid 输入：输出 `prefix_1.xxx`
- 控制台输出 `[OK] Rendered N diagram(s):` 及每个文件路径

## 注意事项

- 首次使用需要联网安装 npm 依赖。
- 若渲染报错，优先检查 Mermaid 语法是否正确。
- 产物建议写入独立目录（例如 `output/` 或 `verify_output/`），避免污染仓库根目录。
