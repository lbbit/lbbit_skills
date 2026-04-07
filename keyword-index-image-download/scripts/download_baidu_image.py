import argparse
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BAIDU_IMAGE_SEARCH_URL = "https://image.baidu.com/search/acjson"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://image.baidu.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def sanitize_filename(text: str) -> str:
    sanitized = re.sub(r"[\\/:*?\"<>|]+", "_", text.strip())
    return sanitized or "image"


def http_get_text(url: str, params: dict[str, str | int], timeout: int) -> str:
    query = urlencode(params)
    request = Request(f"{url}?{query}", headers=DEFAULT_HEADERS)
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def http_get_bytes(url: str, timeout: int) -> bytes:
    request = Request(url, headers=DEFAULT_HEADERS)
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_image_url(keyword: str, index: int, timeout: int) -> str:
    params = {
        "tn": "resultjson_com",
        "ipn": "rj",
        "ct": 201326592,
        "is": "",
        "fp": "result",
        "queryWord": keyword,
        "cl": 2,
        "lm": -1,
        "ie": "utf-8",
        "oe": "utf-8",
        "adpicid": "",
        "st": -1,
        "z": "",
        "ic": "",
        "hd": "",
        "latest": "",
        "copyright": "",
        "word": keyword,
        "s": "",
        "se": "",
        "tab": "",
        "width": "",
        "height": "",
        "face": 0,
        "istype": 2,
        "qc": "",
        "nc": "1",
        "fr": "",
        "expermode": "",
        "force": "",
        "cg": "",
        "pn": index,
        "rn": 1,
        "gsm": "1e",
    }
    response_text = http_get_text(
        url=BAIDU_IMAGE_SEARCH_URL,
        params=params,
        timeout=timeout,
    )

    image_url_list = re.findall(r'"thumbURL":"(.*?)",', response_text, re.S)
    if not image_url_list:
        raise RuntimeError("No image found for the given keyword/index")

    return image_url_list[0].replace("\\/", "/")


def download_keyword_index_image(
    keyword: str,
    index: int,
    output_dir: str,
    filename: str | None,
    timeout: int,
    force: bool,
) -> tuple[Path, str | None]:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    if filename:
        image_path = target_dir / filename
    else:
        image_path = target_dir / f"{sanitize_filename(keyword)}_{index}.jpg"

    if image_path.exists() and not force:
        return image_path, None

    image_url = fetch_image_url(keyword=keyword, index=index, timeout=timeout)
    image_bytes = http_get_bytes(image_url, timeout=timeout)
    image_path.write_bytes(image_bytes)
    return image_path, image_url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download one Baidu image by keyword + index"
    )
    parser.add_argument("--keyword", required=True, help="Image search keyword")
    parser.add_argument(
        "--index",
        type=int,
        default=0,
        help="Result index offset in Baidu image search",
    )
    parser.add_argument(
        "--output-dir",
        default="images",
        help="Directory to save the downloaded image",
    )
    parser.add_argument(
        "--filename",
        default=None,
        help="Custom output file name, defaults to <keyword>_<index>.jpg",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if local image already exists",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.index < 0:
        print("[ERROR] --index must be >= 0", file=sys.stderr)
        return 2

    try:
        image_path, image_url = download_keyword_index_image(
            keyword=args.keyword,
            index=args.index,
            output_dir=args.output_dir,
            filename=args.filename,
            timeout=args.timeout,
            force=args.force,
        )
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"[ERROR] Request failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if image_url is None:
        print(f"[OK] Cache hit: {image_path}")
    else:
        print(f"[OK] Downloaded: {image_path}")
        print(f"[INFO] Source URL: {image_url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
