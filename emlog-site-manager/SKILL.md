---
name: emlog-site-manager
description: "使用 EMLOG / emlog 官方 API 管理站点。Use when: EMLOG 站点管理、API 密钥配置、文章发布/编辑、草稿查询、分类列表、微语笔记、资源上传、站点内容运维。"
argument-hint: "站点名称、操作类型、文章/草稿/笔记/上传参数"
compatibility:
  tools: ["read_file", "run_in_terminal", "apply_patch"]
---

# emlog-site-manager

## 目的

通过 EMLOG 官方 API 管理站点内容，覆盖 API 密钥配置、文章发布与编辑、文章/草稿/分类/微语笔记查询、微语笔记发布和资源上传等常见站点管理任务。

官方文档：<https://www.emlog.net/docs/api/>

## 目录结构

```text
emlog-site-manager/
├── SKILL.md
├── config/
│   └── emlog_sites.local.json    # 保存站点地址等本地配置，已被仓库 .gitignore 忽略
└── scripts/
    └── emlog_api.py
```

## 适用场景

当用户表达以下意图时使用本 skill：
- 配置或保存 EMLOG API 密钥。
- 查看 EMLOG 文章列表、文章详情、草稿、分类、微语笔记。
- 发布文章、更新文章或草稿。
- 发布微语笔记。
- 上传图片、zip 等资源文件。
- 诊断 EMLOG API 调用失败，例如 `sign error`、`api is closed`、`parameter error`。

## 安全与配置约定

- 默认从 `EMLOG_API_KEY` 环境变量读取 API 密钥。
- 默认配置文件：`./config/emlog_sites.local.json`，用于保存站点 base_url 和鉴权模式，已通过仓库根目录 `.gitignore` 忽略。
- 为兼容远程对话或单站点场景，也支持将 API 密钥保存到本地配置文件；但运行时仍优先使用 `EMLOG_API_KEY`。
- 不要使用脚本的控制台交互提示采集 API 密钥，因为用户可能只在远程对话中与 AI 交互，无法跳转到终端输入。
- 缺少 API 密钥时，先检查环境变量和本地配置；二者都没有时，通过对话向用户索取 API 密钥，并用 `config set --api-key` 记录到本地配置文件，后续直接复用。
- 优先使用签名鉴权：脚本会自动生成 `req_time` 和 `req_sign = md5(str(req_time) + api_key)`。
- 如用户明确要求免签名鉴权，可在配置时设置 `--auth plain`，脚本会发送 `api_key` 参数。

## 首次配置流程

1. 检查是否已有配置：

```powershell
python emlog-site-manager/scripts/emlog_api.py sites
```

2. 若目标站点未配置，向用户索要非敏感信息：
   - 站点名称，例如 `main`。
   - 站点首页地址，例如 `https://example.com`。

3. 保存站点配置。默认不保存 API 密钥：

```powershell
python emlog-site-manager/scripts/emlog_api.py config set --site main --base-url "https://example.com"
```

4. 配置 API 密钥。优先使用系统或会话环境变量 `EMLOG_API_KEY`：

```powershell
$env:EMLOG_API_KEY = "your_api_key"
```

如果环境变量没有配置，或用户只是远程对话无法操作终端环境变量，则直接在对话中向用户索取 API 密钥，并保存到本地配置文件：

```powershell
python emlog-site-manager/scripts/emlog_api.py config set --site main --base-url "https://example.com" --api-key "your_api_key"
```

5. 验证只读接口：

```powershell
python emlog-site-manager/scripts/emlog_api.py call --site main --api sort_list
```

## 常用命令

列出已配置站点：

```powershell
python emlog-site-manager/scripts/emlog_api.py sites
```

获取分类列表：

```powershell
python emlog-site-manager/scripts/emlog_api.py sort list --site main
```

获取文章列表：

```powershell
python emlog-site-manager/scripts/emlog_api.py call --site main --api article_list --param page=1 --param count=10
```

获取文章详情：

```powershell
python emlog-site-manager/scripts/emlog_api.py call --site main --api article_detail --param id=123
```

发布微语笔记：

```powershell
python emlog-site-manager/scripts/emlog_api.py note post --site main --text "今天的站点更新记录" --private n
```

查看草稿列表和详情：

```powershell
python emlog-site-manager/scripts/emlog_api.py draft list --site main --count 5
python emlog-site-manager/scripts/emlog_api.py draft detail --site main --id 123
```

查看微语笔记列表：

```powershell
python emlog-site-manager/scripts/emlog_api.py note list --site main --page 1 --count 10
```

发布文章：

```powershell
python emlog-site-manager/scripts/emlog_api.py article post --site main --title "文章标题" --content-file ".\post.md" --sort-id 1 --tags "EMLOG,API" --draft n
```

更新文章或草稿：

```powershell
python emlog-site-manager/scripts/emlog_api.py article update --site main --id 123 --title "新标题" --content-file ".\post.md" --draft n
```

上传资源文件：

```powershell
python emlog-site-manager/scripts/emlog_api.py upload --site main --file ".\cover.png" --sid 1
```

## API 能力速查

无需鉴权的常用接口：
- `article_list`：文章列表。
- `article_detail`：文章详情。
- `sort_list`：分类列表。
- `comment_list` / `comment_list_simple`：评论列表。
- `like_list`：获赞列表。

需要 API 密钥鉴权的管理接口：
- `article_post`：文章发布。
- `article_update`：文章或草稿编辑。
- `draft_list`：草稿列表。
- `draft_detail`：草稿详情。
- `note_post`：微语笔记发布。
- `note_list`：微语笔记列表。
- `upload`：资源文件上传。
- `user_detail`：用户信息。

## 执行流程建议

1. 明确用户目标属于只读查询、内容发布、内容编辑还是资源上传。
2. 若是只读公开接口，可直接调用，不强制要求 API 密钥。
3. 若是管理接口，先检查站点配置、`EMLOG_API_KEY` 和本地配置中的 `api_key`；缺少 API 密钥时，通过对话索取并用 `--api-key` 保存到本地配置。
4. 发布或编辑文章前，确认标题、正文来源、分类 ID、标签、草稿状态。
5. 调用 API 后检查 JSON：`code == 0` 视为成功；否则向用户解释 `msg` 并给出下一步。
6. 对会修改站点内容的操作，在执行前简要复述目标站点、接口和关键参数。

## 常见错误处理

- `sign error`：检查 API 密钥、服务器时间与本机时间，或改用 `--auth plain` 验证。
- `api is closed`：需要在 EMLOG 后台“系统-设置-API 设置”开启 API。
- `API function is not exist`：接口名拼写错误或站点版本不支持。
- `parameter error`：缺少必填参数，例如文章发布必须提供 `title` 和 `content`。
- 网络或证书错误：检查 `base_url` 是否可访问，是否必须使用 HTTPS。
