import argparse
import json
from pathlib import Path
import sys
import time

import requests
from requests.exceptions import RequestException, Timeout

CONVERT_URL = "https://md2word.com/api/convert"
DEFAULT_TIMEOUT = 120
LARGE_FILE_TIMEOUT = 300
LARGE_FILE_BYTES = 512 * 1024
DEFAULT_RETRIES = 2
CHUNK_SIZE = 1024 * 256


def fail(message, **extra):
    payload = {"ok": False, "error": message}
    payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(1)


def detect_timeout(input_path: Path, user_timeout: int | None) -> int:
    if user_timeout and user_timeout > 0:
        return user_timeout
    try:
        size = input_path.stat().st_size
    except OSError:
        return DEFAULT_TIMEOUT
    return LARGE_FILE_TIMEOUT if size >= LARGE_FILE_BYTES else DEFAULT_TIMEOUT


def load_markdown(input_path: Path) -> str:
    try:
        return input_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        fail("failed to read markdown as utf-8", input=str(input_path))
    except Exception as exc:
        fail("failed to read input file", input=str(input_path), detail=str(exc))


def post_convert(data: dict, timeout: int) -> tuple[requests.Response, dict]:
    response = requests.post(CONVERT_URL, data=data, headers={"Accept": "application/json"}, timeout=timeout)
    try:
        result = response.json()
    except Exception:
        fail(
            "convert endpoint did not return valid json",
            status_code=response.status_code,
            response_text=response.text[:1000],
        )
    return response, result


def download_file(download_url: str, output_path: Path, timeout: int) -> int:
    with requests.get(download_url, timeout=timeout, stream=True) as download_resp:
        if not download_resp.ok:
            fail(
                "download endpoint returned error",
                status_code=download_resp.status_code,
                response_text=download_resp.text[:1000],
                download_url=download_url,
            )
        total = 0
        with output_path.open("wb") as f:
            for chunk in download_resp.iter_content(chunk_size=CHUNK_SIZE):
                if not chunk:
                    continue
                f.write(chunk)
                total += len(chunk)
        return total


def convert_once(input_path: Path, output_path: Path, auto_fix: bool, timeout: int) -> dict:
    content = load_markdown(input_path)
    data = {
        "content": content,
        "format": "pdf",
        "config": "{}",
        "input_method": "upload",
        "auto_fix": "true" if auto_fix else "false",
        "original_filename": input_path.name,
    }

    response, result = post_convert(data, timeout)
    if not response.ok:
        fail(
            "convert endpoint returned error",
            status_code=response.status_code,
            response=result,
        )

    download_url = result.get("download_url")
    filename = result.get("filename") or output_path.name
    if not download_url:
        fail("convert succeeded but download_url is missing", response=result)

    byte_count = download_file(download_url, output_path, timeout)
    return {
        "filename": filename,
        "download_url": download_url,
        "bytes": byte_count,
        "response": result,
    }


def main():
    parser = argparse.ArgumentParser(description="Convert a local Markdown file to PDF via md2word.com")
    parser.add_argument("--input", required=True, help="Input markdown file path")
    parser.add_argument("--output", help="Output pdf file path")
    parser.add_argument("--auto-fix", action="store_true", help="Enable md2word auto_fix")
    parser.add_argument("--timeout", type=int, default=0, help="HTTP timeout in seconds; 0 means auto")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help="Retry count for timeout/network errors")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        fail("input file does not exist", input=str(input_path))
    if input_path.suffix.lower() != ".md":
        fail("only .md input is supported", input=str(input_path))

    output_path = Path(args.output).expanduser().resolve() if args.output else input_path.with_suffix(".pdf")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    timeout = detect_timeout(input_path, args.timeout)
    attempts = max(1, args.retries + 1)
    errors = []

    for attempt in range(1, attempts + 1):
        try:
            result = convert_once(input_path, output_path, args.auto_fix, timeout)
            print(json.dumps({
                "ok": True,
                "input": str(input_path),
                "output": str(output_path),
                "filename": result["filename"],
                "download_url": result["download_url"],
                "bytes": result["bytes"],
                "timeout": timeout,
                "attempt": attempt,
                "retries": args.retries,
            }, ensure_ascii=False, indent=2))
            return
        except (Timeout, RequestException) as exc:
            errors.append({"attempt": attempt, "type": exc.__class__.__name__, "detail": str(exc)})
            if attempt >= attempts:
                fail(
                    "request to md2word convert endpoint failed after retries",
                    input=str(input_path),
                    timeout=timeout,
                    retries=args.retries,
                    attempts=attempt,
                    errors=errors,
                )
            time.sleep(min(2 * attempt, 5))
        except Exception as exc:
            fail("unexpected error during conversion", input=str(input_path), detail=str(exc))


if __name__ == "__main__":
    main()
