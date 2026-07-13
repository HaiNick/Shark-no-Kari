# Changelog

All notable changes to Shark-no-Kari are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Versioning follows [Semantic Versioning](https://semver.org/).

---

## [2.1.10] - 2026-07-13

### Fixed
- Require fastmcp >= 3.4.4; fixes consent 403 (Forbidden Origin) behind reverse
  proxy for CIMD clients (fastmcp 3.4.3 reconstructed the origin from the
  proxy-rewritten Host header instead of the browser's Origin header).

---

## [2.1.9] - 2026-07-13

### Changed
- Replace persistent OAuth client storage (FileTreeStore + Fernet) with FastMCP's
  default in-memory storage (fleet-standard pattern). Fixes consent 403 that appeared
  alongside the v2.1.8 storage key fix; supersedes it. Trade-off: clients must
  re-authenticate after a container restart (no user data is stored there anyway).
- `STORAGE_ENCRYPTION_KEY` is no longer required and has been removed from config
  validation and `.env.example`.

---

## [2.1.8] - 2026-07-13

### Fixed
- 500 on `GET /authorize` when Claude.ai registers via CIMD: the client_id is
  the metadata document URL (`https://claude.ai/oauth/mcp-oauth-client-metadata`),
  and `FileTreeStore` was mapping `/` and `:` directly to filesystem path
  separators, causing `FileNotFoundError`.  Fixed by passing
  `FileTreeV1KeySanitizationStrategy` and `FileTreeV1CollectionSanitizationStrategy`
  to `FileTreeStore` so keys are encoded to safe filenames before any I/O.
- Carried over from v2.1.7: `forward_resource=False` on `OIDCProxy` to suppress
  the RFC 8707 `resource` parameter that Pocket ID ≥ 2.10 (fosite) rejects.

### Notes
- The `/app/oauth_state` volume is ephemeral OAuth proxy state; clearing it
  only forces clients to re-authenticate (no user data is stored there).

---

## [2.1.7] - 2026-07-13

### Fixed
- `OIDCProxy`: set `forward_resource=False` to suppress the RFC 8707 `resource` parameter
  that Pocket ID >= 2.10 (fosite) rejects during the token exchange.

---

## [2.1.6] - 2026-07-06

### Fixed
- `get_youtube_transcript`: the `kari-bgutil-pot` PO token provider added in 2.1.5 was
  never actually being invoked. `yt-dlp` was falling back to the `android_vr` player
  client (no JS runtime available in the container), and only the `web` client uses PO
  tokens — `android_vr` doesn't request one, and is increasingly hitting its own
  `LOGIN_REQUIRED` wall independently.
- Installed `deno` in the Docker image so `yt-dlp` can solve YouTube's signature/cipher
  challenge for the `web` client.
- Forced `player_client: ["web"]` via `extractor_args` so `yt-dlp` actually requests the
  `web` client (and therefore a PO token from `kari-bgutil-pot`) instead of silently
  falling back to a non-JS client.

---

## [2.1.5] - 2026-07-06

### Added
- `kari-bgutil-pot` Docker Compose sidecar (`brainicism/bgutil-ytdlp-pot-provider`) —
  generates PO tokens over HTTP so `yt-dlp` passes YouTube's bot check for
  `get_youtube_transcript`. Wired in via `extractor_args` on the `youtubepot-bgutilhttp`
  extractor, base URL configurable via `BGUTIL_POT_URL`.
- `bgutil-ytdlp-pot-provider` Python plugin dependency (talks to the sidecar container).

---

## [2.1.0] - 2026-07-06

### Changed
- `get_youtube_transcript` now uses `yt-dlp` instead of `youtube_transcript_api` for
  fetching captions. `youtube_transcript_api` was getting blocked by YouTube even through
  the NordLynx proxy fallback (commercial VPN IP ranges are commonly blocklisted at the
  application layer); `yt-dlp` is more actively maintained against YouTube's anti-bot
  measures and handles this more robustly.
- Transcript output no longer includes per-line [Ns] timestamps — now returns continuous
  transcript text parsed from the VTT subtitle track.

### Removed
- `youtube-transcript-api` dependency

---

## [2.0.0] - 2026-06-29

### Added
- **CloakBrowser stealth engine** — optional Chromium CDP backend for `stealth_fetch_page`.
  Enable by setting `COMPOSE_PROFILES=cloakbrowser`; the `kari-cloakbrowser` sidecar starts
  automatically and `stealth_fetch_page` routes through it via Chrome DevTools Protocol.
  When the profile is unset the existing Camoufox/`StealthyFetcher` path is used unchanged.
- `kari-cloakbrowser` Docker Compose service (`cloakhq/cloakbrowser` image, profile-gated).
  Isolated on a dedicated `kari-internal` bridge network; NordLynx proxy wired in via
  `cloakserve --proxy-server=socks5h://kari-nordlynx:1080`.
- `COMPOSE_PROFILES` and `CLOAKBROWSER_CDP_URL` environment variables.
- `cloakbrowser` Python package to `requirements.txt`.
- Four Unicode/CJK font packages to Dockerfile apt layer
  (`fonts-freefont-ttf`, `fonts-unifont`, `fonts-ipafont-gothic`, `fonts-wqy-zenhei`).

### Changed
- `stealth_fetch_page` CloakBrowser path: fetches WebSocket URL from `/json/version`
  (5 s timeout) and calls `StealthyFetcher.async_fetch(cdp_url=ws_url, block_ads=True, network_idle=True)`.
- `stealth_fetch_page` Camoufox fallback path: `block_ads=True` added.
- `fetch_page` and `extract_elements`: `follow_redirects=True` → `follow_redirects="safe"`.
- Dockerfile browser install: `scrapling install` → `scrapling install --force`;
  added `python -m cloakbrowser install` build step.
- Bumped `scrapling[fetchers]` from `>=0.4.7` to `>=0.4.9`.
- Version bumped to `2.0.0`.

---

## [1.5.0] - 2026-05-27

### Added
- `fetch_feed` tool — fetch RSS/Atom feeds and return only items published after a cutoff datetime.
  Strips HTML from summaries, filters by optional `skip_terms`, returns compact JSON sorted newest-first.
  Use this instead of `fetch_page` for all RSS/Atom feed URLs.
- `feedparser` and `python-dateutil` dependencies.

---

## [1.4.0] - 2026-05-01

### Added
- Optional OAuth 2.1 authentication via OIDC, federated to a self-hosted Pocket ID instance.
  Activated by setting `OIDC_ENABLED=true` in `.env`. Default is disabled; existing IP-allowlist
  and bearer token modes are unchanged.
- `OIDC_CONFIG_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_BASE_URL`, `JWT_SIGNING_KEY`,
  and `STORAGE_ENCRYPTION_KEY` environment variables (all required when `OIDC_ENABLED=true`).
- Encrypted on-disk OAuth client registration store: `py-key-value-aio` FileTreeStore wrapped
  with Fernet encryption, mounted at `/app/oauth_state` via a named Docker volume. Survives
  container restarts so Claude does not re-register on every deploy.
- `scripts/verify-oidc.sh`: smoke-test script that checks the three OIDC metadata endpoints
  and verifies that unauthenticated `/mcp` requests receive a `WWW-Authenticate` header.
- README section "OAuth (OIDC) Authentication" documenting all three auth modes, Pocket ID
  client setup, key generation commands, and verification steps.

### Changed
- Migrated from `mcp[cli]` (official Anthropic MCP SDK) to `fastmcp>=2.0` (PrefectHQ).
  `fastmcp` is API-compatible for tools and HTTP transport, and adds built-in OIDCProxy support.
  Key API changes: `streamable_http_app()` replaced by `http_app(stateless_http=True)`;
  `stateless_http` and `json_response` are now kwargs on `http_app()`, not on the constructor.
- Caddyfile updated: `/authorize*`, `/auth/callback`, `/consent*`, and `/.well-known/*` paths
  are now reachable from outside the Anthropic IP range to support the browser-based OAuth flow.


## [1.3.0] - 2026-04-04

### Added
- Bundled `nordlynx-proxy` sidecar container for reliable SOCKS5 proxy fallback via NordVPN WireGuard tunnel — runs the NordVPN Linux client internally and exposes a local SOCKS5 proxy on the Docker network
- `NORDVPN_TOKEN` and `NORDVPN_COUNTRY` environment variables

### Changed
- `PROXY_URL` now defaults to local `socks5h://kari-nordlynx:1080` instead of remote NordVPN SOCKS5 endpoints
- Bumped Scrapling from >=0.3.2 to >=0.4.3 — includes proxy rotation, Cloudflare solver improvements, and MCP server enhancements

### Fixed
- Proxy fallback failing due to NordVPN blocking SOCKS5 connections from datacenter IPs
- SOCKS5 proxy fallback broken — `socks5://` resolves DNS locally which can fail in containers. Server now auto-normalizes `socks5://` to `socks5h://` at startup (delegates DNS to proxy) and logs a warning.

## [1.2.0] - 2026-03-29

### Added
- SOCKS5 proxy fallback for `get_youtube_transcript` — YouTube blocks datacenter IPs, now retries via `PROXY_URL` automatically
- Dependabot for pip, Docker, and GitHub Actions dependency updates
- GitHub Release workflow — creates releases from changelog on version tags
- Issue templates (bug report, feature request) and PR template
- Branch protection on `main` — requires PR review and passing CI

### Changed
- Dockerfile base image bumped from Python 3.12 to 3.14
- GitHub Actions bumped: checkout v6, buildx v4, login v4, metadata v6, build-push v7

### Fixed
- Docker healthcheck now uses MCP POST ping instead of GET (was always showing unhealthy)
- Dockerfile now copies `pyproject.toml` for version reading

## [1.1.0] - 2026-03-29

### Added
- `get_youtube_transcript` tool — fetch YouTube video transcripts/captions with language fallback
  - Supports watch URLs, `youtu.be` short links, and `/shorts/` URLs
  - Automatic fallback to first available language when preferred language is unavailable
  - Truncation at 80,000 characters
- GitHub Actions CI workflow — auto-builds and pushes Docker images to `ghcr.io` on push to `main` or version tags
- Docker image layer caching via GitHub Actions cache
- Test suite with 13 tests covering all tools (`pytest` + `pytest-asyncio`)
- Version tracking via `pyproject.toml` and semver git tags
- CHANGELOG

### Changed
- `docker-compose.yml` now uses pre-built image from `ghcr.io/hainick/shark-no-kari` instead of local build
- Environment config switched from inline `environment:` block to `env_file: .env`
- Quick Start and Deployment guides updated — no longer require cloning the full repo

## [1.0.0] - 2026-03-28

### Added
- `fetch_page` tool — fast HTTP fetcher with stealth headers and SOCKS5 proxy fallback
- `stealth_fetch_page` tool — headless browser fetcher with anti-bot evasion (Camoufox/Playwright)
- `extract_elements` tool — structured multi-selector CSS extraction returning JSON
- HTML-to-Markdown conversion via `html2text` with 80,000 char truncation
- Optional bearer token authentication via `MCP_API_KEY`
- Caddy reverse proxy with auto HTTPS and IP allowlisting
- Docker Compose setup with shared memory for headless browsers
- VPS bootstrap script
