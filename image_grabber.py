"""
Image Grabber CLI - Advanced Image Downloader

Author: Ramin Eslami
Telegram: @resonea

A powerful command-line tool for downloading high-resolution images from various search engines.
Supports DuckDuckGo Images, Google Custom Search API, and browser-based scraping.

Features:
- Multiple search engines (DuckDuckGo, Google CSE, Browser automation)
- Concurrent downloads with configurable limits
- Image filtering by dimensions
- Automatic file type detection
- Rate limiting and retry mechanisms
- Persian language support

Usage Examples:
    # Simple usage with DuckDuckGo
    python image_grabber.py --query "cats" --limit 50
    
    # Using Google Custom Search
    python image_grabber.py --query "تخت جمشید" --limit 100 --engine google --google-api-key YOUR_KEY --google-cx YOUR_CX
    
    # Browser-based scraping
    python image_grabber.py --query "nature" --limit 30 --engine browser --show-browser
"""

import argparse
import concurrent.futures
import hashlib
import os
import re
import threading
import time
import sys
import asyncio
import base64
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
try:
	from ddgs import DDGS
	from ddgs.exceptions import RatelimitException
except ImportError:
	from duckduckgo_search import DDGS
	from duckduckgo_search.exceptions import RatelimitException
from tqdm import tqdm
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import undetected_chromedriver as uc

# Ensure Windows selector loop policy set (left for compatibility)
if sys.platform.startswith("win"):
	asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Thread-local session for connection pooling per worker
_thread_local = threading.local()


def log(verbose: bool, message: str) -> None:
	if verbose:
		print(message, flush=True)


def get_session(timeout: int) -> requests.Session:
	if getattr(_thread_local, "session", None) is None:
		s = requests.Session()
		s.headers.update({
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win32; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
			"Accept": "*/*",
			"Accept-Language": "en-US,en;q=0.9",
			"Referer": "https://www.google.com/",
		})
		# Configure session for better connection handling
		adapter = requests.adapters.HTTPAdapter(
			pool_connections=1,
			pool_maxsize=1,
			max_retries=3
		)
		s.mount('http://', adapter)
		s.mount('https://', adapter)
		_thread_local.session = s
	_thread_local.timeout = timeout
	return _thread_local.session


def sanitize_folder_name(name: str) -> str:
	name = name.strip()
	name = re.sub(r"[\\/:*?\"<>|]", "_", name)
	name = re.sub(r"\s+", " ", name)
	return name[:100] if len(name) > 100 else name


def choose_best_url(result: Dict) -> Optional[Tuple[str, Optional[int], Optional[int]]]:
	candidates: List[Tuple[str, Optional[int], Optional[int]]] = []
	for key in ("image", "url", "thumbnail"):
		url = result.get(key) or result.get("image") if key == "url" else result.get(key)
		if url:
			w = result.get("width") or result.get("image_width")
			h = result.get("height") or result.get("image_height")
			candidates.append((url, w, h))
	if not candidates:
		return None
	candidates.sort(key=lambda x: (x[1] or 0) * (x[2] or 0), reverse=True)
	return candidates[0]


def fetch_results_ddg(query: str, limit: int, min_width: int, min_height: int) -> List[Dict]:
	attempt = 0
	wait_seconds = 2
	while True:
		try:
			with DDGS() as ddgs:
				results = []
				for r in ddgs.images(
					query=query,
					region="wt-wt",
					safesearch="off",
					size=None,
					color=None,
					type_image=None,
					layout=None,
					max_results=max(10, limit * 2),
				):
					w = r.get("width") or r.get("image_width") or 0
					h = r.get("height") or r.get("image_height") or 0
					if w >= min_width and h >= min_height:
						results.append(r)
						if len(results) >= limit:
							break
				return results
		except RatelimitException:
			attempt += 1
			if attempt > 3:
				raise
			time.sleep(wait_seconds)
			wait_seconds = min(wait_seconds * 2, 30)


def fetch_results_google_cse(api_key: str, cx: str, query: str, limit: int, min_width: int, min_height: int) -> List[Dict]:
	results: List[Dict] = []
	start_index = 1
	session = get_session(timeout=20)
	while len(results) < limit and start_index <= 91:
		num = min(10, limit - len(results))
		resp = session.get(
			"https://www.googleapis.com/customsearch/v1",
			params={
				"q": query,
				"searchType": "image",
				"num": num,
				"start": start_index,
				"safe": "off",
				"key": api_key,
				"cx": cx,
			},
			timeout=_thread_local.timeout,
		)
		if resp.status_code != 200:
			break
		data = resp.json()
		items = data.get("items") or []
		if not items:
			break
		for it in items:
			link = it.get("link")
			image_info = it.get("image") or {}
			w = int(image_info.get("width")) if image_info.get("width") else 0
			h = int(image_info.get("height")) if image_info.get("height") else 0
			if w >= min_width and h >= min_height and link:
				results.append({"image": link, "width": w, "height": h})
				if len(results) >= limit:
					break
		start_index += len(items)
	return results


def fetch_results_browser_google(query: str, limit: int, min_width: int, min_height: int, *, verbose: bool = False, max_time_seconds: int = 90, show_browser: bool = False) -> List[Dict]:
	results: List[Dict] = []
	options = ChromeOptions()
	if not show_browser:
		options.add_argument("--headless=new")
	options.add_argument("--no-sandbox")
	options.add_argument("--disable-gpu")
	options.add_argument("--disable-dev-shm-usage")
	options.add_argument("--window-size=1366,768")
	options.add_argument("--disable-blink-features=AutomationControlled")
	options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
	
	# Use webdriver-manager to automatically handle ChromeDriver version
	try:
		service = Service(ChromeDriverManager().install())
		driver = uc.Chrome(options=options, service=service)
	except Exception as e:
		log(verbose, f"[browser] webdriver-manager failed, trying direct: {e}")
		# Create new options object for retry
		options_retry = ChromeOptions()
		if not show_browser:
			options_retry.add_argument("--headless=new")
		options_retry.add_argument("--no-sandbox")
		options_retry.add_argument("--disable-gpu")
		options_retry.add_argument("--disable-dev-shm-usage")
		options_retry.add_argument("--window-size=1366,768")
		options_retry.add_argument("--disable-blink-features=AutomationControlled")
		options_retry.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
		driver = uc.Chrome(options=options_retry)
	start_time = time.monotonic()
	try:
		url = f"https://www.google.com/search?tbm=isch&q={requests.utils.quote(query)}"
		log(verbose, f"[browser] goto: {url}")
		driver.get(url)
		time.sleep(2)
		# Try to accept consent if present
		for selector in [
			"button[aria-label='Accept all']",
			"button[aria-label='I agree']",
			"#L2AGLb",
		]:
			try:
				btns = driver.find_elements(By.CSS_SELECTOR, selector)
				if btns:
					btns[0].click()
					log(verbose, f"[browser] clicked consent: {selector}")
					time.sleep(1)
					break
			except Exception:
				pass
		thumb_selector = "img[jsname='Q4LuWd']"
		large_selector = "img.n3VNCb"
		index = 0
		last_count = 0
		empty_scrolls = 0
		while len(results) < limit:
			# Time budget
			if time.monotonic() - start_time > max_time_seconds:
				log(verbose, "[browser] timeout waiting for enough results")
				break
			thumbs = driver.find_elements(By.CSS_SELECTOR, thumb_selector)
			count = len(thumbs)
			if count == 0:
				log(verbose, "[browser] no thumbnails yet, scrolling")
				driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
				time.sleep(1)
				continue
			if count == last_count:
				empty_scrolls += 1
			else:
				empty_scrolls = 0
				last_count = count
			if empty_scrolls >= 6 and index >= count:
				log(verbose, "[browser] reached end of page (no new thumbs)")
				break
			if index >= count:
				log(verbose, f"[browser] need more thumbs; scrolling (have {count})")
				driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
				time.sleep(0.8)
				continue
			# Try clicking a thumbnail
			try:
				log(verbose, f"[browser] click thumb #{index+1}/{count}")
				thumbs[index].click()
				time.sleep(0.8)
			except Exception as e:
				log(verbose, f"[browser] thumb click failed: {e}")
				index += 1
				continue
			# Collect large image candidates
			candidates = driver.find_elements(By.CSS_SELECTOR, large_selector)
			if not candidates:
				log(verbose, "[browser] no large images yet")
				index += 1
				continue
			picked = False
			for img in candidates[:5]:
				src = img.get_attribute("src") or ""
				if not src.startswith("http"):
					continue
				try:
					w = img.get_property("naturalWidth") or 0
					h = img.get_property("naturalHeight") or 0
				except Exception:
					w = 0
					h = 0
				results.append({"image": src, "width": int(w), "height": int(h)})
				log(verbose, f"[browser] added image {len(results)}: {int(w)}x{int(h)}")
				picked = True
				break
			if not picked:
				log(verbose, "[browser] no valid candidate srcs")
			index += 1
	finally:
		driver.quit()
	return results[:limit]


def guess_ext_from_headers(headers: Dict[str, str], url: str) -> str:
	content_type = headers.get("Content-Type", "").lower()
	if "image/jpeg" in content_type or ".jpg" in url.lower() or ".jpeg" in url.lower():
		return ".jpg"
	if "image/png" in content_type or ".png" in url.lower():
		return ".png"
	if "image/webp" in content_type or ".webp" in url.lower():
		return ".webp"
	if "image/gif" in content_type or ".gif" in url.lower():
		return ".gif"
	return ".img"


def download_one(index_and_result: Tuple[int, Dict], out_dir: Path, timeout: int, verbose: bool, max_retries: int = 2) -> Optional[Path]:
	idx, result = index_and_result
	choice = choose_best_url(result)
	if not choice:
		log(verbose, f"[dl] #{idx} no usable url")
		return None
	url, w, h = choice
	hsh = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
	name_base = f"{idx:04d}_{w or 0}x{h or 0}_{hsh}"

	# Handle data URLs directly
	if url.startswith("data:"):
		try:
			header, b64data = url.split(",", 1)
			mime = ""
			if ";base64" in header:
				mime = header.split(";")[0][5:].lower()
			data = base64.b64decode(b64data)
			ext = ".img"
			if "jpeg" in mime:
				ext = ".jpg"
			elif "png" in mime:
				ext = ".png"
			elif "webp" in mime:
				ext = ".webp"
			elif "gif" in mime:
				ext = ".gif"
			out_file = out_dir / f"{name_base}{ext}"
			if not out_file.exists() or out_file.stat().st_size == 0:
				with open(out_file, "wb") as f:
					f.write(data)
			log(verbose, f"[dl] #{idx} saved data URL -> {out_file.name}")
			return out_file
		except Exception as e:
			log(verbose, f"[dl] #{idx} data URL failed: {e}")
			return None

	session = get_session(timeout)
	last_err: Optional[Exception] = None
	for attempt in range(max_retries + 1):
		try:
			resp = session.get(url, stream=True, timeout=_thread_local.timeout)
			if resp.status_code != 200:
				raise RuntimeError(f"status {resp.status_code}")
			ext = guess_ext_from_headers(resp.headers, url)
			out_file = out_dir / f"{name_base}{ext}"
			if out_file.exists() and out_file.stat().st_size > 0:
				log(verbose, f"[dl] #{idx} exists, skip -> {out_file.name}")
				return out_file
			with open(out_file, "wb") as f:
				for chunk in resp.iter_content(chunk_size=64 * 1024):
					if chunk:
						f.write(chunk)
			log(verbose, f"[dl] #{idx} OK -> {out_file.name}")
			return out_file
		except Exception as e:
			last_err = e
			log(verbose, f"[dl] #{idx} attempt {attempt+1} failed: {e}")
			time.sleep(1 + attempt)
			continue
	if last_err:
		log(verbose, f"[dl] #{idx} failed permanently: {last_err}")
	return None


def run(query: str, limit: int, out_base: Path, max_concurrent: int, timeout: int, min_width: int, min_height: int, engine: str, google_api_key: Optional[str], google_cx: Optional[str], *, verbose: bool = False, show_browser: bool = False) -> None:
	topic_dir_name = sanitize_folder_name(query)
	out_dir = out_base / topic_dir_name
	out_dir.mkdir(parents=True, exist_ok=True)

	results: List[Dict] = []
	try:
		if engine == "google":
			if not google_api_key or not google_cx:
				raise SystemExit("Google engine selected but --google-api-key and --google-cx are required.")
			results = fetch_results_google_cse(google_api_key, google_cx, query, limit, min_width, min_height)
		elif engine == "browser":
			results = fetch_results_browser_google(query, limit, min_width, min_height, verbose=verbose, show_browser=show_browser)
		else:
			results = fetch_results_ddg(query, limit, min_width, min_height)
	except RatelimitException:
		print("DuckDuckGo rate-limited. Switching to browser crawling...")
		try:
			results = fetch_results_browser_google(query, limit, min_width, min_height, verbose=verbose, show_browser=show_browser)
		except Exception as e:
			print(f"Browser crawling failed: {e}")
			return
	except Exception as e:
		print(f"Search failed: {e}")
		return

	if not results:
		print("No results matched the filters.")
		return

	print(f"Found {len(results)} candidates. Starting downloads...")
	success_count = 0
	with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as ex:
		jobs = list(enumerate(results))
		progress = tqdm(total=len(jobs), desc="Downloading", unit="img")
		for saved in ex.map(lambda x: download_one(x, out_dir, timeout, verbose), jobs):
			if saved:
				success_count += 1
			progress.update(1)
		progress.close()

	print(f"Saved {success_count}/{len(results)} images to: {out_dir}")


def run_simple(query: str) -> None:
	engine = "ddg"  # Use DuckDuckGo instead of browser to avoid ChromeDriver issues
	run(
		query=query,
		limit=10,
		out_base=Path("downloads"),
		max_concurrent=2,
		timeout=20,
		min_width=0,
		min_height=0,
		engine=engine,
		google_api_key=os.environ.get("GOOGLE_API_KEY"),
		google_cx=os.environ.get("GOOGLE_CX"),
		verbose=True,
		show_browser=False,
	)


def main() -> None:
	if len(sys.argv) == 1:
		# فقط همین کلمه را عوض کن
		run_simple("گربه")
		return

	parser = argparse.ArgumentParser(description="Download images for a topic from search engines.")
	parser.add_argument("--query", "-q", required=True, help="Search topic text.")
	parser.add_argument("--limit", "-n", type=int, default=50, help="Number of images to download.")
	parser.add_argument("--out", "-o", default="downloads", help="Base output directory.")
	parser.add_argument("--max-concurrent", type=int, default=8, help="Max concurrent downloads.")
	parser.add_argument("--timeout", type=int, default=20, help="Per-request timeout in seconds.")
	parser.add_argument("--min-width", type=int, default=0, help="Minimum image width filter.")
	parser.add_argument("--min-height", type=int, default=0, help="Minimum image height filter.")
	parser.add_argument("--engine", choices=["ddg", "google", "browser"], default="ddg", help="Search engine backend")
	parser.add_argument("--google-api-key", default=os.environ.get("GOOGLE_API_KEY"), help="Google API key for Custom Search (env GOOGLE_API_KEY)")
	parser.add_argument("--google-cx", default=os.environ.get("GOOGLE_CX"), help="Google Custom Search CX (env GOOGLE_CX)")
	parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
	parser.add_argument("--show-browser", action="store_true", help="Show real browser window during crawling")
	args = parser.parse_args()

	out_base = Path(args.out)
	run(
		query=args.query,
		limit=args.limit,
		out_base=out_base,
		max_concurrent=max(1, args.__dict__["max_concurrent"]),
		timeout=args.timeout,
		min_width=args.__dict__["min_width"],
		min_height=args.__dict__["min_height"],
		engine=args.engine,
		google_api_key=args.__dict__["google_api_key"],
		google_cx=args.__dict__["google_cx"],
		verbose=bool(args.__dict__["verbose"]),
		show_browser=bool(args.__dict__["show_browser"]),
	)


if __name__ == "__main__":
	main()
