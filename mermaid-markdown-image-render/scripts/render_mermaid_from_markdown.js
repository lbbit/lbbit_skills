#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const os = require("os");
const { execFileSync } = require("child_process");

function printUsage() {
  console.log(
    [
      "Usage:",
      "  node scripts/render_mermaid_from_markdown.js --input <path> [options]",
      "",
      "Required:",
      "  --input <path>           Markdown(.md) or Mermaid(.mmd/.mermaid) file",
      "",
      "Options:",
      "  --output-dir <path>      Output directory (default: output)",
      "  --format <png|svg|pdf>   Output format (default: png)",
      "  --prefix <name>          Output file name prefix (default: diagram)",
      "  --scale <number>         Render scale (default: 2)",
      "  --background <value>     Background color (default: transparent)",
      "  --puppeteer-config <path> Path to puppeteer config JSON (optional)",
      "  -h, --help               Show this help",
    ].join("\n")
  );
}

function parseArgs(argv) {
  const args = {
    input: "",
    outputDir: "output",
    format: "png",
    prefix: "diagram",
    scale: 2,
    background: "transparent",
    puppeteerConfig: "",
  };

  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];

    if (token === "-h" || token === "--help") {
      args.help = true;
      return args;
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
    } else if (key === "output-dir") {
      args.outputDir = value;
    } else if (key === "format") {
      args.format = value.toLowerCase();
    } else if (key === "prefix") {
      args.prefix = value;
    } else if (key === "scale") {
      args.scale = Number(value);
    } else if (key === "background") {
      args.background = value;
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
    throw new Error(`Input file not found: ${filePath}`);
  }
}

function extractMermaidBlocks(markdownText) {
  const regex = /```mermaid\s*([\s\S]*?)```/gim;
  const blocks = [];
  let match = regex.exec(markdownText);

  while (match) {
    blocks.push(match[1].trim());
    match = regex.exec(markdownText);
  }

  return blocks;
}

function resolveMmdcCliPath(baseDir) {
  const cliPath = path.join(
    baseDir,
    "node_modules",
    "@mermaid-js",
    "mermaid-cli",
    "src",
    "cli.js"
  );

  if (!fs.existsSync(cliPath)) {
    throw new Error(
      "Mermaid CLI not found. Please run 'npm install' in mermaid-markdown-image-render first."
    );
  }

  return cliPath;
}

function renderSingleDiagram(cliPath, inputFile, outputFile, args, puppeteerConfigPath) {
  const cmdArgs = [
    cliPath,
    "-i",
    inputFile,
    "-o",
    outputFile,
    "-s",
    String(args.scale),
    "-b",
    args.background,
  ];

  if (puppeteerConfigPath) {
    cmdArgs.push("-p", puppeteerConfigPath);
  }

  try {
    execFileSync(process.execPath, cmdArgs, { stdio: "pipe" });
  } catch (error) {
    const stderr = error.stderr ? String(error.stderr) : "";
    const stdout = error.stdout ? String(error.stdout) : "";
    const detail = error && error.message ? String(error.message) : "";
    throw new Error(
      `Render failed for ${path.basename(inputFile)}\n${detail}\n${stdout}${stderr}`.trim()
    );
  }
}

function writeTempFile(content, index) {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "mermaid-block-"));
  const tempFile = path.join(tempDir, `block_${index}.mmd`);
  fs.writeFileSync(tempFile, content, "utf8");
  return { tempDir, tempFile };
}

function cleanupTempDir(tempDir) {
  fs.rmSync(tempDir, { recursive: true, force: true });
}

function validateArgs(args) {
  if (!args.input) {
    throw new Error("--input is required");
  }

  if (!Number.isFinite(args.scale) || args.scale <= 0) {
    throw new Error("--scale must be a positive number");
  }

  if (!["png", "svg", "pdf"].includes(args.format)) {
    throw new Error("--format must be one of: png, svg, pdf");
  }
}

function renderFromMarkdown(cliPath, markdownPath, args, outputDir, puppeteerConfigPath) {
  const markdownText = fs.readFileSync(markdownPath, "utf8");
  const blocks = extractMermaidBlocks(markdownText);

  if (blocks.length === 0) {
    throw new Error("No mermaid code blocks found in markdown file");
  }

  const outputs = [];

  blocks.forEach((block, idx) => {
    const { tempDir, tempFile } = writeTempFile(block, idx + 1);
    const outputFile = path.join(outputDir, `${args.prefix}_${idx + 1}.${args.format}`);

    try {
      renderSingleDiagram(cliPath, tempFile, outputFile, args, puppeteerConfigPath);
      outputs.push(outputFile);
    } finally {
      cleanupTempDir(tempDir);
    }
  });

  return outputs;
}

function renderFromMermaidFile(cliPath, mermaidPath, args, outputDir, puppeteerConfigPath) {
  const outputFile = path.join(outputDir, `${args.prefix}_1.${args.format}`);
  renderSingleDiagram(cliPath, mermaidPath, outputFile, args, puppeteerConfigPath);
  return [outputFile];
}

function main() {
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
  const inputPath = path.resolve(baseDir, args.input);
  const outputDir = path.resolve(baseDir, args.outputDir);
  let puppeteerConfigPath = "";

  try {
    ensureFileExists(inputPath);
    if (args.puppeteerConfig) {
      puppeteerConfigPath = path.isAbsolute(args.puppeteerConfig)
        ? args.puppeteerConfig
        : path.resolve(baseDir, args.puppeteerConfig);
      ensureFileExists(puppeteerConfigPath);
    }
    fs.mkdirSync(outputDir, { recursive: true });

    const cliPath = resolveMmdcCliPath(baseDir);
    const ext = path.extname(inputPath).toLowerCase();

    let outputs;

    if (ext === ".md" || ext === ".markdown") {
      outputs = renderFromMarkdown(cliPath, inputPath, args, outputDir, puppeteerConfigPath);
    } else if (ext === ".mmd" || ext === ".mermaid") {
      outputs = renderFromMermaidFile(cliPath, inputPath, args, outputDir, puppeteerConfigPath);
    } else {
      throw new Error("Unsupported input extension. Use .md, .markdown, .mmd, or .mermaid");
    }

    console.log(`[OK] Rendered ${outputs.length} diagram(s):`);
    outputs.forEach((filePath) => {
      console.log(`- ${filePath}`);
    });
  } catch (error) {
    console.error(`[ERROR] ${error.message}`);
    process.exit(1);
  }
}

main();
