#!/usr/bin/env python3
"""md2pdf: Markdown -> PDF 高质量本地转换（pandoc + 无头浏览器打印）。

特性:
- pandoc 转 HTML（GFM 表格、任务列表、删除线、[TOC]/--toc 目录）
- 内嵌打印 CSS：全边框表格、跨页重复表头、中文字体
- mermaid 代码块用随 skill 分发的离线 mermaid.min.js 在无头浏览器中渲染
- 通过 Edge/Chrome 无头模式 --print-to-pdf 输出 PDF

用法:
  python md2pdf.py input.md [-o output.pdf] [--toc-depth N] [--no-mermaid]
                            [--browser PATH] [--keep-html] [--css extra.css]
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS = SKILL_DIR / "assets"

BROWSER_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def die(msg: str) -> None:
    print(f"[md2pdf] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def find_browsers(override: str | None) -> list[str]:
    if override:
        if not Path(override).exists():
            die(f"browser not found: {override}")
        return [override]
    found = [c for c in BROWSER_CANDIDATES if Path(c).exists()]
    if not found:
        die("no Chrome/Edge browser found; install one or pass --browser")
    return found


def pandoc_to_html(md_path: Path, out_html: Path, toc_depth: int, extra_css: list[Path]) -> None:
    pandoc = shutil.which("pandoc")
    if not pandoc:
        die("pandoc not found in PATH")
    cmd = [
        pandoc, str(md_path), "-f", "markdown+pipe_tables+task_lists+footnotes",
        "-t", "html5", "--standalone", "--embed-resources", "--self-contained",
        f"--toc", f"--toc-depth={toc_depth}", "-M", "toc-title=目录",
        "--metadata", "lang=zh-CN", "-o", str(out_html),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        die(f"pandoc failed:\n{r.stdout}\n{r.stderr}")
    _inject_style_and_mermaid(out_html, extra_css)


def _inject_style_and_mermaid(html_file: Path, extra_css: list[Path]) -> None:
    html = html_file.read_text(encoding="utf-8")
    css_parts = []
    main_css = ASSETS / "style.css"
    if main_css.exists():
        css_parts.append(main_css.read_text(encoding="utf-8"))
    for c in extra_css:
        css_parts.append(Path(c).read_text(encoding="utf-8"))

    mermaid_js_path = ASSETS / "mermaid.min.js"
    inject = ""
    if css_parts:
        inject += "<style>\n" + "\n".join(css_parts) + "\n</style>\n"
    has_mermaid = 'class="mermaid"' in html or "language-mermaid" in html
    if mermaid_js_path.exists() and has_mermaid:
        js = mermaid_js_path.read_text(encoding="utf-8")
        inject += (
            "<script>" + js + "</script>\n"
            "<script>\n"
            "window.addEventListener('DOMContentLoaded', async () => {\n"
            "  const ns = window.__esbuild_esm_mermaid_nm && window.__esbuild_esm_mermaid_nm.mermaid;\n"
            "  const m = ns && (ns.default || ns);\n"
            "  if (!m || typeof m.initialize !== 'function') { document.title = 'MERMAID_UNAVAILABLE'; return; }\n"
            "  try {\n"
            "    m.initialize({ startOnLoad: false, securityLevel: 'loose', theme: 'default' });\n"
            "    const nodes = Array.from(document.querySelectorAll('pre.mermaid > code, div.mermaid > code'));\n"
            "    let n = 0, failed = 0;\n"
            "    for (const c of nodes) {\n"
            "      const src = c.textContent;\n"
            "      try {\n"
            "        const { svg } = await m.render('md2pdf-m-' + (n), src);\n"
            "        c.parentElement.innerHTML = svg;\n"
            "      } catch (e) { failed++; c.parentElement.classList.add('mermaid-render-failed'); }\n"
            "      n++;\n"
            "    }\n"
            "    document.title = failed ? ('RENDERED_WITH_ERRORS:' + failed + '/' + n) : 'RENDERED';\n"

            "  } catch (e) { document.title = 'MERMAID_ERROR:' + e.message; }\n"
            "});\n"
            "</script>\n"
        )
    if inject:
        if "</head>" in html:
            html = html.replace("</head>", inject + "</head>")
        else:
            html = inject + html
    # pandoc --self-contained/--embed-resources 需要资源在磁盘上才能内嵌；本脚本全部内存注入，去掉重复的旧参数即可。
    html_file.write_text(html, encoding="utf-8")


def print_pdf(browser: str, html_file: Path, pdf_out: Path, workdir: Path, timeout: int = 300) -> bool:
    url = html_file.resolve().as_uri()
    udd = workdir / ("profile_" + re.sub(r"\W", "", Path(browser).stem))
    cmd = [
        browser, "--headless=new", "--disable-gpu", "--no-first-run",
        f"--user-data-dir={udd}",
        "--virtual-time-budget=120000", "--run-all-compositor-stages-before-draw",
        "--no-pdf-header-footer", f"--print-to-pdf={pdf_out}", url,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"[md2pdf] WARN: {Path(browser).name} timed out, trying next browser...", file=sys.stderr)
        return False
    return pdf_out.exists()


def main() -> None:
    ap = argparse.ArgumentParser(description="Markdown -> PDF (pandoc + headless browser)")
    ap.add_argument("input", help="input .md file")
    ap.add_argument("-o", "--output", help="output .pdf path (default: alongside input)")
    ap.add_argument("--toc-depth", type=int, default=3)
    ap.add_argument("--css", action="append", default=[], help="extra css files appended after built-in style")
    ap.add_argument("--browser", help="path to chrome/edge executable")
    ap.add_argument("--keep-html", action="store_true", help="keep intermediate html for debugging")
    args = ap.parse_args()

    md_path = Path(args.input).resolve()
    if not md_path.exists():
        die(f"input not found: {md_path}")
    pdf_out = Path(args.output).resolve() if args.output else md_path.with_suffix(".pdf")

    workdir = Path(tempfile.mkdtemp(prefix="md2pdf_"))
    try:
        html_file = workdir / (md_path.stem + ".html")
        pandoc_to_html(md_path, html_file, args.toc_depth, args.css)
        if args.keep_html:
            kept = md_path.parent / (md_path.stem + ".debug.html")
            shutil.copyfile(html_file, kept)
            print(f"[md2pdf] debug html: {kept}")
        browsers = find_browsers(args.browser)
        ok = False
        for b in browsers:
            ok = print_pdf(b, html_file, pdf_out, workdir)
            if ok:
                break
        if not ok:
            die("all candidate browsers failed to produce a PDF")
        size_kb = pdf_out.stat().st_size / 1024
        print(f"[md2pdf] OK -> {pdf_out} ({size_kb:.0f} KB)")
    finally:
        if not args.keep_html:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
