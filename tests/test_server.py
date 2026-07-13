"""Tests for Shark-no-Kari MCP server tools."""

import json
import os
import sys
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.server import get_youtube_transcript, fetch_page, extract_elements


# --------------------------------------------------------------------------- #
# OAuth client storage tests
# --------------------------------------------------------------------------- #

class TestOAuthClientStorage:
    """Verify that URL-shaped CIMD client_ids survive the storage round-trip.

    Claude.ai registers via CIMD and sends its metadata document URL as the
    client_id (e.g. "https://claude.ai/oauth/mcp-oauth-client-metadata").
    Without FileTreeV1KeySanitizationStrategy the raw "/" and ":" in that URL
    become filesystem path separators and FileTreeStore dies with
    FileNotFoundError.  These tests confirm the fix holds.
    """

    CIMD_CLIENT_ID = "https://claude.ai/oauth/mcp-oauth-client-metadata"

    async def test_url_key_put_fails_without_sanitization(self, tmp_path):
        """FileTreeStore without sanitization raises on a URL-shaped key."""
        from key_value.aio.stores.filetree import FileTreeStore

        store = FileTreeStore(data_directory=tmp_path)
        with pytest.raises((FileNotFoundError, OSError)):
            await store.put(
                key=self.CIMD_CLIENT_ID,
                value={"client_id": self.CIMD_CLIENT_ID},
                collection="mcp-oauth-proxy-clients",
            )

    async def test_url_key_round_trips_with_sanitization(self, tmp_path):
        """FileTreeStore + sanitization strategies allow URL-shaped keys."""
        from cryptography.fernet import Fernet
        from key_value.aio.stores.filetree import (
            FileTreeStore,
            FileTreeV1CollectionSanitizationStrategy,
            FileTreeV1KeySanitizationStrategy,
        )
        from key_value.aio.wrappers.encryption.fernet import FernetEncryptionWrapper

        store = FernetEncryptionWrapper(
            key_value=FileTreeStore(
                data_directory=tmp_path,
                key_sanitization_strategy=FileTreeV1KeySanitizationStrategy(tmp_path),
                collection_sanitization_strategy=FileTreeV1CollectionSanitizationStrategy(tmp_path),
            ),
            fernet=Fernet(Fernet.generate_key()),
        )

        payload = {"client_id": self.CIMD_CLIENT_ID, "scope": "openid"}
        await store.put(key=self.CIMD_CLIENT_ID, value=payload, collection="mcp-oauth-proxy-clients")
        result = await store.get(key=self.CIMD_CLIENT_ID, collection="mcp-oauth-proxy-clients")

        assert result is not None
        assert result["client_id"] == self.CIMD_CLIENT_ID
        assert result["scope"] == "openid"

    async def test_distinct_url_keys_do_not_collide(self, tmp_path):
        """Two different URL keys sanitize to distinct file names."""
        from key_value.aio.stores.filetree import (
            FileTreeStore,
            FileTreeV1CollectionSanitizationStrategy,
            FileTreeV1KeySanitizationStrategy,
        )

        store = FileTreeStore(
            data_directory=tmp_path,
            key_sanitization_strategy=FileTreeV1KeySanitizationStrategy(tmp_path),
            collection_sanitization_strategy=FileTreeV1CollectionSanitizationStrategy(tmp_path),
        )

        key_a = "https://claude.ai/oauth/mcp-oauth-client-metadata"
        key_b = "https://other.example.com/oauth/mcp-oauth-client-metadata"
        await store.put(key=key_a, value={"id": "a"}, collection="clients")
        await store.put(key=key_b, value={"id": "b"}, collection="clients")

        result_a = await store.get(key=key_a, collection="clients")
        result_b = await store.get(key=key_b, collection="clients")

        assert result_a is not None and result_a["id"] == "a"
        assert result_b is not None and result_b["id"] == "b"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _make_vtt(*lines):
    """Build a minimal WEBVTT payload from a list of caption lines."""
    body = "WEBVTT\n\n"
    for i, line in enumerate(lines):
        start = f"00:00:{i:02d}.000"
        end = f"00:00:{i + 1:02d}.000"
        body += f"{i + 1}\n{start} --> {end}\n{line}\n\n"
    return body


def _make_ydl(subtitles=None, automatic_captions=None):
    """Create a fake yt_dlp.YoutubeDL context manager returning the given info dict."""
    info = {
        "subtitles": subtitles or {},
        "automatic_captions": automatic_captions or {},
    }
    instance = MagicMock()
    instance.extract_info.return_value = info
    instance.__enter__.return_value = instance
    instance.__exit__.return_value = False
    return instance


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
        vtt = _make_vtt("Hello", "world", "!")
        ydl = _make_ydl(subtitles={"en": [{"ext": "vtt", "url": "https://example.com/en.vtt"}]})
        resp = MagicMock(text=vtt)
        resp.raise_for_status.return_value = None

        with patch("yt_dlp.YoutubeDL", return_value=ydl), \
             patch("requests.get", return_value=resp):
            result = await get_youtube_transcript("https://www.youtube.com/watch?v=abc12345678")
        assert "abc12345678" in result
        assert "Hello" in result
        assert "world" in result
        assert "!" in result

    async def test_transcript_short_url(self):
        vtt = _make_vtt("Hi")
        ydl = _make_ydl(subtitles={"en": [{"ext": "vtt", "url": "https://example.com/en.vtt"}]})
        resp = MagicMock(text=vtt)
        resp.raise_for_status.return_value = None

        with patch("yt_dlp.YoutubeDL", return_value=ydl), \
             patch("requests.get", return_value=resp):
            result = await get_youtube_transcript("https://youtu.be/XyZ_1234567")
        assert "XyZ_1234567" in result

    async def test_transcript_shorts_url(self):
        vtt = _make_vtt("Short")
        ydl = _make_ydl(subtitles={"en": [{"ext": "vtt", "url": "https://example.com/en.vtt"}]})
        resp = MagicMock(text=vtt)
        resp.raise_for_status.return_value = None

        with patch("yt_dlp.YoutubeDL", return_value=ydl), \
             patch("requests.get", return_value=resp):
            result = await get_youtube_transcript("https://www.youtube.com/shorts/SHORT123456")
        assert "SHORT123456" in result

    async def test_transcript_lang_fallback(self):
        vtt = _make_vtt("Bonjour")
        ydl = _make_ydl(subtitles={"fr": [{"ext": "vtt", "url": "https://example.com/fr.vtt"}]})
        resp = MagicMock(text=vtt)
        resp.raise_for_status.return_value = None

        with patch("yt_dlp.YoutubeDL", return_value=ydl), \
             patch("requests.get", return_value=resp):
            result = await get_youtube_transcript("https://www.youtube.com/watch?v=abc12345678")

        assert "Bonjour" in result

    async def test_transcript_auto_caption_fallback(self):
        vtt = _make_vtt("Auto generated")
        ydl = _make_ydl(automatic_captions={"en": [{"ext": "vtt", "url": "https://example.com/en-auto.vtt"}]})
        resp = MagicMock(text=vtt)
        resp.raise_for_status.return_value = None

        with patch("yt_dlp.YoutubeDL", return_value=ydl), \
             patch("requests.get", return_value=resp):
            result = await get_youtube_transcript("https://www.youtube.com/watch?v=abc12345678")

        assert "Auto generated" in result

    async def test_transcript_no_captions(self):
        ydl = _make_ydl()

        with patch("yt_dlp.YoutubeDL", return_value=ydl):
            result = await get_youtube_transcript("https://www.youtube.com/watch?v=abc12345678")
        assert "Failed to fetch transcript" in result

    async def test_transcript_invalid_url(self):
        result = await get_youtube_transcript("https://example.com/not-a-video")
        assert "Failed" in result

    async def test_transcript_truncation(self):
        vtt = _make_vtt(*[f"line{i} " + "A" * 1000 for i in range(200)])
        ydl = _make_ydl(subtitles={"en": [{"ext": "vtt", "url": "https://example.com/en.vtt"}]})
        resp = MagicMock(text=vtt)
        resp.raise_for_status.return_value = None

        with patch("yt_dlp.YoutubeDL", return_value=ydl), \
             patch("requests.get", return_value=resp):
            result = await get_youtube_transcript("https://www.youtube.com/watch?v=abc12345678")
        assert result.endswith("[... truncated ...]")

    async def test_transcript_proxy_fallback(self):
        vtt = _make_vtt("via proxy")
        ydl = _make_ydl(subtitles={"en": [{"ext": "vtt", "url": "https://example.com/en.vtt"}]})
        resp = MagicMock(text=vtt)
        resp.raise_for_status.return_value = None
        call_count = 0

        def make_ydl(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("IP blocked by YouTube")
            return ydl

        with patch("yt_dlp.YoutubeDL", side_effect=make_ydl), \
             patch("requests.get", return_value=resp), \
             patch("src.server.PROXY_URL", "socks5://proxy:1080"):
            result = await get_youtube_transcript("https://www.youtube.com/watch?v=abc12345678")
        assert "via proxy" in result
        assert call_count == 2


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


# --------------------------------------------------------------------------- #
# OIDC startup tests
# --------------------------------------------------------------------------- #

def _purge_server_module():
    """Remove src.server from sys.modules so it can be freshly re-imported."""
    for key in list(sys.modules.keys()):
        if key == "src.server":
            del sys.modules[key]


class TestOIDCStartup:
    """Tests for module-level OIDC validation that runs at import time."""

    @pytest.fixture(autouse=True)
    def restore_module(self):
        """Re-import the real server module after each test in this class."""
        original = sys.modules.get("src.server")
        yield
        _purge_server_module()
        if original is not None:
            sys.modules["src.server"] = original

    def test_oidc_missing_vars_raises(self):
        """RuntimeError at startup when OIDC_ENABLED=true but required vars absent."""
        env = {
            "OIDC_ENABLED": "true",
            "MCP_API_KEY": "",
            "OIDC_CONFIG_URL": "",
            "OIDC_CLIENT_ID": "",
            "OIDC_BASE_URL": "",
            "JWT_SIGNING_KEY": "",
            "STORAGE_ENCRYPTION_KEY": "",
        }
        _purge_server_module()
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(RuntimeError, match="missing required vars"):
                import src.server

    def test_oidc_and_api_key_raises(self):
        """RuntimeError at startup when both OIDC_ENABLED and MCP_API_KEY are set."""
        env = {
            "OIDC_ENABLED": "true",
            "MCP_API_KEY": "some-key",
        }
        _purge_server_module()
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(RuntimeError, match="cannot both be set"):
                import src.server

    def test_oidc_startup_succeeds_with_mocked_deps(self):
        """Server module loads cleanly with OIDC_ENABLED=true when deps are mocked."""
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()

        env = {
            "OIDC_ENABLED": "true",
            "MCP_API_KEY": "",
            "OIDC_CONFIG_URL": "https://id.example.com/.well-known/openid-configuration",
            "OIDC_CLIENT_ID": "test-client",
            "OIDC_CLIENT_SECRET": "test-secret",
            "OIDC_BASE_URL": "https://kari.example.com",
            "JWT_SIGNING_KEY": "A" * 32,
            "STORAGE_ENCRYPTION_KEY": key,
        }

        # fastmcp calls auth._get_resource_url() when building the HTTP app.
        # Returning None tells it to skip resource-metadata URL construction.
        mock_auth_instance = MagicMock()
        mock_auth_instance._get_resource_url.return_value = None
        mock_oidc_cls = MagicMock(return_value=mock_auth_instance)
        mock_file_tree_cls = MagicMock(return_value=MagicMock())
        mock_fernet_wrapper_cls = MagicMock(return_value=MagicMock())

        mock_filetree_pkg = MagicMock(
            FileTreeStore=mock_file_tree_cls,
            FileTreeV1KeySanitizationStrategy=MagicMock(return_value=MagicMock()),
            FileTreeV1CollectionSanitizationStrategy=MagicMock(return_value=MagicMock()),
        )
        injected_modules = {
            "fastmcp.server.auth.oidc_proxy": MagicMock(OIDCProxy=mock_oidc_cls),
            "key_value.aio.stores.filetree": mock_filetree_pkg,
            "key_value.aio.stores.filetree.store": MagicMock(FileTreeStore=mock_file_tree_cls),
            "key_value.aio.wrappers.encryption.fernet": MagicMock(
                FernetEncryptionWrapper=mock_fernet_wrapper_cls
            ),
        }

        # Remove any cached real versions of these modules so our mocks take effect.
        for mod in injected_modules:
            sys.modules.pop(mod, None)

        _purge_server_module()
        with patch.dict(os.environ, env, clear=False), \
             patch.dict(sys.modules, injected_modules):
            import src.server
            assert src.server.OIDC_ENABLED is True
            mock_oidc_cls.assert_called_once()
            call_kwargs = mock_oidc_cls.call_args.kwargs
            assert call_kwargs["client_id"] == "test-client"
            assert call_kwargs["base_url"] == "https://kari.example.com"
            assert "openid" in call_kwargs["required_scopes"]
