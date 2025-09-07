# Image Grabber CLI

**Author:** Ramin Eslami  
**Telegram:** @resonea

Downloads highest-resolution images for a given topic.

## Use Cases

This tool is perfect for various applications:

### 🤖 **Machine Learning & AI**
- **Dataset Collection**: Gather training data for computer vision models
- **Image Classification**: Collect labeled images for classification tasks
- **Object Detection**: Build datasets for detecting specific objects
- **Style Transfer**: Collect images for neural style transfer models
- **GAN Training**: Gather diverse images for Generative Adversarial Networks

### 🎨 **Creative Projects**
- **Digital Art**: Collect reference images for digital artwork
- **Graphic Design**: Gather inspiration and assets for design projects
- **Content Creation**: Build image libraries for blogs, websites, presentations
- **Mood Boards**: Create visual collections for design inspiration

### 📚 **Research & Education**
- **Academic Research**: Collect visual data for research papers
- **Educational Materials**: Gather images for teaching presentations
- **Cultural Studies**: Collect images of historical sites, artifacts, traditions
- **Language Learning**: Gather visual context for vocabulary learning

### 🏢 **Business Applications**
- **Product Research**: Collect competitor product images
- **Market Analysis**: Gather visual data for market research
- **Brand Monitoring**: Track how your brand appears in search results
- **Content Marketing**: Build image libraries for marketing campaigns

### 🔍 **Technical Applications**
- **Web Scraping**: Automated image collection for various purposes
- **Data Analysis**: Visual data collection for analytical projects
- **Testing**: Gather test images for software development
- **Documentation**: Collect screenshots and visual examples

## Features

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
