"""Tests for Shark-no-Kari MCP server tools."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Force the youtube_transcript_api imports to be resolvable at module level in server
import youtube_transcript_api
from src.server import get_youtube_transcript, fetch_page, extract_elements


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _make_entry(start, text):
    """Create a fake transcript entry."""
    e = SimpleNamespace(start=start, text=text)
    return e


def _make_page(status, html="<h1>Hello</h1>", body=None):
    """Create a fake Scrapling page object."""
    page = MagicMock()
    page.status = status
    page.html_content = html
    page.body = body or html
    return page


# --------------------------------------------------------------------------- #
# get_youtube_transcript tests
# --------------------------------------------------------------------------- #

class TestGetYoutubeTranscript:

    async def test_transcript_success(self):
        entries = [_make_entry(0, "Hello"), _make_entry(5, "world"), _make_entry(10, "!")]
        with patch("youtube_transcript_api.YouTubeTranscriptApi") as MockApi:
            MockApi.return_value.fetch.return_value = entries
            result = await get_youtube_transcript("https://www.youtube.com/watch?v=abc12345678")
        assert "abc12345678" in result
        assert "[0s] Hello" in result
        assert "[5s] world" in result
        assert "[10s] !" in result

    async def test_transcript_short_url(self):
        entries = [_make_entry(0, "Hi")]
        with patch("youtube_transcript_api.YouTubeTranscriptApi") as MockApi:
            MockApi.return_value.fetch.return_value = entries
            result = await get_youtube_transcript("https://youtu.be/XyZ_1234567")
        assert "XyZ_1234567" in result

    async def test_transcript_shorts_url(self):
        entries = [_make_entry(0, "Short")]
        with patch("youtube_transcript_api.YouTubeTranscriptApi") as MockApi:
            MockApi.return_value.fetch.return_value = entries
            result = await get_youtube_transcript("https://www.youtube.com/shorts/SHORT123456")
        assert "SHORT123456" in result

    async def test_transcript_lang_fallback(self):
        from youtube_transcript_api._errors import NoTranscriptFound

        entries = [_make_entry(0, "Bonjour")]
        fake_transcript = MagicMock()
        fake_transcript.fetch.return_value = entries

        fake_list = MagicMock()
        fake_list._manually_created_transcripts = {"fr": True}
        fake_list._generated_transcripts = {}
        fake_list.find_transcript.return_value = fake_transcript

        with patch("youtube_transcript_api.YouTubeTranscriptApi") as MockApi:
            inst = MockApi.return_value
            inst.fetch.side_effect = NoTranscriptFound("abc12345678", ["en"], None)
            inst.list.return_value = fake_list
            result = await get_youtube_transcript("https://www.youtube.com/watch?v=abc12345678")

        assert "Bonjour" in result
        inst.list.assert_called_once_with("abc12345678")

    async def test_transcript_disabled(self):
        from youtube_transcript_api._errors import TranscriptsDisabled

        with patch("youtube_transcript_api.YouTubeTranscriptApi") as MockApi:
            MockApi.return_value.fetch.side_effect = TranscriptsDisabled("abc12345678")
            result = await get_youtube_transcript("https://www.youtube.com/watch?v=abc12345678")
        assert "disabled" in result.lower()

    async def test_transcript_invalid_url(self):
        result = await get_youtube_transcript("https://example.com/not-a-video")
        assert "Failed" in result

    async def test_transcript_truncation(self):
        entries = [_make_entry(i, "A" * 1000) for i in range(200)]
        with patch("youtube_transcript_api.YouTubeTranscriptApi") as MockApi:
            MockApi.return_value.fetch.return_value = entries
            result = await get_youtube_transcript("https://www.youtube.com/watch?v=abc12345678")
        assert result.endswith("[... truncated ...]")


# --------------------------------------------------------------------------- #
# fetch_page tests
# --------------------------------------------------------------------------- #

class TestFetchPage:

    async def test_fetch_page_success(self):
        page = _make_page(200, "<h1>Hello World</h1>")
        with patch("src.server.asyncio.to_thread", return_value=page):
            result = await fetch_page("https://example.com")
        assert "Hello World" in result

    async def test_fetch_page_http_error(self):
        page = _make_page(404)
        with patch("src.server.asyncio.to_thread", side_effect=Exception("HTTP 404")):
            result = await fetch_page("https://example.com/missing")
        assert "404" in result

    async def test_fetch_page_proxy_fallback(self):
        page_ok = _make_page(200, "<p>via proxy</p>")
        call_count = 0

        async def fake_to_thread(fn, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Connection refused")
            return page_ok

        with patch("src.server.asyncio.to_thread", side_effect=fake_to_thread), \
             patch("src.server.PROXY_URL", "socks5://proxy:1080"):
            result = await fetch_page("https://example.com")
        assert "via proxy" in result
        assert call_count == 2


# --------------------------------------------------------------------------- #
# extract_elements tests
# --------------------------------------------------------------------------- #

class TestExtractElements:

    async def test_extract_elements_single(self):
        page = _make_page(200)
        mock_el = MagicMock()
        mock_el.text = "Test Title"
        page.css.return_value = [mock_el]

        with patch("src.server.asyncio.to_thread", return_value=page):
            result = await extract_elements("https://example.com", {"title": "h1"})
        parsed = json.loads(result)
        assert parsed["title"] == "Test Title"

    async def test_extract_elements_missing(self):
        page = _make_page(200)
        page.css.return_value = []

        with patch("src.server.asyncio.to_thread", return_value=page):
            result = await extract_elements("https://example.com", {"title": "h1.missing"})
        parsed = json.loads(result)
        assert parsed["title"] is None
