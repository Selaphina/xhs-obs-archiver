#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VAULT_ROOT = REPO_ROOT
DEFAULT_URL_FILE = REPO_ROOT / "config" / "xhs_urls.txt"
LOCAL_HOME = REPO_ROOT / ".local_state" / "home"
CONFIG_DIR_NAME = ".xiaohongshu-cli"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read Xiaohongshu notes via xhs CLI and archive them into an Obsidian-friendly vault."
    )
    parser.add_argument("--url", action="append", default=[], help="A Xiaohongshu note URL. Can be specified multiple times.")
    parser.add_argument("--input", type=Path, default=DEFAULT_URL_FILE, help="A text file with one Xiaohongshu note URL per line.")
    parser.add_argument("--vault-root", type=Path, default=DEFAULT_VAULT_ROOT, help="Obsidian vault root directory.")
    parser.add_argument("--delay-seconds", type=float, default=2.0, help="Delay between xhs requests. Keep this non-zero to reduce account risk.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing markdown, raw JSON, and downloaded image files.")
    return parser.parse_args()


def read_urls(input_file: Path, inline_urls: Iterable[str]) -> List[str]:
    urls: List[str] = []
    for url in inline_urls:
        cleaned = url.strip()
        if cleaned:
            urls.append(cleaned)

    if input_file.exists():
        for line in input_file.read_text(encoding="utf-8").splitlines():
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("#"):
                urls.append(cleaned)

    deduped: List[str] = []
    seen = set()
    for url in urls:
        if url not in seen:
            deduped.append(url)
            seen.add(url)
    return deduped


def bootstrap_local_xhs_home() -> Path:
    local_home = LOCAL_HOME
    local_config = local_home / CONFIG_DIR_NAME
    local_config.mkdir(parents=True, exist_ok=True)

    original_config = Path.home() / CONFIG_DIR_NAME
    if original_config.exists():
        for name in ("cookies.json", "token_cache.json", "index_cache.json"):
            source = original_config / name
            target = local_config / name
            if source.exists() and not target.exists():
                shutil.copy2(source, target)
    return local_home


def build_xhs_env() -> Dict[str, str]:
    local_home = bootstrap_local_xhs_home()
    env = os.environ.copy()
    env["HOME"] = str(local_home)
    env["USERPROFILE"] = str(local_home)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def decode_output(raw: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "cp936"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def sanitize_filename(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\r\n\t]+", " ", value or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned:
        cleaned = fallback
    return cleaned[:80].replace(" ", "_")


def extract_note_id(url: str) -> str:
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if path_parts:
        return path_parts[-1]
    return re.sub(r"\W+", "", url)[:24] or "unknown-note"


def save_failed_output(url: str, stdout: str, stderr: str) -> Tuple[Path, Path]:
    note_id = extract_note_id(url)
    failed_dir = REPO_ROOT / "_raw_failed" / "xiaohongshu"
    failed_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = "{}_{}".format(timestamp, sanitize_filename(note_id, "unknown"))
    stdout_path = failed_dir / (base_name + ".stdout.txt")
    stderr_path = failed_dir / (base_name + ".stderr.txt")
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    return stdout_path, stderr_path


def extract_json_object(text: str) -> Optional[str]:
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def parse_xhs_payload(stdout: str) -> Dict[str, Any]:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        candidate = extract_json_object(stdout)
        if not candidate:
            raise
        return json.loads(candidate)


def run_xhs_read(url: str) -> Dict[str, Any]:
    result = subprocess.run(
        ["xhs", "read", url, "--json"],
        capture_output=True,
        text=False,
        env=build_xhs_env(),
    )

    stdout = decode_output(result.stdout or b"").strip()
    stderr = decode_output(result.stderr or b"").strip()
    if not stdout:
        stdout_path, stderr_path = save_failed_output(url, stdout, stderr)
        raise RuntimeError(
            "xhs read produced no stdout. stderr: {} | failed_stdout: {} | failed_stderr: {}".format(
                stderr[:300], stdout_path, stderr_path
            )
        )

    try:
        payload = parse_xhs_payload(stdout)
    except json.JSONDecodeError as exc:
        stdout_path, stderr_path = save_failed_output(url, stdout, stderr)
        raise RuntimeError(
            "Failed to parse xhs JSON output: {} | stdout: {} | stderr: {} | failed_stdout: {} | failed_stderr: {}".format(
                exc, stdout[:300], stderr[:300], stdout_path, stderr_path
            )
        ) from exc

    if not payload.get("ok"):
        error = payload.get("error") or {}
        message = error.get("message") or "unknown xhs error"
        code = error.get("code") or "unknown"
        raise RuntimeError("xhs read failed [{}]: {}".format(code, message))

    return payload


def first_non_empty(*values: Any) -> Optional[Any]:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def get_path(obj: Any, *path: str) -> Any:
    current = obj
    for key in path:
        if isinstance(current, list):
            try:
                current = current[int(key)]
            except (ValueError, IndexError):
                return None
            continue
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def pick(obj: Dict[str, Any], paths: List[Tuple[str, ...]]) -> Any:
    for path in paths:
        value = get_path(obj, *path)
        if value is not None and value != "":
            return value
    return None


def listify(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def slugify(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\r\n\t]+", " ", value or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned:
        cleaned = fallback
    return cleaned[:80]


def parse_publish_time(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        timestamp = float(raw)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000.0
        return datetime.fromtimestamp(timestamp)
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return None
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y/%m/%d",
        ):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def normalize_note(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload.get("data") or {}
    note = pick(data, [("note",), ("note_card",), ("item",)])
    if not isinstance(note, dict):
        note = data

    user = pick(note, [("user",), ("author",), ("user_info",)])
    if not isinstance(user, dict):
        user = {}

    title = first_non_empty(note.get("title"), get_path(note, "note_card", "title"), get_path(data, "share_info", "title"), get_path(data, "shareInfo", "title"))
    content = first_non_empty(note.get("desc"), note.get("content"), note.get("text"), get_path(note, "note_card", "desc"), get_path(data, "share_info", "content"), get_path(data, "shareInfo", "content"))
    note_id = first_non_empty(note.get("note_id"), note.get("noteId"), note.get("id"), get_path(data, "note_id"), get_path(data, "noteId"), extract_note_id(url))
    author_name = first_non_empty(user.get("nickname"), user.get("name"), user.get("nick_name"), note.get("nickname"), "未知作者")
    author_id = first_non_empty(user.get("user_id"), user.get("userId"), user.get("id"), user.get("userid"))
    publish_time = parse_publish_time(first_non_empty(note.get("time"), note.get("publish_time"), note.get("publishTime"), note.get("last_update_time"), note.get("lastUpdateTime"), note.get("create_time"), note.get("createTime"), get_path(note, "interact_info", "time"), get_path(note, "interactInfo", "time")))

    tags = []
    for item in listify(first_non_empty(note.get("tag_list"), note.get("tagList"), note.get("tags"), note.get("topics"))):
        if isinstance(item, dict):
            tag_value = first_non_empty(item.get("name"), item.get("tag"), item.get("topic_name"), item.get("topicName"))
        else:
            tag_value = item
        if isinstance(tag_value, str) and tag_value.strip():
            tags.append(tag_value.strip().lstrip("#"))

    images: List[str] = []
    image_sources = listify(first_non_empty(note.get("image_list"), note.get("imageList"), note.get("images"), get_path(note, "note_card", "image_list"), get_path(note, "note_card", "imageList")))
    for item in image_sources:
        if isinstance(item, dict):
            image_url = first_non_empty(item.get("url"), item.get("image_url"), item.get("imageUrl"), item.get("master_url"), item.get("masterUrl"), item.get("default"), item.get("urlDefault"), item.get("urlPre"), get_path(item, "infoList", "0", "url"), get_path(item, "info_list", "0", "url"))
            if image_url:
                images.append(str(image_url))
        elif isinstance(item, str) and item.strip():
            images.append(item.strip())

    return {
        "source_url": url,
        "note_id": str(note_id),
        "title": str(title or "无标题"),
        "content": str(content or ""),
        "author_name": str(author_name),
        "author_id": str(author_id) if author_id is not None else "",
        "publish_time": publish_time,
        "tags": tags,
        "images": images,
        "image_downloads": [],
        "raw_data": data,
    }


def format_datetime(value: Optional[datetime]) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def infer_image_extension(image_url: str, content_type: str = "") -> str:
    path = urlparse(image_url).path.lower()
    for extension in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"):
        if path.endswith(extension):
            return extension
    normalized_type = content_type.lower().split(";")[0].strip()
    mapping = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif", "image/bmp": ".bmp", "image/avif": ".avif"}
    return mapping.get(normalized_type, ".jpg")


def download_images(vault_root: Path, note: Dict[str, Any], overwrite: bool) -> List[Dict[str, str]]:
    if not note["images"]:
        return []

    published = note["publish_time"] or datetime.now()
    author_dir = slugify(note["author_name"], "未知作者")
    assets_dir = vault_root / "_assets" / "xiaohongshu" / author_dir / published.strftime("%Y") / sanitize_filename(note["note_id"], "note")
    assets_dir.mkdir(parents=True, exist_ok=True)

    downloads: List[Dict[str, str]] = []
    for index, image_url in enumerate(note["images"], start=1):
        request = Request(image_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.xiaohongshu.com/"})
        fallback_name = "image_{:02d}".format(index)
        try:
            with urlopen(request, timeout=30) as response:
                content = response.read()
                extension = infer_image_extension(image_url, response.headers.get("Content-Type", ""))
            local_path = assets_dir / (fallback_name + extension)
            if overwrite or not local_path.exists():
                local_path.write_bytes(content)
            downloads.append({"source_url": image_url, "local_path": str(local_path), "vault_relative_path": local_path.relative_to(vault_root).as_posix(), "status": "downloaded"})
        except Exception:
            downloads.append({"source_url": image_url, "local_path": "", "vault_relative_path": "", "status": "failed"})
    return downloads


def make_markdown(note: Dict[str, Any], archive_time: datetime) -> str:
    title = note["title"]
    author_name = note["author_name"]
    note_id = note["note_id"]
    publish_time = format_datetime(note["publish_time"])
    archive_time_text = format_datetime(archive_time)
    tags_yaml = json.dumps(note["tags"], ensure_ascii=False)
    lines = [
        "---",
        'type: "xiaohongshu-note"',
        "source: xiaohongshu",
        'source_url: "{}"'.format(note["source_url"].replace('"', '\\"')),
        'note_id: "{}"'.format(note_id.replace('"', '\\"')),
        'author: "{}"'.format(author_name.replace('"', '\\"')),
        'author_id: "{}"'.format(note["author_id"].replace('"', '\\"')),
        'published_at: "{}"'.format(publish_time),
        'archived_at: "{}"'.format(archive_time_text),
        "tags: {}".format(tags_yaml),
        "---",
        "",
        "# {}".format(title),
        "",
        "## 信息",
        "",
        "- 作者：{}".format(author_name),
        "- 原文：{}".format(note["source_url"]),
        "- 发布时间：{}".format(publish_time or "未知"),
        "- 归档时间：{}".format(archive_time_text),
        "- 笔记 ID：{}".format(note_id),
    ]
    if note["tags"]:
        lines.append("- 标签：{}".format(" / ".join("#{}".format(tag) for tag in note["tags"])))

    lines.extend(["", "## 正文", ""])
    body = note["content"].strip()
    if body:
        lines.append(body)
    else:
        lines.append("_未从接口中提取到正文文本。_")

    if note["image_downloads"]:
        lines.extend(["", "## 图片", ""])
        for image in note["image_downloads"]:
            if image["status"] == "downloaded":
                lines.append("![[{}]]".format(image["vault_relative_path"]))
            else:
                lines.append("- 下载失败，保留原链接：{}".format(image["source_url"]))

    lines.extend(["", "## 归档说明", "", "- 本文由 `scripts/archive_xhs.py` 调用 `xhs read` 自动归档。", "- 图片已优先下载到本地 `_assets/xiaohongshu/`，下载失败时回退保留原链接。"])
    return "\n".join(lines) + "\n"


def build_paths(vault_root: Path, note: Dict[str, Any]) -> Tuple[Path, Path]:
    published = note["publish_time"] or datetime.now()
    author_dir = slugify(note["author_name"], "未知作者")
    title_part = slugify(note["title"], note["note_id"])
    note_dir = vault_root / "小红书归档" / author_dir / published.strftime("%Y")
    filename = "{} {} {}.md".format(published.strftime("%Y-%m-%d"), note["note_id"], title_part)
    raw_filename = "{} {} {}.json".format(published.strftime("%Y-%m-%d"), note["note_id"], title_part)
    markdown_path = note_dir / filename
    raw_path = vault_root / "_raw" / "xiaohongshu" / author_dir / published.strftime("%Y") / raw_filename
    return markdown_path, raw_path


def write_file(path: Path, content: str, overwrite: bool) -> bool:
    if path.exists() and not overwrite:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def archive_note(vault_root: Path, note: Dict[str, Any], payload: Dict[str, Any], overwrite: bool) -> Tuple[Path, Path, bool, bool]:
    archive_time = datetime.now()
    note["image_downloads"] = download_images(vault_root, note, overwrite)
    markdown_path, raw_path = build_paths(vault_root, note)
    markdown_content = make_markdown(note, archive_time)
    raw_content = json.dumps(payload, ensure_ascii=False, indent=2)
    wrote_markdown = write_file(markdown_path, markdown_content, overwrite)
    wrote_raw = write_file(raw_path, raw_content, overwrite)
    return markdown_path, raw_path, wrote_markdown, wrote_raw


def main() -> int:
    args = parse_args()
    vault_root = args.vault_root.resolve()
    urls = read_urls(args.input, args.url)

    if not urls:
        print("No URLs provided. Use --url or create config/xhs_urls.txt", file=sys.stderr)
        return 1

    failures = 0
    successes = 0
    failed_notes: List[str] = []
    for index, url in enumerate(urls, start=1):
        current_note_id = extract_note_id(url)
        print("[{}/{}] Reading {}".format(index, len(urls), url))
        try:
            payload = run_xhs_read(url)
            note = normalize_note(url, payload)
            current_note_id = note["note_id"]
            markdown_path, raw_path, wrote_markdown, wrote_raw = archive_note(vault_root=vault_root, note=note, payload=payload, overwrite=args.overwrite)
            print("  note_id: {}".format(note["note_id"]))
            print("  markdown: {}{}".format(markdown_path, "" if wrote_markdown else " (skipped)"))
            print("  raw_json: {}{}".format(raw_path, "" if wrote_raw else " (skipped)"))
            downloaded_count = len([item for item in note["image_downloads"] if item["status"] == "downloaded"])
            print("  images: {}/{} downloaded".format(downloaded_count, len(note["image_downloads"])))
            successes += 1
        except Exception as exc:
            failures += 1
            failed_notes.append(current_note_id)
            print("  error: {}".format(exc), file=sys.stderr)

        if index < len(urls):
            time.sleep(max(args.delay_seconds, 0.0))

    print("Summary: success={} failure={}".format(successes, failures))
    if failed_notes:
        print("Failed note_ids:")
        for note_id in failed_notes:
            print("- {}".format(note_id))

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
