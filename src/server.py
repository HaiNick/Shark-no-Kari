"""
Shark-no-Kari - Streamable HTTP transport for claude.ai
Exposes Scrapling's fetchers as MCP tools so Claude can scrape
pages that web_fetch fails on (GitHub, Cloudflare-protected, etc.)
"""

import os
import re
import asyncio
import logging
import html2text
import tomllib
from pathlib import Path
from typing import Optional
from mcp.server.fastmcp import FastMCP

with open(Path(__file__).resolve().parent.parent / "pyproject.toml", "rb") as f:
    __version__ = tomllib.load(f)["project"]["version"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shark-no-kari")

# --------------------------------------------------------------------------- #
# Server setup
# --------------------------------------------------------------------------- #

API_KEY = os.getenv("MCP_API_KEY", "")
PROXY_URL = os.getenv("PROXY_URL", "")

# socks5:// resolves DNS locally; socks5h:// delegates DNS to the proxy.
# VPN proxies (NordVPN, etc.) expect proxy-side resolution, so normalize.
if PROXY_URL.startswith("socks5://"):
    PROXY_URL = "socks5h://" + PROXY_URL[len("socks5://"):]
    logger.warning(
        "PROXY_URL had socks5:// scheme — rewritten to socks5h:// "
        "(delegates DNS to the proxy). Update your .env to silence this warning."
    )

mcp = FastMCP(
    "Shark-no-Kari",
    instructions=(
        "Shark-no-Kari is a web fetching tool. Use it when:\n"
        "- web_fetch fails with 'Failed to fetch' errors\n"
        "- The target is GitHub raw content, blob URLs, or githubusercontent.com\n"
        "- The site is behind Cloudflare or other bot protection\n"
        "- The page requires JavaScript rendering\n\n"
        "Tool selection:\n"
        "- fetch_page: Try this FIRST. Fast HTTP request with stealth headers. "
        "Works for GitHub, docs sites, static pages, and most URLs.\n"
        "- stealth_fetch_page: Use ONLY if fetch_page fails or the site is known "
        "to have heavy bot protection (Cloudflare Turnstile, etc.). "
        "Slower (5-15s) as it launches a real headless browser.\n"
        "- extract_elements: Use when you need structured data from a page. "
        "Pass a dict of field names to CSS selectors and get JSON back. "
        "Set use_stealth=True for bot-protected sites.\n\n"
        "Tips:\n"
        "- Use css_selector on fetch_page/stealth_fetch_page for simple single-selector extraction\n"
        "- Use extract_elements when you need multiple different pieces of data from one page\n"
        "- to_markdown=True (default) converts HTML to readable text\n"
        "- Always try fetch_page before stealth_fetch_page\n"
        "- get_youtube_transcript: Fetch YouTube video transcripts/captions by URL."
    ),
    stateless_http=True,
    json_response=True,
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

converter = html2text.HTML2Text()
converter.ignore_links = False
converter.ignore_images = True
converter.body_width = 0  # no wrapping


def _html_to_markdown(html: str, max_chars: int = 80_000) -> str:
    """Convert raw HTML to readable Markdown, truncated to max_chars."""
    md = converter.handle(html)
    if len(md) > max_chars:
        md = md[:max_chars] + "\n\n[... truncated ...]"
    return md


def _build_response(page, css_selector: Optional[str], to_markdown: bool) -> str:
    """Build the text response from a Scrapling page object."""
    if css_selector:
        elements = page.css(css_selector)
        if not elements:
            return f"No elements matched selector: {css_selector}"
        parts = [el.text for el in elements if el.text]
        return "\n\n---\n\n".join(parts) if parts else "Elements found but no text content."

    html = page.html_content if hasattr(page, "html_content") else str(page.body)
    if to_markdown:
        return _html_to_markdown(html)
    return html[:80_000]


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #

@mcp.tool()
async def fetch_page(
    url: str,
    css_selector: str = "",
    to_markdown: bool = True,
) -> str:
    """
    Fetch a web page using a fast HTTP request with stealth headers.
    Good for static pages, GitHub raw content, docs sites, etc.

    Args:
        url: The full URL to fetch (must include https://).
        css_selector: Optional CSS selector to extract specific elements.
        to_markdown: Convert HTML to readable Markdown (default True).
    """
    def _sync_fetch(proxy=None):
        from scrapling.fetchers import Fetcher
        kwargs = dict(stealthy_headers=True, follow_redirects=True)
        if proxy:
            kwargs["proxy"] = proxy
        return Fetcher.get(url, **kwargs)

    logger.info(f"fetch_page: {url}")
    try:
        page = await asyncio.to_thread(_sync_fetch)
        if page.status != 200:
            raise Exception(f"HTTP {page.status}")
    except Exception as e:
        if PROXY_URL:
            logger.info(f"fetch_page: direct failed ({e}), retrying via proxy")
            try:
                page = await asyncio.to_thread(_sync_fetch, PROXY_URL)
            except Exception as e:
                return f"Fetch failed (via proxy): {e}"
            if page.status != 200:
                return f"HTTP {page.status} for {url} (via proxy)"
        else:
            return f"Fetch failed: {e}"

    return _build_response(page, css_selector or None, to_markdown)


@mcp.tool()
async def stealth_fetch_page(
    url: str,
    css_selector: str = "",
    to_markdown: bool = True,
    wait_seconds: float = 3.0,
) -> str:
    """
    Fetch a page using a real headless browser with anti-bot evasion.
    Bypasses Cloudflare Turnstile, bot detection, JS-rendered pages.
    Slower than fetch_page (~5-15s) but much more capable.

    Args:
        url: The full URL to fetch (must include https://).
        css_selector: Optional CSS selector to extract specific elements.
        to_markdown: Convert HTML to readable Markdown (default True).
        wait_seconds: Seconds to wait for JS to render (default 3).
    """
    def _sync_fetch():
        from scrapling.fetchers import StealthyFetcher
        return StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            wait_after_idle=wait_seconds,
        )

    logger.info(f"stealth_fetch_page: {url}")
    try:
        page = await asyncio.to_thread(_sync_fetch)
    except Exception as e:
        return f"Stealth fetch failed: {e}"

    if page.status != 200:
        return f"HTTP {page.status} for {url}"

    return _build_response(page, css_selector or None, to_markdown)


@mcp.tool()
async def extract_elements(
    url: str,
    selectors: dict[str, str],
    use_stealth: bool = False,
) -> str:
    """
    Fetch a page and extract multiple elements using CSS selectors.
    Returns structured JSON with the results.

    Args:
        url: The full URL to fetch.
        selectors: Dict mapping field names to CSS selectors, e.g. {"title": "h1", "price": ".product-price", "description": ".content p"}
        use_stealth: Use headless browser with anti-bot evasion (default False).
    """
    import orjson

    def _sync_fetch(proxy=None):
        if use_stealth:
            from scrapling.fetchers import StealthyFetcher
            return StealthyFetcher.fetch(url, headless=True, network_idle=True)
        else:
            from scrapling.fetchers import Fetcher
            kwargs = dict(stealthy_headers=True, follow_redirects=True)
            if proxy:
                kwargs["proxy"] = proxy
            return Fetcher.get(url, **kwargs)

    logger.info(f"extract_elements: {url} (stealth={use_stealth})")
    try:
        page = await asyncio.to_thread(_sync_fetch)
        if page.status != 200:
            raise Exception(f"HTTP {page.status}")
    except Exception as e:
        if PROXY_URL and not use_stealth:
            logger.info(f"extract_elements: direct failed ({e}), retrying via proxy")
            try:
                page = await asyncio.to_thread(_sync_fetch, PROXY_URL)
            except Exception as e:
                return f"Fetch failed (via proxy): {e}"
            if page.status != 200:
                return f"HTTP {page.status} for {url} (via proxy)"
        else:
            return f"Fetch failed: {e}"

    result = {}
    for name, selector in selectors.items():
        elements = page.css(selector)
        if not elements:
            result[name] = None
        elif len(elements) == 1:
            result[name] = elements[0].text or None
        else:
            result[name] = [el.text for el in elements if el.text]

    return orjson.dumps(result, option=orjson.OPT_INDENT_2).decode()


@mcp.tool()
async def get_youtube_transcript(url: str, lang: str = "en") -> str:
    """
    Fetch the transcript/captions for a YouTube video.

    Args:
        url: YouTube video URL (watch, youtu.be, or /shorts/ link).
        lang: Preferred language code (default "en").
    """
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

    pattern = r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})"
    match = re.search(pattern, url)
    if not match:
        return f"Failed to extract video ID from URL: {url}"

    video_id = match.group(1)

    def _sync_fetch(proxy=None):
        from youtube_transcript_api.proxies import GenericProxyConfig
        proxy_config = GenericProxyConfig(https_url=proxy) if proxy else None
        ytt = YouTubeTranscriptApi(proxy_config=proxy_config)
        try:
            transcript = ytt.fetch(video_id, languages=[lang])
        except NoTranscriptFound:
            transcript_list = ytt.list(video_id)
            transcript = transcript_list.find_transcript(
                list(transcript_list._manually_created_transcripts.keys())
                or list(transcript_list._generated_transcripts.keys())
            ).fetch()
        lines = [f"[{int(entry.start)}s] {entry.text}" for entry in transcript]
        return "\n".join(lines)

    logger.info(f"get_youtube_transcript: {video_id} (lang={lang})")
    try:
        result = await asyncio.to_thread(_sync_fetch)
    except TranscriptsDisabled:
        return f"Transcripts are disabled for video: {video_id}"
    except Exception as e:
        if PROXY_URL:
            logger.info(f"get_youtube_transcript: direct failed ({e}), retrying via proxy")
            try:
                result = await asyncio.to_thread(_sync_fetch, PROXY_URL)
            except TranscriptsDisabled:
                return f"Transcripts are disabled for video: {video_id}"
            except Exception as e2:
                return f"Failed to fetch transcript (via proxy): {e2}"
        else:
            return f"Failed to fetch transcript: {e}"

    if len(result) > 80_000:
        result = result[:80_000] + "\n\n[... truncated ...]"

    return f"Transcript for https://www.youtube.com/watch?v={video_id}:\n\n{result}"


# --------------------------------------------------------------------------- #
# Auth middleware (optional bearer token check)
# --------------------------------------------------------------------------- #

if API_KEY:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class BearerAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            # Skip auth for the MCP discovery endpoint
            if request.url.path == "/.well-known/oauth-authorization-server":
                return await call_next(request)
            auth = request.headers.get("authorization", "")
            if auth != f"Bearer {API_KEY}":
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

    # Access the underlying Starlette app and add middleware
    app = mcp.streamable_http_app()
    app.add_middleware(BearerAuthMiddleware)
else:
    app = mcp.streamable_http_app()


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    logger.info(f"Starting Shark-no-Kari v{__version__} on {host}:{port}")
    if PROXY_URL:
        logger.info("SOCKS5 proxy fallback is ENABLED")
    if API_KEY:
        logger.info("Bearer token auth is ENABLED")
    else:
        logger.warning("No MCP_API_KEY set - server is unauthenticated!")

    uvicorn.run(app, host=host, port=port)
