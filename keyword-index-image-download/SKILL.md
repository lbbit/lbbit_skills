---
name: keyword-index-image-download
description: 使用关键词(keyword) + 序号(index)下载单张图片到本地。适用于内容配图、素材抓取、自动化生成本地图片资源等场景。
compatibility:
  tools: ["read_file", "create_directory", "create_file", "run_in_terminal"]
---

# keyword-index-image-download

## 目的

将“关键词 + 序号”图片下载能力沉淀为可复用 skill，方便在 skills 仓库中按子目录独立维护。

该 skill 的核心输入是：
- keyword：图片关键词
- index：序号（从 0 开始）

## 目录结构

```text
keyword-index-image-download/
├── SKILL.md
└── scripts/
    └── download_baidu_image.py
```

## 适用场景

当用户希望“按关键词并指定序号下载图片”时，使用本 skill。

典型表达包括：
- 下载某个关键词的第 N 张图
- 根据关键词取一张配图并保存到本地
- 自动化脚本里按 keyword + index 拉取图片

## 脚本参数

脚本路径：
- scripts/download_baidu_image.py

参数说明：
- --keyword：必填，搜索关键词
- --index：可选，默认 0，表示结果序号偏移
- --output-dir：可选，默认 images，图片输出目录
- --filename：可选，自定义文件名（不传则自动生成 keyword_index.jpg）
- --timeout：可选，默认 15 秒
- --force：可选，强制重下，忽略本地缓存

## 执行示例

下载“猫咪”关键词第 0 张图：

```bash
python scripts/download_baidu_image.py --keyword "猫咪" --index 0 --output-dir "./images"
```

下载“风景”关键词第 8 张图并指定文件名：

```bash
python scripts/download_baidu_image.py --keyword "风景" --index 8 --output-dir "./images" --filename "landscape_8.jpg"
```

## 输出约定

成功下载时输出：
- [OK] Downloaded: <本地图片路径>
- [INFO] Source URL: <图片来源地址>

命中本地缓存时输出：
- [OK] Cache hit: <本地图片路径>

失败时输出：
- [ERROR] ...

## 执行流程建议

1. 校验是否提供 keyword。
2. 将 index 规范为非负整数。
3. 执行脚本下载图片。
4. 读取 [OK] 输出中的本地路径，供后续 Markdown 或业务流程引用。

## 注意事项

- 脚本使用 Python 标准库 urllib 实现，不依赖 requests 等第三方包。
- 百度图片接口存在反爬策略，若偶发失败可重试或更换关键词。
- index 语义与百度接口参数 pn 对齐，通常建议从 0 开始递增。
- 默认启用本地缓存，相同 keyword + index 再次执行会直接复用本地文件。
