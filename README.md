# xhs-obs-archiver

[EN](https://github.com/Selaphina/xhs-obs-archiver?tab=readme-ov-file#xhs-obs-archiver)/[中文](https://github.com/Selaphina/xhs-obs-archiver?tab=readme-ov-file#中文说明)

**Python:** 3.9+

Archive Xiaohongshu notes into an Obsidian-friendly local repository with Markdown, downloaded images, and raw JSON snapshots.

Built on top of [`xiaohongshu-cli`](https://github.com/jackwener/xiaohongshu-cli).

## Features

- Archive one or many Xiaohongshu note URLs
- Save notes as Markdown for Obsidian
- Download images to local storage and embed them in Markdown
- Keep raw JSON responses for future reprocessing
- Save failed stdout/stderr for debugging
- Print batch summaries with success and failure counts

## Requirements

- Python 3.9+
- [`xiaohongshu-cli`](https://github.com/jackwener/xiaohongshu-cli)
- A valid Xiaohongshu session via `xhs login`

## Install

```bash
uv tool install xiaohongshu-cli
# or
pipx install xiaohongshu-cli
```

Then log in:

```powershell
xhs login
xhs status
```

## Usage

Archive from a URL list:

```powershell
Copy-Item config\xhs_urls.example.txt config\xhs_urls.txt
python scripts\archive_xhs.py
```

Archive a single note:

```powershell
python scripts\archive_xhs.py --input config\__empty__.txt --url "https://www.xiaohongshu.com/explore/<note_id>?xsec_token=<token>&xsec_source=pc_user"
```

Overwrite existing outputs:

```powershell
python scripts\archive_xhs.py --overwrite
```

## Output

```text
小红书归档/<author>/<year>/<date> <note_id> <title>.md
_assets/xiaohongshu/<author>/<year>/<note_id>/image_01.jpg
_raw/xiaohongshu/<author>/<year>/<date> <note_id> <title>.json
_raw_failed/xiaohongshu/<timestamp>_<note_id>.stdout.txt
```

At the end of each run, the script prints a summary like:

```text
Summary: success=7 failure=2
Failed note_ids:
- 69xxxxxxxxxxxxxxxxxxxxxx
- 69yyyyyyyyyyyyyyyyyyyyyy
```

## Notes

- Images are downloaded locally; if a download fails, the original URL is kept in Markdown.
- The script forces UTF-8 for the `xhs` subprocess to avoid Windows `gbk` encoding failures on emoji-containing posts.
- `xhs` runtime state is redirected into repository-local `.local_state/`.
- Requests are intentionally sequential to reduce account risk.

## Limitations

- No video download yet
- No author timeline sync yet
- Depends on upstream `xiaohongshu-cli` behavior and API stability

## Privacy

Do not publish personal cookies or private archive data.

Recommended `.gitignore` entries:

```gitignore
.local_state/
_assets/
_raw/
_raw_failed/
小红书归档/
config/xhs_urls.txt
```

## Disclaimer

Use this project responsibly and comply with Xiaohongshu's terms, local laws, and privacy expectations. This repository is intended for personal archival and research workflows.

---

# 中文说明

**Python 版本：** 3.9+

这是一个把小红书笔记归档到本地仓库的工具，适合配合 Obsidian 使用。它会把网页 URL 对应的笔记整理成 Markdown，下载图片到本地，并保留原始 JSON 快照，便于后续检索、重建和长期保存。

底层依赖 [`xiaohongshu-cli`](https://github.com/jackwener/xiaohongshu-cli)。

## 功能

- 支持单条或批量归档小红书笔记 URL
- 生成适合 Obsidian 的 Markdown
- 下载图片到本地并在 Markdown 中嵌入
- 保存原始 JSON 响应
- 保存失败时的 stdout / stderr 便于排查
- 批量执行结束后输出成功数、失败数和失败 note_id 列表

## 环境要求

- Python 3.9+
- 已安装 `xiaohongshu-cli`
- 已完成 `xhs login`

## 安装

```bash
uv tool install xiaohongshu-cli
# 或
pipx install xiaohongshu-cli
```

登录：

```powershell
xhs login
xhs status
```

## 使用方法

批量归档：

```powershell
Copy-Item config\xhs_urls.example.txt config\xhs_urls.txt
python scripts\archive_xhs.py
```

单条归档：

```powershell
python scripts\archive_xhs.py --input config\__empty__.txt --url "https://www.xiaohongshu.com/explore/<note_id>?xsec_token=<token>&xsec_source=pc_user"
```

覆盖已有输出：

```powershell
python scripts\archive_xhs.py --overwrite
```

## 输出目录

```text
小红书归档/<作者>/<年份>/<日期> <note_id> <标题>.md
_assets/xiaohongshu/<作者>/<年份>/<note_id>/image_01.jpg
_raw/xiaohongshu/<作者>/<年份>/<日期> <note_id> <标题>.json
_raw_failed/xiaohongshu/<时间戳>_<note_id>.stdout.txt
```

## 说明

- 图片会优先下载到本地；如果个别图片下载失败，Markdown 中会保留原图链接。
- 为了避免 Windows 下 `gbk` 编码导致 emoji 文章输出中断，脚本会强制 `xhs` 子进程使用 UTF-8。
- `xhs` 的运行状态被重定向到仓库本地 `.local_state/`，避免污染系统目录。
- 请求默认串行执行，不做并发，主要是为了降低风控风险。

## 当前限制

- 还不支持视频下载
- 还没有做博主主页增量同步
- 依赖上游 `xiaohongshu-cli` 的输出稳定性

## 隐私与安全

不要把 cookies、本地归档内容和失败快照提交到公开仓库。

建议忽略：

```gitignore
.local_state/
_assets/
_raw/
_raw_failed/
小红书归档/
config/xhs_urls.txt
```
