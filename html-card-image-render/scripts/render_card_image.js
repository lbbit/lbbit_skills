#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

let puppeteer;

try {
  puppeteer = require("puppeteer-core");
} catch (error) {
  console.error("[ERROR] Missing dependency: puppeteer-core. Run 'npm install' first.");
  process.exit(1);
}

function printUsage() {
  console.log(
    [
      "Usage:",
      "  node scripts/render_card_image.js --input <path> [options]",
      "",
      "Required:",
      "  --input <path>             Input file: .html/.htm/.json/.md/.txt",
      "",
      "Options:",
      "  --output <path>            Output image path (default: output/card.png)",
      "  --width <number>           Viewport width (default: 1600)",
      "  --height <number>          Viewport height (default: 900)",
      "  --device-scale-factor <n>  Device scale factor (default: 2)",
      "  --theme <name>             Template theme: architect|sunset|forest|minimal",
      "  --selector <css>           Capture element selector (default: #card-root)",
      "  --format <png|jpeg|webp>   Output format, defaults from output extension",
      "  --quality <1-100>          JPEG/WEBP quality (default: 90)",
      "  --full-page                Capture full page screenshot",
      "  --timeout <ms>             Render timeout (default: 30000)",
      "  --puppeteer-config <path>  Puppeteer launch config JSON",
      "  -h, --help                 Show this help",
    ].join("\n")
  );
}

function parseArgs(argv) {
  const args = {
    input: "",
    output: "output/card.png",
    width: 1600,
    height: 900,
    dpr: 2,
    theme: "architect",
    selector: "#card-root",
    format: "",
    quality: 90,
    fullPage: false,
    timeout: 30000,
    puppeteerConfig: "",
  };

  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];

    if (token === "-h" || token === "--help") {
      args.help = true;
      return args;
    }

    if (token === "--full-page") {
      args.fullPage = true;
      continue;
    }

    if (!token.startsWith("--")) {
      throw new Error(`Unknown argument: ${token}`);
    }

    const key = token.slice(2);
    const value = argv[i + 1];

    if (value == null || value.startsWith("--")) {
      throw new Error(`Missing value for --${key}`);
    }

    i += 1;

    if (key === "input") {
      args.input = value;
    } else if (key === "output") {
      args.output = value;
    } else if (key === "width") {
      args.width = Number(value);
    } else if (key === "height") {
      args.height = Number(value);
    } else if (key === "device-scale-factor") {
      args.dpr = Number(value);
    } else if (key === "theme") {
      args.theme = String(value).toLowerCase();
    } else if (key === "selector") {
      args.selector = value;
    } else if (key === "format") {
      args.format = String(value).toLowerCase();
    } else if (key === "quality") {
      args.quality = Number(value);
    } else if (key === "timeout") {
      args.timeout = Number(value);
    } else if (key === "puppeteer-config") {
      args.puppeteerConfig = value;
    } else {
      throw new Error(`Unsupported argument: --${key}`);
    }
  }

  return args;
}

function ensureFileExists(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`File not found: ${filePath}`);
  }
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function readJsonFile(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (error) {
    throw new Error(`Invalid JSON input: ${filePath}`);
  }
}

function normalizeSpec(spec) {
  const normalized = {
    eyebrow: spec.eyebrow || "CARD",
    title: spec.title || "Untitled Card",
    subtitle: spec.subtitle || "",
    description: spec.description || "",
    tags: Array.isArray(spec.tags) ? spec.tags : [],
    metrics: Array.isArray(spec.metrics) ? spec.metrics : [],
    bullets: Array.isArray(spec.bullets) ? spec.bullets : [],
    code: spec.code && typeof spec.code === "object" ? spec.code : null,
    footer: spec.footer || "",
  };

  return normalized;
}

function renderMarkdownToHtml(markdownText) {
  const placeholders = [];
  const text = markdownText.replace(/\r\n/g, "\n").replace(/```([a-zA-Z0-9_-]+)?\n([\s\S]*?)```/g, (_, lang, code) => {
    const idx = placeholders.push({ lang: lang || "text", code: code.trimEnd() }) - 1;
    return `@@CODE_BLOCK_${idx}@@`;
  });

  const lines = text.split("\n");
  const out = [];
  let inList = false;

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (!line) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      continue;
    }

    const blockMatch = line.match(/^@@CODE_BLOCK_(\d+)@@$/);
    if (blockMatch) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      const item = placeholders[Number(blockMatch[1])];
      out.push(
        `<div class=\"section\"><div class=\"section-title\">${escapeHtml(item.lang)}</div><pre class=\"code-block\"><code>${escapeHtml(
          item.code
        )}</code></pre></div>`
      );
      continue;
    }

    if (line.startsWith("### ")) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      out.push(`<h3>${escapeHtml(line.slice(4))}</h3>`);
      continue;
    }

    if (line.startsWith("## ")) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      out.push(`<h2>${escapeHtml(line.slice(3))}</h2>`);
      continue;
    }

    if (line.startsWith("# ")) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      out.push(`<h1>${escapeHtml(line.slice(2))}</h1>`);
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${escapeHtml(line.replace(/^[-*]\s+/, ""))}</li>`);
      continue;
    }

    if (inList) {
      out.push("</ul>");
      inList = false;
    }
    out.push(`<p>${escapeHtml(line)}</p>`);
  }

  if (inList) {
    out.push("</ul>");
  }

  return out.join("\n");
}

function getThemeVars(theme) {
  const themes = {
    architect: {
      bg: "radial-gradient(circle at 12% 15%, #e3f0ff 0%, #f5f8fc 44%, #eef3fb 100%)",
      cardBg: "rgba(255, 255, 255, 0.88)",
      text: "#1d2a3f",
      muted: "#52617f",
      border: "rgba(57, 83, 132, 0.18)",
      accent: "#2f6ee9",
      accentSoft: "rgba(47, 110, 233, 0.12)",
    },
    sunset: {
      bg: "radial-gradient(circle at 20% 20%, #ffe7d4 0%, #fff3e7 45%, #ffe9dd 100%)",
      cardBg: "rgba(255, 255, 255, 0.9)",
      text: "#3f2a1f",
      muted: "#755544",
      border: "rgba(176, 97, 45, 0.2)",
      accent: "#df6f2d",
      accentSoft: "rgba(223, 111, 45, 0.14)",
    },
    forest: {
      bg: "radial-gradient(circle at 12% 16%, #dff4e5 0%, #edf7f0 45%, #e7f5ee 100%)",
      cardBg: "rgba(255, 255, 255, 0.9)",
      text: "#173127",
      muted: "#486356",
      border: "rgba(52, 107, 83, 0.2)",
      accent: "#1f8a5f",
      accentSoft: "rgba(31, 138, 95, 0.14)",
    },
    minimal: {
      bg: "linear-gradient(145deg, #f7f7f7 0%, #efefef 100%)",
      cardBg: "rgba(255, 255, 255, 0.94)",
      text: "#1f1f1f",
      muted: "#5a5a5a",
      border: "rgba(0, 0, 0, 0.12)",
      accent: "#111111",
      accentSoft: "rgba(0, 0, 0, 0.08)",
    },
  };

  return themes[theme] || themes.architect;
}

function buildTemplateCss(theme) {
  const t = getThemeVars(theme);
  return `
:root {
  --bg: ${t.bg};
  --card-bg: ${t.cardBg};
  --text: ${t.text};
  --muted: ${t.muted};
  --border: ${t.border};
  --accent: ${t.accent};
  --accent-soft: ${t.accentSoft};
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  color: var(--text);
  background: var(--bg);
}
.stage {
  min-height: 100vh;
  padding: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}
.stage::before,
.stage::after {
  content: "";
  position: absolute;
  border-radius: 999px;
  filter: blur(4px);
}
.stage::before {
  width: 260px;
  height: 260px;
  right: 8%;
  top: 8%;
  background: var(--accent-soft);
}
.stage::after {
  width: 180px;
  height: 180px;
  left: 6%;
  bottom: 8%;
  background: var(--accent-soft);
}
.card {
  width: min(1200px, 100%);
  border: 1px solid var(--border);
  border-radius: 28px;
  background: var(--card-bg);
  box-shadow: 0 24px 60px rgba(13, 28, 45, 0.18);
  padding: 36px 40px;
  backdrop-filter: blur(6px);
}
.header {
  margin-bottom: 22px;
}
.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 13px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
}
.title {
  margin: 14px 0 8px;
  font-size: 42px;
  line-height: 1.12;
  letter-spacing: -0.02em;
}
.subtitle {
  margin: 0;
  font-size: 21px;
  line-height: 1.45;
  color: var(--muted);
}
.description {
  margin: 14px 0 0;
  font-size: 18px;
  line-height: 1.65;
}
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 22px 0;
}
.tag {
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 14px;
  color: var(--muted);
  background: rgba(255, 255, 255, 0.55);
}
.metrics {
  margin: 24px 0;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}
.metric {
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.55);
}
.metric-value {
  font-size: 30px;
  font-weight: 700;
  letter-spacing: -0.01em;
  margin-bottom: 4px;
}
.metric-label {
  font-size: 14px;
  color: var(--muted);
}
.body-grid {
  display: grid;
  gap: 20px;
  grid-template-columns: 1fr 1fr;
}
.section {
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 16px 18px;
  background: rgba(255, 255, 255, 0.62);
}
.section-title {
  margin: 0 0 10px;
  color: var(--accent);
  font-weight: 700;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
ul {
  margin: 0;
  padding-left: 20px;
  line-height: 1.6;
}
li {
  margin: 4px 0;
}
.code-block {
  margin: 0;
  padding: 14px;
  border-radius: 12px;
  background: #11151f;
  color: #f4f6fb;
  font-size: 13px;
  line-height: 1.55;
  overflow-x: auto;
}
.markdown {
  display: grid;
  gap: 12px;
}
.markdown h1,
.markdown h2,
.markdown h3,
.markdown p {
  margin: 0;
}
.footer {
  margin-top: 20px;
  color: var(--muted);
  font-size: 14px;
  border-top: 1px dashed var(--border);
  padding-top: 12px;
}
@media (max-width: 900px) {
  .stage {
    padding: 20px;
  }
  .card {
    padding: 24px 20px;
    border-radius: 22px;
  }
  .title {
    font-size: 30px;
  }
  .subtitle {
    font-size: 17px;
  }
  .body-grid {
    grid-template-columns: 1fr;
  }
}
`;
}

function buildCardFromSpec(spec, theme) {
  const s = normalizeSpec(spec);

  const tagsHtml = s.tags
    .map((tag) => `<span class=\"tag\">${escapeHtml(tag)}</span>`)
    .join("");

  const metricsHtml = s.metrics
    .map(
      (item) =>
        `<div class=\"metric\"><div class=\"metric-value\">${escapeHtml(item.value || "-")}</div><div class=\"metric-label\">${escapeHtml(
          item.label || ""
        )}</div></div>`
    )
    .join("");

  const bulletsHtml = s.bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join("");

  const codeHtml = s.code
    ? `<div class=\"section\"><div class=\"section-title\">${escapeHtml(
        s.code.language || "code"
      )}</div><pre class=\"code-block\"><code>${escapeHtml(s.code.content || "")}</code></pre></div>`
    : "";

  const leftSection =
    s.bullets.length > 0
      ? `<div class=\"section\"><div class=\"section-title\">Highlights</div><ul>${bulletsHtml}</ul></div>`
      : `<div class=\"section\"><div class=\"section-title\">Summary</div><p>${escapeHtml(
          s.description || "No summary provided."
        )}</p></div>`;

  return `
<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>${buildTemplateCss(theme)}</style>
  </head>
  <body>
    <main class=\"stage\">
      <article id=\"card-root\" class=\"card\">
        <header class=\"header\">
          <div class=\"eyebrow\">${escapeHtml(s.eyebrow)}</div>
          <h1 class=\"title\">${escapeHtml(s.title)}</h1>
          ${s.subtitle ? `<p class=\"subtitle\">${escapeHtml(s.subtitle)}</p>` : ""}
          ${s.description ? `<p class=\"description\">${escapeHtml(s.description)}</p>` : ""}
          ${tagsHtml ? `<div class=\"tag-row\">${tagsHtml}</div>` : ""}
        </header>
        ${metricsHtml ? `<section class=\"metrics\">${metricsHtml}</section>` : ""}
        <section class=\"body-grid\">
          ${leftSection}
          ${codeHtml || `<div class=\"section\"><div class=\"section-title\">Notes</div><p>Use JSON/Markdown input to generate rich cards quickly.</p></div>`}
        </section>
        ${s.footer ? `<footer class=\"footer\">${escapeHtml(s.footer)}</footer>` : ""}
      </article>
    </main>
  </body>
</html>
`;
}

function buildCardFromMarkdown(markdownText, theme) {
  const html = renderMarkdownToHtml(markdownText);
  const titleMatch = markdownText.match(/^\s*#\s+(.+)$/m);
  const title = titleMatch ? titleMatch[1].trim() : "Markdown Card";

  return `
<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>${buildTemplateCss(theme)}</style>
  </head>
  <body>
    <main class=\"stage\">
      <article id=\"card-root\" class=\"card\">
        <header class=\"header\">
          <div class=\"eyebrow\">TEXT TO CARD</div>
          <h1 class=\"title\">${escapeHtml(title)}</h1>
          <p class=\"subtitle\">Auto styled from Markdown/TXT input</p>
        </header>
        <section class=\"markdown\">${html}</section>
      </article>
    </main>
  </body>
</html>
`;
}

function buildCardFromHtmlSnippet(htmlSnippet, theme) {
  return `
<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>${buildTemplateCss(theme)}</style>
  </head>
  <body>
    <main class=\"stage\">
      <section id=\"card-root\" class=\"card\">${htmlSnippet}</section>
    </main>
  </body>
</html>
`;
}

function buildHtmlForInput(inputPath, theme) {
  const ext = path.extname(inputPath).toLowerCase();
  const content = fs.readFileSync(inputPath, "utf8");

  if (ext === ".html" || ext === ".htm") {
    if (/<html[\s>]/i.test(content)) {
      return content;
    }
    return buildCardFromHtmlSnippet(content, theme);
  }

  if (ext === ".json") {
    return buildCardFromSpec(readJsonFile(inputPath), theme);
  }

  if (ext === ".md" || ext === ".markdown" || ext === ".txt") {
    return buildCardFromMarkdown(content, theme);
  }

  throw new Error("Unsupported input extension. Use .html/.htm/.json/.md/.txt");
}

function validateArgs(args) {
  if (!args.input) {
    throw new Error("--input is required");
  }

  if (!Number.isFinite(args.width) || args.width <= 0) {
    throw new Error("--width must be a positive number");
  }

  if (!Number.isFinite(args.height) || args.height <= 0) {
    throw new Error("--height must be a positive number");
  }

  if (!Number.isFinite(args.dpr) || args.dpr <= 0) {
    throw new Error("--device-scale-factor must be a positive number");
  }

  if (!Number.isFinite(args.quality) || args.quality < 1 || args.quality > 100) {
    throw new Error("--quality must be between 1 and 100");
  }

  if (!Number.isFinite(args.timeout) || args.timeout <= 0) {
    throw new Error("--timeout must be a positive number");
  }

  const format = resolveOutputFormat(args.output, args.format);
  if (!["png", "jpeg", "webp"].includes(format)) {
    throw new Error("--format must be one of: png, jpeg, webp");
  }
}

function resolveOutputFormat(outputPath, preferredFormat) {
  if (preferredFormat) {
    return preferredFormat;
  }
  const ext = path.extname(outputPath).toLowerCase();
  if (ext === ".jpg" || ext === ".jpeg") {
    return "jpeg";
  }
  if (ext === ".webp") {
    return "webp";
  }
  return "png";
}

async function loadPuppeteerLaunchOptions(baseDir, maybePath) {
  if (!maybePath) {
    return { headless: true };
  }

  const resolved = path.isAbsolute(maybePath) ? maybePath : path.resolve(baseDir, maybePath);
  ensureFileExists(resolved);

  const data = readJsonFile(resolved);
  return { headless: true, ...data };
}

async function screenshotHtml(html, args, outputPath, launchOptions) {
  const browser = await puppeteer.launch(launchOptions);

  try {
    const page = await browser.newPage();
    await page.setViewport({
      width: Math.round(args.width),
      height: Math.round(args.height),
      deviceScaleFactor: Number(args.dpr),
    });

    await page.setContent(html, {
      waitUntil: ["load", "networkidle0"],
      timeout: args.timeout,
    });

    await page.evaluate(() => document.fonts && document.fonts.ready);

    const imageType = resolveOutputFormat(outputPath, args.format);
    const screenshotOptions = {
      type: imageType,
      path: outputPath,
      fullPage: args.fullPage,
    };

    if (imageType === "jpeg" || imageType === "webp") {
      screenshotOptions.quality = Math.round(args.quality);
    }

    if (!args.fullPage) {
      const target = await page.$(args.selector);
      if (!target) {
        throw new Error(`Selector not found: ${args.selector}`);
      }
      await target.screenshot(screenshotOptions);
      return;
    }

    await page.screenshot(screenshotOptions);
  } finally {
    await browser.close();
  }
}

async function main() {
  let args;

  try {
    args = parseArgs(process.argv);
  } catch (error) {
    console.error(`[ERROR] ${error.message}`);
    printUsage();
    process.exit(2);
  }

  if (args.help) {
    printUsage();
    return;
  }

  try {
    validateArgs(args);
  } catch (error) {
    console.error(`[ERROR] ${error.message}`);
    printUsage();
    process.exit(2);
  }

  const baseDir = path.resolve(__dirname, "..");
  const inputPath = path.isAbsolute(args.input) ? args.input : path.resolve(baseDir, args.input);
  const outputPath = path.isAbsolute(args.output) ? args.output : path.resolve(baseDir, args.output);

  try {
    ensureFileExists(inputPath);
    const outputDir = path.dirname(outputPath);
    fs.mkdirSync(outputDir, { recursive: true });

    const html = buildHtmlForInput(inputPath, args.theme);
    const launchOptions = await loadPuppeteerLaunchOptions(baseDir, args.puppeteerConfig);

    await screenshotHtml(html, args, outputPath, launchOptions);

    console.log("[OK] Rendered image:");
    console.log(`- ${outputPath}`);
  } catch (error) {
    console.error(`[ERROR] ${error.message}`);
    process.exit(1);
  }
}

main();
