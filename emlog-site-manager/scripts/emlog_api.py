#!/usr/bin/env python3
"""Small EMLOG API client for the emlog-site-manager skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = SKILL_DIR / "config" / "emlog_sites.local.json"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
API_KEY_ENV = "EMLOG_API_KEY"


def load_config(path: Path) -> dict:
    if not path.exists():
        return {"sites": {}}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if "sites" not in data or not isinstance(data["sites"], dict):
        raise SystemExit(f"Invalid config file: {path}")
    return data


def save_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def normalize_base_url(base_url: str) -> str:
    base_url = base_url.strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise SystemExit("base-url must start with http:// or https://")
    return base_url


def get_site(config: dict, site_name: str) -> dict:
    site = config.get("sites", {}).get(site_name)
    if not site:
        raise SystemExit(f"Site is not configured: {site_name}")
    if not site.get("base_url"):
        raise SystemExit(f"Site base_url is missing: {site_name}")
    return site


def parse_params(values: list[str]) -> dict:
    params: dict[str, object] = {}
    for item in values:
        if "=" not in item:
            raise SystemExit(f"Parameter must be key=value: {item}")
        key, value = item.split("=", 1)
        if not key:
            raise SystemExit(f"Parameter key is empty: {item}")
        if key.endswith("[]"):
            params.setdefault(key, [])
            if not isinstance(params[key], list):
                raise SystemExit(f"Parameter cannot mix scalar and list values: {key}")
            params[key].append(value)
        else:
            params[key] = value
    return params


def add_auth(site: dict, params: dict, require_auth: bool) -> dict:
    merged = dict(params)
    api_key = os.environ.get(API_KEY_ENV) or site.get("api_key")
    if not require_auth:
        return merged
    if not api_key:
        raise SystemExit(
            "API key is missing. Set EMLOG_API_KEY first, for example: "
            "$env:EMLOG_API_KEY='your_api_key'. To persist it in local config instead, "
            "run: config set --site <name> --base-url <url> --api-key <your_api_key>"
        )
    auth_mode = site.get("auth", "sign")
    if auth_mode == "plain":
        merged["api_key"] = api_key
        return merged
    req_time = str(int(time.time()))
    merged["req_time"] = req_time
    merged["req_sign"] = hashlib.md5((req_time + api_key).encode("utf-8")).hexdigest()
    return merged


def build_rest_url(base_url: str, api: str, query: dict | None = None) -> str:
    url = f"{base_url}/?rest-api={urllib.parse.quote(api)}"
    if query:
        url += "&" + urllib.parse.urlencode(query, doseq=True)
    return url


def request_form(url: str, method: str, params: dict, timeout: int, insecure: bool) -> dict:
    method = method.upper()
    data = None
    if method == "GET":
        if params:
            separator = "&" if "?" in url else "?"
            url = url + separator + urllib.parse.urlencode(params, doseq=True)
    else:
        data = urllib.parse.urlencode(params, doseq=True).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/json")
    request.add_header("User-Agent", DEFAULT_USER_AGENT)
    if data is not None:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
    return open_json(request, timeout, insecure)


def request_multipart(url: str, params: dict, file_path: Path, timeout: int, insecure: bool) -> dict:
    boundary = "----emlog-" + uuid.uuid4().hex
    body = bytearray()

    for key, value in params.items():
        values = value if isinstance(value, list) else [value]
        for item in values:
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
            body.extend(str(item).encode("utf-8"))
            body.extend(b"\r\n")

    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode("utf-8"))
    body.extend(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
    body.extend(file_path.read_bytes())
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    request = urllib.request.Request(url, data=bytes(body), method="POST")
    request.add_header("Accept", "application/json")
    request.add_header("User-Agent", DEFAULT_USER_AGENT)
    request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    return open_json(request, timeout, insecure)


def open_json(request: urllib.request.Request, timeout: int, insecure: bool) -> dict:
    context = ssl._create_unverified_context() if insecure else None
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {error.code}: {raw}") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"Request failed: {error.reason}") from error
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise SystemExit(f"Response is not JSON: {raw[:500]}") from error


def print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def handle_sites(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    sites = config.get("sites", {})
    if not sites:
        print("No sites configured.")
        return
    for name, site in sites.items():
        print(f"{name}\t{site.get('base_url')}\tauth={site.get('auth', 'sign')}")


def handle_config_set(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    site_config = {
        "base_url": normalize_base_url(args.base_url),
        "auth": args.auth,
    }
    existing_site = config.get("sites", {}).get(args.site, {})
    if existing_site.get("api_key") and not args.clear_saved_api_key:
        site_config["api_key"] = existing_site["api_key"]

    if args.api_key:
        site_config["api_key"] = args.api_key

    config.setdefault("sites", {})[args.site] = site_config
    save_config(args.config, config)
    if os.environ.get(API_KEY_ENV):
        key_source = API_KEY_ENV
    elif site_config.get("api_key"):
        key_source = "local config"
    else:
        key_source = "not configured"
    print(f"Saved site '{args.site}' to {args.config} (api_key: {key_source})")


def handle_call(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    site = get_site(config, args.site)
    params = parse_params(args.param)
    params = add_auth(site, params, not args.no_auth)
    url = build_rest_url(site["base_url"], args.api)
    data = request_form(url, args.method, params, args.timeout, args.insecure)
    print_json(data)


def call_rest(args: argparse.Namespace, api: str, method: str, params: dict, require_auth: bool) -> None:
    config = load_config(args.config)
    site = get_site(config, args.site)
    params = add_auth(site, params, require_auth)
    url = build_rest_url(site["base_url"], api)
    data = request_form(url, method, params, args.timeout, args.insecure)
    print_json(data)


def read_content(args: argparse.Namespace) -> str:
    if args.content_file:
        return Path(args.content_file).read_text(encoding="utf-8")
    if args.content is not None:
        return args.content
    raise SystemExit("content or content-file is required")


def article_params(args: argparse.Namespace, include_id: bool) -> dict:
    params = {
        "title": args.title,
        "content": read_content(args),
    }
    if include_id:
        params["id"] = str(args.id)
    optional = {
        "excerpt": args.excerpt,
        "cover": args.cover,
        "author_uid": args.author_uid,
        "sort_id": args.sort_id,
        "tags": args.tags,
        "draft": args.draft,
        "post_date": args.post_date,
        "alias": args.alias,
        "top": args.top,
        "sortop": args.sortop,
        "allow_remark": args.allow_remark,
        "password": args.password,
        "link": args.link,
        "auto_cover": args.auto_cover,
    }
    params.update({key: value for key, value in optional.items() if value is not None})
    params.update(parse_params(args.param))
    return params


def handle_article(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    site = get_site(config, args.site)
    api = "article_update" if args.article_command == "update" else "article_post"
    params = article_params(args, args.article_command == "update")
    params = add_auth(site, params, True)
    url = build_rest_url(site["base_url"], api)
    data = request_form(url, "POST", params, args.timeout, args.insecure)
    print_json(data)


def handle_sort(args: argparse.Namespace) -> None:
    call_rest(args, "sort_list", "GET", {}, False)


def handle_draft(args: argparse.Namespace) -> None:
    if args.draft_command == "detail":
        params = {"id": args.id}
        api = "draft_detail"
    else:
        params = {}
        if args.count is not None:
            params["count"] = args.count
        api = "draft_list"
    call_rest(args, api, "GET", params, True)


def handle_note(args: argparse.Namespace) -> None:
    if args.note_command == "post":
        params = {"t": args.text}
        if args.private is not None:
            params["private"] = args.private
        if args.author_uid is not None:
            params["author_uid"] = args.author_uid
        call_rest(args, "note_post", "POST", params, True)
        return
    params = {}
    if args.page is not None:
        params["page"] = args.page
    if args.count is not None:
        params["count"] = args.count
    if args.author_uid is not None:
        params["author_uid"] = args.author_uid
    call_rest(args, "note_list", "GET", params, True)


def handle_upload(args: argparse.Namespace) -> None:
    file_path = Path(args.file)
    if not file_path.is_file():
        raise SystemExit(f"File does not exist: {file_path}")
    config = load_config(args.config)
    site = get_site(config, args.site)
    params = parse_params(args.param)
    if args.author_uid is not None:
        params["author_uid"] = args.author_uid
    if args.sid is not None:
        params["sid"] = args.sid
    params = add_auth(site, params, True)
    url = build_rest_url(site["base_url"], "upload")
    data = request_multipart(url, params, file_path, args.timeout, args.insecure)
    print_json(data)


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="config file path")
    parser.add_argument("--timeout", type=int, default=30, help="request timeout seconds")
    parser.add_argument("--insecure", action="store_true", help="disable TLS certificate verification")


def add_article_options(parser: argparse.ArgumentParser, require_id: bool) -> None:
    parser.add_argument("--site", required=True)
    if require_id:
        parser.add_argument("--id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--content")
    parser.add_argument("--content-file")
    parser.add_argument("--excerpt")
    parser.add_argument("--cover")
    parser.add_argument("--author-uid")
    parser.add_argument("--sort-id")
    parser.add_argument("--tags")
    parser.add_argument("--draft", choices=["y", "n"], default="n")
    parser.add_argument("--post-date")
    parser.add_argument("--alias")
    parser.add_argument("--top", choices=["y", "n"])
    parser.add_argument("--sortop", choices=["y", "n"])
    parser.add_argument("--allow-remark", choices=["y", "n"])
    parser.add_argument("--password")
    parser.add_argument("--link")
    parser.add_argument("--auto-cover", choices=["y", "n"])
    parser.add_argument("--param", action="append", default=[], help="extra key=value parameter")
    add_common(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EMLOG API helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sites = subparsers.add_parser("sites", help="list configured sites")
    add_common(sites)
    sites.set_defaults(func=handle_sites)

    config = subparsers.add_parser("config", help="manage local config")
    config_subparsers = config.add_subparsers(dest="config_command", required=True)
    config_set = config_subparsers.add_parser("set", help="save or update a site")
    config_set.add_argument("--site", required=True)
    config_set.add_argument("--base-url", required=True)
    config_set.add_argument("--api-key", help="save API key to local config; prefer EMLOG_API_KEY when possible")
    config_set.add_argument("--clear-saved-api-key", action="store_true", help="remove saved API key from this site config")
    config_set.add_argument("--auth", choices=["sign", "plain"], default="sign")
    add_common(config_set)
    config_set.set_defaults(func=handle_config_set)

    call = subparsers.add_parser("call", help="call a rest-api endpoint")
    call.add_argument("--site", required=True)
    call.add_argument("--api", required=True)
    call.add_argument("--method", choices=["GET", "POST"], default="GET")
    call.add_argument("--param", action="append", default=[], help="key=value parameter")
    call.add_argument("--no-auth", action="store_true", help="do not add API authentication parameters")
    add_common(call)
    call.set_defaults(func=handle_call)

    article = subparsers.add_parser("article", help="publish or update articles")
    article_subparsers = article.add_subparsers(dest="article_command", required=True)
    article_post = article_subparsers.add_parser("post", help="publish an article")
    add_article_options(article_post, False)
    article_post.set_defaults(func=handle_article)
    article_update = article_subparsers.add_parser("update", help="update an article or draft")
    add_article_options(article_update, True)
    article_update.set_defaults(func=handle_article)

    sort = subparsers.add_parser("sort", help="category operations")
    sort_subparsers = sort.add_subparsers(dest="sort_command", required=True)
    sort_list = sort_subparsers.add_parser("list", help="list categories")
    sort_list.add_argument("--site", required=True)
    add_common(sort_list)
    sort_list.set_defaults(func=handle_sort)

    draft = subparsers.add_parser("draft", help="draft operations")
    draft_subparsers = draft.add_subparsers(dest="draft_command", required=True)
    draft_list = draft_subparsers.add_parser("list", help="list recent drafts")
    draft_list.add_argument("--site", required=True)
    draft_list.add_argument("--count")
    add_common(draft_list)
    draft_list.set_defaults(func=handle_draft)
    draft_detail = draft_subparsers.add_parser("detail", help="show draft detail")
    draft_detail.add_argument("--site", required=True)
    draft_detail.add_argument("--id", required=True)
    add_common(draft_detail)
    draft_detail.set_defaults(func=handle_draft)

    note = subparsers.add_parser("note", help="note operations")
    note_subparsers = note.add_subparsers(dest="note_command", required=True)
    note_list = note_subparsers.add_parser("list", help="list notes")
    note_list.add_argument("--site", required=True)
    note_list.add_argument("--page")
    note_list.add_argument("--count")
    note_list.add_argument("--author-uid")
    add_common(note_list)
    note_list.set_defaults(func=handle_note)
    note_post = note_subparsers.add_parser("post", help="publish a note")
    note_post.add_argument("--site", required=True)
    note_post.add_argument("--text", required=True)
    note_post.add_argument("--private", choices=["y", "n"])
    note_post.add_argument("--author-uid")
    add_common(note_post)
    note_post.set_defaults(func=handle_note)

    upload = subparsers.add_parser("upload", help="upload a resource file")
    upload.add_argument("--site", required=True)
    upload.add_argument("--file", required=True)
    upload.add_argument("--author-uid")
    upload.add_argument("--sid")
    upload.add_argument("--param", action="append", default=[], help="extra key=value parameter")
    add_common(upload)
    upload.set_defaults(func=handle_upload)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())