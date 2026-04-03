# xhs-obs-archiver

Archive Xiaohongshu notes into a local, Obsidian-friendly repository with Markdown, downloaded images, and raw JSON snapshots.

This project is built around [`xiaohongshu-cli`](https://github.com/jackwener/xiaohongshu-cli) and is designed for people who want a personal, searchable archive of Xiaohongshu posts they care about, even if the original post is later deleted, hidden, or edited.

## Features

- Archive one or many Xiaohongshu note URLs
- Convert note content into Markdown files suitable for Obsidian
- Download note images to local storage and embed them in Markdown
- Preserve raw API responses for future reprocessing
- Keep failed outputs for debugging and retry
- Reuse an existing `xhs login` session
- Print batch summaries with success and failure counts

## How It Works

For each Xiaohongshu note URL, the script will:

1. Call `xhs read <url> --json`
2. Parse note metadata and content
3. Save note content as Markdown
4. Download all available images to local storage
5. Save the original JSON response alongside the archive
6. Print a summary at the end of the batch run

## Repository Layout

```text
.
├─ config/
│  ├─ xhs_urls.example.txt
│  └─ xhs_urls.txt
├─ scripts/
│  └─ archive_xhs.py
├─ 小红书归档/
│  └─ <author>/<year>/*.md
├─ _assets/
│  └─ xiaohongshu/<author>/<year>/<note_id>/image_*.jpg
├─ _raw/
│  └─ xiaohongshu/<author>/<year>/*.json
├─ _raw_failed/
│  └─ xiaohongshu/*.stdout.txt
└─ README.md
```

## Requirements

- Windows PowerShell environment was the initial target, but the script itself is plain Python
- Python 3.9+
- [`xiaohongshu-cli`](https://github.com/jackwener/xiaohongshu-cli)
- A valid Xiaohongshu login session via `xhs login`

## Installation

Install `xiaohongshu-cli` first.

If you use `uv`:

```bash
uv tool install xiaohongshu-cli
```

If you use `pipx`:

```bash
pipx install xiaohongshu-cli
```

Then log in:

```powershell
xhs login
xhs status
```

## Usage

### Archive from a URL list

Create your input file from the example template:

```powershell
Copy-Item config\xhs_urls.example.txt config\xhs_urls.txt
```

Put one Xiaohongshu note URL per line into `config\xhs_urls.txt`, then run:

```powershell
python scripts\archive_xhs.py
```

### Archive a single note

```powershell
python scripts\archive_xhs.py --input config\__empty__.txt --url "https://www.xiaohongshu.com/explore/<note_id>?xsec_token=<token>&xsec_source=pc_user"
```

### Overwrite existing files

```powershell
python scripts\archive_xhs.py --overwrite
```

## Output Format

### Markdown

Archived notes are stored under:

```text
小红书归档/<author>/<year>/<date> <note_id> <title>.md
```

Each note contains:

- frontmatter metadata
- source URL
- author and publish time
- note text content
- local Obsidian image embeds such as `![[...]]`

### Images

Images are downloaded to:

```text
_assets/xiaohongshu/<author>/<year>/<note_id>/image_01.jpg
```

### Raw JSON

Raw responses are saved to:

```text
_raw/xiaohongshu/<author>/<year>/<date> <note_id> <title>.json
```

### Failed Raw Output

If `xiaohongshu-cli` returns broken or truncated output, the script stores the original stdout and stderr for inspection:

```text
_raw_failed/xiaohongshu/<timestamp>_<note_id>.stdout.txt
_raw_failed/xiaohongshu/<timestamp>_<note_id>.stderr.txt
```

## Batch Summary

At the end of each run, the script prints a summary like:

```text
Summary: success=7 failure=2
Failed note_ids:
- 69xxxxxxxxxxxxxxxxxxxxxx
- 69yyyyyyyyyyyyyyyyyyyyyy
```

## Notes on Reliability

This project includes several workarounds for common Windows and CLI issues:

- Forces UTF-8 for the `xhs` subprocess to avoid `gbk` encoding crashes on emoji-containing posts
- Redirects `xhs` runtime state into the repository-local `.local_state/` directory
- Saves failed outputs for postmortem debugging
- Avoids parallel Xiaohongshu requests to reduce account risk

## Limitations

- No video download yet
- No automatic author timeline sync yet
- Requires a valid logged-in Xiaohongshu session
- Depends on upstream `xiaohongshu-cli` behavior and API stability

## Privacy and Security

Do not commit personal cookies or private archive data to a public repository.

At minimum, make sure the following paths are ignored by Git in real use:

```gitignore
.local_state/
_assets/
_raw/
_raw_failed/
小红书归档/
config/xhs_urls.txt
```

## Roadmap

- Incremental sync from author profiles
- Better duplicate detection
- Video/media preservation
- Metadata enrichment and tagging strategies
- Scheduled archive jobs

## Acknowledgements

- [`xiaohongshu-cli`](https://github.com/jackwener/xiaohongshu-cli) for the Xiaohongshu access layer
- [Obsidian](https://obsidian.md/) for local knowledge-base workflows

## Disclaimer

Use this project responsibly and comply with Xiaohongshu's terms, local laws, and privacy expectations. This repository is intended for personal archival and research workflows.
