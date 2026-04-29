# Changelog

All notable changes to Shark-no-Kari are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

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
