---
name: md2word-remote-pdf
description: 使用 md2word.com 的在线转换接口，将本地 Markdown 文件转换为 PDF。适合个人临时自用，不适合敏感文档或长期稳定依赖。
---

# md2word-remote-pdf

## 用途

把指定的本地 `.md` 文件上传到 `md2word.com` 的网页转换接口，并下载生成的 PDF 到本地。

适用场景：
- 临时把 Markdown 转为 PDF
- 希望复用 md2word.com 的排版效果
- 用户接受文档内容上传到第三方服务

不适用场景：
- 敏感文档、涉密内容、客户资料、内部设计文档
- 需要长期稳定、可审计、可离线的生产流程
- 非 Markdown 源文件

## 重要限制

1. **这是第三方网站接口，不是正式开放 API。** 可能随时变更、限流或失效。
2. **会离开本地。** 文档内容会被发送到 `https://md2word.com`。
3. **仅支持 Markdown 输入。** 第一版只处理 `.md` 文件。
4. **更适合个人临时自用。** 不建议作为正式生产链路唯一依赖。

## 默认行为

- 输入：一个本地 `.md` 文件路径
- 输出：同目录下同名 `.pdf` 文件
- `auto_fix` 默认关闭
- 使用 `md2word.com/api/convert` 发起转换
- 成功后下载返回的 `download_url`
- 默认启用超时自适应：小文件默认 120 秒，大于等于 512 KB 的 Markdown 默认 300 秒
- 默认对超时/网络错误自动重试 2 次

## 调用步骤

当用户要求“把某个 Markdown 文件转成 PDF，允许使用 md2word 网站接口”时：

1. 确认输入文件存在且后缀为 `.md`
2. 运行：

```bash
python skills/md2word-remote-pdf/scripts/md2word_remote_pdf.py --input "<markdown文件路径>"
```

3. 如需指定输出路径：

```bash
python skills/md2word-remote-pdf/scripts/md2word_remote_pdf.py --input "<markdown文件路径>" --output "<pdf输出路径>"
```

4. 如需开启站点的自动修复：

```bash
python skills/md2word-remote-pdf/scripts/md2word_remote_pdf.py --input "<markdown文件路径>" --auto-fix
```

## 参数说明

- `--input`：必填，本地 Markdown 文件路径
- `--output`：可选，输出 PDF 路径；不填则默认同名 `.pdf`
- `--auto-fix`：可选，开启站点的 `auto_fix=true`
- `--timeout`：可选，默认 `0`，表示自动判断超时；小文件默认 120 秒，大文件默认 300 秒
- `--retries`：可选，默认 `2`，当发生超时或网络错误时自动重试

## 输出说明

脚本成功时会输出一段 JSON，例如：

```json
{
  "ok": true,
  "input": "C:\\docs\\a.md",
  "output": "C:\\docs\\a.pdf",
  "filename": "a.pdf",
  "download_url": "https://api-prod.md2word.com/download?...",
  "bytes": 123456,
  "timeout": 300,
  "attempt": 1,
  "retries": 2
}
```

失败时也会输出 JSON，包含错误信息，便于上层调用判断。

## 建议

如果后续要长期稳定使用，应再做一个本地后端版本（如 Pandoc/Chromium），把它和本 skill 并列作为两个 provider，而不是完全依赖这个远程接口。
