# Image Grabber CLI

**Author:** Ramin Eslami  
**Telegram:** @resonea

Downloads highest-resolution images for a given topic.

- Default backend: DuckDuckGo Images (no key, can rate-limit)
- Optional backend: Google Custom Search (stable, needs API key and CX)

## Setup

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

## Usage (DuckDuckGo)

```bash
python image_grabber.py --query "cats" --limit 50 --out downloads --engine ddg
```

## Usage (Google Custom Search)

1) Create an API key and a Custom Search Engine (CX) that searches the whole web.
2) Set env vars or pass flags.

```bash
set GOOGLE_API_KEY=YOUR_KEY
set GOOGLE_CX=YOUR_CX
python image_grabber.py -q "گربه" -n 50 -o downloads --engine google
# or explicitly:
python image_grabber.py -q "گربه" -n 50 -o downloads --engine google --google-api-key YOUR_KEY --google-cx YOUR_CX
```

## Options

- `--query` / `-q`: search topic.
- `--limit` / `-n`: number of images.
- `--out` / `-o`: base output directory; per-topic subfolder is created.
- `--max-concurrent`: max concurrent downloads (default 8).
- `--timeout`: per-request timeout seconds (default 20).
- `--min-width`, `--min-height`: filter by minimum dimensions.
- `--engine`: `ddg` (default) or `google`.
- `--google-api-key`, `--google-cx`: required if `--engine google`.

Example Persian topics:

```bash
python image_grabber.py -q "تخت جمشید" -n 100 -o downloads --min-width 800 --min-height 600 --engine google
```
