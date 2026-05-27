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
from fastmcp import FastMCP

with open(Path(__file__).resolve().parent.parent / "pyproject.toml", "rb") as f:
    __version__ = tomllib.load(f)["project"]["version"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shark-no-kari")

# --------------------------------------------------------------------------- #
# Server setup
# --------------------------------------------------------------------------- #

API_KEY = os.getenv("MCP_API_KEY", "")
PROXY_URL = os.getenv("PROXY_URL", "")
OIDC_ENABLED = os.getenv("OIDC_ENABLED", "").lower() in {"1", "true", "yes"}

# socks5:// resolves DNS locally; socks5h:// delegates DNS to the proxy.
# VPN proxies (NordVPN, etc.) expect proxy-side resolution, so normalize.
if PROXY_URL.startswith("socks5://"):
    PROXY_URL = "socks5h://" + PROXY_URL[len("socks5://"):]
    logger.warning(
        "PROXY_URL had socks5:// scheme - rewritten to socks5h:// "
        "(delegates DNS to the proxy). Update your .env to silence this warning."
    )

if OIDC_ENABLED and API_KEY:
    raise RuntimeError(
        "OIDC_ENABLED and MCP_API_KEY cannot both be set. Choose one auth mode."
    )

_OIDC_CONFIG_URL = os.getenv("OIDC_CONFIG_URL", "")
_OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "")
_OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")
_OIDC_BASE_URL = os.getenv("OIDC_BASE_URL", "")
_JWT_SIGNING_KEY = os.getenv("JWT_SIGNING_KEY", "")
_STORAGE_ENCRYPTION_KEY = os.getenv("STORAGE_ENCRYPTION_KEY", "")

if OIDC_ENABLED:
    _missing = [
        name
        for name, val in [
            ("OIDC_CONFIG_URL", _OIDC_CONFIG_URL),
            ("OIDC_CLIENT_ID", _OIDC_CLIENT_ID),
            ("OIDC_BASE_URL", _OIDC_BASE_URL),
            ("JWT_SIGNING_KEY", _JWT_SIGNING_KEY),
            ("STORAGE_ENCRYPTION_KEY", _STORAGE_ENCRYPTION_KEY),
        ]
        if not val
    ]
    if _missing:
        raise RuntimeError(
            f"OIDC_ENABLED=true but missing required vars: {', '.join(_missing)}"
        )

_INSTRUCTIONS = (
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
    "Set use_stealth=True for bot-protected sites.\n"
    "- fetch_feed: Use this for ALL RSS/Atom feed URLs instead of fetch_page. "
    "Parses feed entries, filters by cutoff datetime and optional skip_terms, "
    "strips HTML from summaries, returns compact JSON.\n"
    "- get_youtube_transcript: Fetch YouTube video transcripts/captions by URL.\n\n"
    "Tips:\n"
    "- Use css_selector on fetch_page/stealth_fetch_page for simple single-selector extraction\n"
    "- Use extract_elements when you need multiple different pieces of data from one page\n"
    "- to_markdown=True (default) converts HTML to readable text\n"
    "- Always try fetch_page before stealth_fetch_page\n"
    "- Always use fetch_feed (not fetch_page) for RSS/Atom feed URLs"
)

if OIDC_ENABLED:
    from fastmcp.server.auth.oidc_proxy import OIDCProxy
    from key_value.aio.stores.filetree.store import FileTreeStore
    from key_value.aio.wrappers.encryption.fernet import FernetEncryptionWrapper
    from cryptography.fernet import Fernet

    _client_storage = FernetEncryptionWrapper(
        key_value=FileTreeStore(data_directory="/app/oauth_state"),
        fernet=Fernet(_STORAGE_ENCRYPTION_KEY),
    )
    _auth = OIDCProxy(
        config_url=_OIDC_CONFIG_URL,
        client_id=_OIDC_CLIENT_ID,
        client_secret=_OIDC_CLIENT_SECRET or None,
        base_url=_OIDC_BASE_URL,
        jwt_signing_key=_JWT_SIGNING_KEY,
        required_scopes=["openid"],
        verify_id_token=True,
        client_storage=_client_storage,
    )
    mcp = FastMCP(name="Shark-no-Kari", instructions=_INSTRUCTIONS, auth=_auth)
else:
    mcp = FastMCP(name="Shark-no-Kari", instructions=_INSTRUCTIONS)


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


@mcp.tool()
async def fetch_feed(
    url: str,
    cutoff: str,
    skip_terms: list[str] = [],
) -> str:
    """
    Fetch an RSS or Atom feed and return only items published after the cutoff.
    Strips HTML from summaries, filters by skip_terms, returns compact JSON.
    Use this instead of fetch_page for all RSS/Atom sources.

    Args:
        url: The RSS or Atom feed URL.
        cutoff: ISO 8601 cutoff datetime. Items at or before this are excluded.
                Example: "2026-05-18T11:05:59+02:00"
        skip_terms: Items whose title or author contains any of these strings
                    (case-insensitive) are skipped.
                    Example: ["Sponsored", "Anzeige:", "Deals"]
    """
    import feedparser
    import orjson
    from datetime import datetime, timezone
    from dateutil import parser as dtparser
    from html.parser import HTMLParser
    import re as _re

    class _Stripper(HTMLParser):
        def __init__(self):
            super().__init__()
            self._parts: list[str] = []
        def handle_data(self, d: str) -> None:
            self._parts.append(d)
        def text(self) -> str:
            return _re.sub(r"\s+", " ", " ".join(self._parts)).strip()

    def _strip_html(raw: str) -> str:
        s = _Stripper()
        try:
            s.feed(raw or "")
        except Exception:
            pass
        return s.text()

    def _entry_dt(entry) -> datetime | None:
        for attr in ("published_parsed", "updated_parsed"):
            t = getattr(entry, attr, None)
            if t:
                return datetime(*t[:6], tzinfo=timezone.utc)
        for attr in ("published", "updated"):
            raw = getattr(entry, attr, None)
            if raw:
                try:
                    return dtparser.parse(raw).astimezone(timezone.utc)
                except Exception:
                    pass
        return None

    try:
        cutoff_dt = dtparser.parse(cutoff).astimezone(timezone.utc)
    except Exception as e:
        return f"Invalid cutoff: {e}"

    def _sync_fetch(proxy=None):
        from scrapling.fetchers import Fetcher
        kwargs = dict(stealthy_headers=True, follow_redirects=True)
        if proxy:
            kwargs["proxy"] = proxy
        return Fetcher.get(url, **kwargs)

    logger.info(f"fetch_feed: {url} (cutoff={cutoff})")
    try:
        page = await asyncio.to_thread(_sync_fetch)
        if page.status != 200:
            raise Exception(f"HTTP {page.status}")
        if hasattr(page, "body") and page.body:
            raw = page.body if isinstance(page.body, str) else page.body.decode("utf-8", errors="replace")
        elif hasattr(page, "html_content"):
            raw = page.html_content
        else:
            raw = str(page)
    except Exception as e:
        if PROXY_URL:
            logger.info(f"fetch_feed: direct failed ({e}), retrying via proxy")
            try:
                page = await asyncio.to_thread(_sync_fetch, PROXY_URL)
                if hasattr(page, "body") and page.body:
                    raw = page.body if isinstance(page.body, str) else page.body.decode("utf-8", errors="replace")
                elif hasattr(page, "html_content"):
                    raw = page.html_content
                else:
                    raw = str(page)
            except Exception as e2:
                return f"Feed fetch failed (via proxy): {e2}"
        else:
            return f"Feed fetch failed: {e}"

    feed = await asyncio.to_thread(feedparser.parse, raw)

    skip_lower = [t.lower() for t in skip_terms]
    items = []

    for entry in feed.entries:
        entry_dt = _entry_dt(entry)
        if entry_dt is None or entry_dt <= cutoff_dt:
            continue

        title = entry.get("title", "")
        author = (
            entry.get("author")
            or entry.get("dc_creator")
            or ""
        )
        if any(term in (title + " " + author).lower() for term in skip_lower):
            continue

        raw_summary = (
            entry.get("summary", "")
            or (entry.get("content", [{}])[0].get("value", "") if entry.get("content") else "")
        )
        summary = _strip_html(raw_summary)
        if len(summary) > 400:
            summary = summary[:397] + "..."

        items.append({
            "title": title,
            "link": entry.get("link", ""),
            "date": entry_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "author": author,
            "summary": summary,
        })

    items.sort(key=lambda x: x["date"], reverse=True)

    return orjson.dumps(
        {"feed": feed.feed.get("title", ""), "count": len(items), "items": items},
        option=orjson.OPT_INDENT_2,
    ).decode()


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

app = mcp.http_app(stateless_http=True, json_response=True)
if API_KEY:
    app.add_middleware(BearerAuthMiddleware)


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
    if OIDC_ENABLED:
        logger.info("OIDC authentication is ENABLED (Pocket ID)")
    elif API_KEY:
        logger.info("Bearer token auth is ENABLED")
    else:
        logger.warning("No MCP_API_KEY set - server is unauthenticated!")

    uvicorn.run(app, host=host, port=port)
