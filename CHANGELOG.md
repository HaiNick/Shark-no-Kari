# Changelog

All notable changes to Shark-no-Kari are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Changed
- Bumped Scrapling from >=0.3.2 to >=0.4.3 — includes proxy rotation, Cloudflare solver improvements, and MCP server enhancements

### Fixed
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
