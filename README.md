<div align="center">

# Shark-no-Kari (狩り - the hunt)

**Remote MCP server for web scraping with anti-bot evasion**

Stealth HTTP fetching · Headless browser · Cloudflare bypass · CSS selectors · YouTube transcripts · Markdown conversion

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-Streamable_HTTP-8A2BE2)](https://modelcontextprotocol.io)
[![Scrapling](https://img.shields.io/pypi/v/scrapling?label=Scrapling&color=green)](https://github.com/D4Vinci/Scrapling)

_Claude's built-in `web_fetch` fails on GitHub blob URLs, Cloudflare-protected sites, and JS-rendered pages._
**Shark-no-Kari** is a remote MCP server that gives Claude powerful web tools powered by [Scrapling](https://github.com/D4Vinci/Scrapling) — a fast HTTP fetcher with stealth headers, a real headless browser with anti-bot evasion, structured element extraction, and YouTube transcript fetching. Deploy it on any VPS with Docker, add the URL as a custom connector in claude.ai, and Claude can fetch pages that were previously unreachable.

</div>

---

## Table of Contents

- [Tools](#tools)
- [Quick Start](#quick-start)
- [Deployment](#deployment)
  - [Prerequisites](#prerequisites)
  - [1. Provision a VPS](#1-provision-a-vps)
  - [2. Point Your Domain](#2-point-your-domain)
  - [3. Bootstrap the VPS](#3-bootstrap-the-vps)
  - [4. Deploy](#4-deploy)
  - [5. Connect to Claude](#5-connect-to-claude)
- [Usage in Claude](#usage-in-claude)
- [Security](#security)
  - [IP Allowlisting](#ip-allowlisting)
  - [DNS Rebinding Protection Workaround](#dns-rebinding-protection-workaround)
  - [Optional Bearer Token Auth](#optional-bearer-token-auth)
- [OAuth (OIDC) Authentication](#oauth-oidc-authentication)
  - [Auth Mode Comparison](#auth-mode-comparison)
  - [Pocket ID Client Setup](#pocket-id-client-setup)
  - [Enable OIDC in .env](#enable-oidc-in-env)
  - [Verification](#verification)
- [Architecture](#architecture)
  - [Tech Stack](#tech-stack)
  - [Project Structure](#project-structure)
  - [How It Works](#how-it-works)
- [Configuration](#configuration)
- [Local Development](#local-development)
- [Docker](#docker)
- [Resource Usage](#resource-usage)
- [Troubleshooting](#troubleshooting)
- [Acknowledgements](#acknowledgements)
- [License](#license)

---

## Tools

| Tool                  | Description                                                                  | Speed    |
| --------------------- | ---------------------------------------------------------------------------- | -------- |
| **`fetch_page`**      | Fast HTTP request with stealth headers. Works for GitHub, docs, static pages | ~1-2s    |
| **`stealth_fetch_page`** | Real headless browser with anti-bot evasion. Bypasses Cloudflare, renders JS | ~5-15s   |
| **`extract_elements`** | Fetch a page and extract multiple elements via CSS selectors as structured JSON | ~1-2s |
| **`get_youtube_transcript`** | Fetch YouTube video transcripts/captions with language fallback | ~1-3s |

`fetch_page` and `stealth_fetch_page` support:

- **`css_selector`** — extract specific elements instead of the full page
- **`to_markdown`** — convert HTML to readable Markdown (default: `true`)
- Automatic truncation at 80,000 characters

`get_youtube_transcript` supports:

- Standard watch URLs, `youtu.be` short links, and `/shorts/` URLs
- Preferred language with automatic fallback to the first available language
- Automatic truncation at 80,000 characters

---

## Quick Start

```bash
# Create a directory and grab the required files
mkdir shark-no-kari && cd shark-no-kari
curl -LO https://raw.githubusercontent.com/HaiNick/Shark-no-Kari/main/docker-compose.yml
curl -LO https://raw.githubusercontent.com/HaiNick/Shark-no-Kari/main/Caddyfile

# Configure — edit .env with your domain and optional API key
curl -LO https://raw.githubusercontent.com/HaiNick/Shark-no-Kari/main/.env.example
mv .env.example .env

# Start (pulls the pre-built image from ghcr.io)
docker compose up -d
```

Then add `https://your-domain.com/mcp` as a custom connector in [claude.ai](https://claude.ai) settings.

---

## Deployment

### Prerequisites

| Requirement          | Details                                                  |
| -------------------- | -------------------------------------------------------- |
| **VPS**              | Ubuntu 24.04, 1 GB+ RAM (headless browser needs ~512 MB) |
| **Domain**           | A subdomain you can point to the server                   |
| **Claude account**   | Pro or Max (free accounts get 1 custom connector)         |

### 1. Provision a VPS

Any provider works (Hetzner, DigitalOcean, Vultr, Linode, etc.).

- **OS:** Ubuntu 24.04
- **RAM:** 1 GB minimum
- **Recommended:** Hetzner Cloud CPX22 in Falkenstein (tested, low latency to Anthropic EU)

### 2. Point your domain

Create an A record for your subdomain (e.g. `kari.snowy-burbot.com`) pointing to the server's IPv4 address. Wait for DNS propagation.

### 3. Bootstrap the VPS

```bash
ssh root@<server-ip>
curl -sSL https://raw.githubusercontent.com/HaiNick/Shark-no-Kari/main/scripts/setup-vps.sh | bash
```

Or run the commands from [`scripts/setup-vps.sh`](scripts/setup-vps.sh) manually. This installs Docker and creates `/opt/shark-no-kari`.

### 4. Deploy

```bash
cd /opt/shark-no-kari

# Grab the required files
curl -LO https://raw.githubusercontent.com/HaiNick/Shark-no-Kari/main/docker-compose.yml
curl -LO https://raw.githubusercontent.com/HaiNick/Shark-no-Kari/main/Caddyfile

# Configure environment
curl -LO https://raw.githubusercontent.com/HaiNick/Shark-no-Kari/main/.env.example
mv .env.example .env
# Auth is disabled by default — Caddy IP allowlist handles security (see below)

# Start (pulls the pre-built image from ghcr.io)
docker compose up -d
```

First pull downloads ~2 GB (browser binaries are included in the image). Verify:

```bash
docker compose logs -f shark-no-kari
curl -s https://kari.snowy-burbot.com/mcp | head
```

### 5. Connect to Claude

1. Open [claude.ai](https://claude.ai)
2. Go to **Settings** -> **Connectors**
3. Click **Add custom connector**
4. Enter the URL: `https://kari.snowy-burbot.com/mcp`
5. Click **Add**

The tools now appear in the **Search and tools** menu in any conversation.

---

## Usage in Claude

Once connected, Claude can call the tools automatically when `web_fetch` fails, or you can ask directly:

> "Use the scrapling fetcher to get the contents of https://github.com/user/repo/blob/main/README.md"

> "Stealth-fetch https://example.com and extract all elements matching `.product-card`"

---

## Security

### IP Allowlisting

Authentication is disabled (`MCP_API_KEY` is empty). Instead, Caddy restricts access to Anthropic's outbound IP range via an IP allowlist. Only requests from claude.ai's servers can reach the MCP endpoint; all others receive a 403.

```
@blocked not remote_ip 160.79.104.0/21
respond @blocked 403
```

See [Anthropic's IP ranges documentation](https://support.claude.com/en/articles/11503834) for the latest list.

### DNS Rebinding Protection Workaround

The MCP SDK includes DNS rebinding protection that rejects requests where the `Host` header doesn't match the server's expected hostname. Since Caddy proxies to the Docker container as `shark-no-kari:8000`, the `Host` header won't match. The Caddyfile includes a header rewrite to satisfy the SDK's check:

```
reverse_proxy shark-no-kari:8000 {
    header_up Host localhost:8000
}
```

### Optional Bearer Token Auth

If you prefer token-based auth (e.g. when not using Caddy), set `MCP_API_KEY` in `.env`:

```bash
MCP_API_KEY=$(openssl rand -hex 32)
```

Every request must then include an `Authorization: Bearer <key>` header. Claude sends this automatically if you configure it in the connector's advanced settings.

For a stronger alternative that gives you per-user login and consent, see [OAuth (OIDC) Authentication](#oauth-oidc-authentication) below.

---

## OAuth (OIDC) Authentication

Shark-no-Kari supports optional OAuth 2.1 authentication federated to a self-hosted [Pocket ID](https://pocket-id.org) instance via OIDC. When enabled, Claude opens a browser tab the first time it connects and you log in through Pocket ID. The MCP server issues its own short-lived JWTs to Claude; Pocket ID is only involved during the browser-based login.

### Auth Mode Comparison

| Mode | How it works | When to use |
|------|-------------|-------------|
| **IP allowlist** (default) | Caddy blocks all non-Anthropic IPs. No token needed. | Simplest. Fine if you only use claude.ai. |
| **Bearer token** (`MCP_API_KEY`) | Static secret in the `Authorization` header. | When you need a token-gated endpoint without OIDC. |
| **OIDC** (`OIDC_ENABLED=true`) | OAuth 2.1 + Pocket ID browser login. Per-user consent, short-lived tokens. | Strongest. Recommended for multi-user or internet-facing deployments. |

`OIDC_ENABLED` and `MCP_API_KEY` are mutually exclusive. The server raises a startup error if both are set.

### Pocket ID Client Setup

In your Pocket ID admin panel, create a new OIDC application:

| Field | Value |
|-------|-------|
| **Name** | `Shark-no-Kari` (or any label) |
| **Redirect URI** | `https://kari.snowy-burbot.com/auth/callback` |
| **Scopes** | `openid`, `profile`, `email` |
| **PKCE** | Enabled (S256) |
| **Public client** | Off (confidential client with a secret) |

Copy the generated **Client ID** and **Client Secret** for the next step.

### Enable OIDC in .env

Generate the two key material values:

```bash
# JWT signing key (for fastmcp's own tokens issued to MCP clients):
openssl rand -hex 32

# Fernet encryption key (for the on-disk DCR registration store):
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Then set these variables in `.env`:

```bash
OIDC_ENABLED=true
MCP_API_KEY=                          # must be empty when OIDC is on
OIDC_CONFIG_URL=https://id.snowy-burbot.com/.well-known/openid-configuration
OIDC_CLIENT_ID=<paste from Pocket ID>
OIDC_CLIENT_SECRET=<paste from Pocket ID>
OIDC_BASE_URL=https://kari.snowy-burbot.com
JWT_SIGNING_KEY=<output of openssl command>
STORAGE_ENCRYPTION_KEY=<output of python command>
```

Restart the stack: `docker compose up -d`

On the first connection from Claude, it will open a browser tab. Log in with your Pocket ID account and click **Allow**. Subsequent connections reuse the cached token silently.

### Verification

After deploying with OIDC enabled, run [`scripts/verify-oidc.sh`](scripts/verify-oidc.sh):

```bash
bash scripts/verify-oidc.sh https://kari.snowy-burbot.com
```

Expected output shape:

```
==> Protected resource metadata
{
  "resource": "https://kari.snowy-burbot.com",
  "authorization_servers": ["https://kari.snowy-burbot.com"],
  ...
}

==> Authorization server metadata
{
  "issuer": "https://kari.snowy-burbot.com",
  "authorization_endpoint": "https://kari.snowy-burbot.com/authorize",
  "token_endpoint": "https://kari.snowy-burbot.com/token",
  ...
}

==> Unauthenticated /mcp must 401 with WWW-Authenticate
www-authenticate: Bearer realm="..."
```

If the third check produces no output, the server is not returning a `WWW-Authenticate` header, which means OIDC is not active.

---

## Architecture

### Tech Stack

| Layer           | Technology                                                       | Why                                           |
| --------------- | ---------------------------------------------------------------- | --------------------------------------------- |
| **MCP Server**  | [FastMCP](https://gofastmcp.com) (PrefectHQ)                    | MCP SDK with built-in OAuth 2.1 / OIDCProxy   |
| **Scraping**    | [Scrapling](https://github.com/D4Vinci/Scrapling)               | Stealth headers + headless browser (Camoufox) |
| **HTML→MD**     | [html2text](https://github.com/Alir3z4/html2text)               | Clean Markdown conversion                     |
| **ASGI Server** | [uvicorn](https://www.uvicorn.org)                               | Fast async Python server                      |
| **Reverse Proxy** | [Caddy](https://caddyserver.com)                              | Auto HTTPS, IP allowlisting, OAuth path pass-through |
| **Auth (OIDC)** | OIDCProxy + [Pocket ID](https://pocket-id.org)                  | OAuth 2.1 with self-hosted OIDC provider      |
| **OAuth store** | py-key-value-aio FileTreeStore + Fernet encryption              | Encrypted on-disk DCR registration persistence |
| **Deployment**  | Docker + Docker Compose                                          | Single command setup                          |

### Project Structure

```
Shark-no-Kari/
├── src/
│   └── server.py            MCP server (FastMCP + Scrapling tools + optional OIDC auth)
├── tests/
│   └── test_server.py       pytest test suite for all tools + OIDC startup tests
├── scripts/
│   ├── setup-vps.sh         Bootstrap script for a fresh Ubuntu VPS
│   └── verify-oidc.sh       Smoke-test script for OIDC endpoints
├── .github/
│   └── workflows/
│       └── docker-publish.yml  CI: build & push Docker image to ghcr.io
├── Caddyfile                 Reverse proxy config (auto HTTPS + IP allowlist + OAuth paths)
├── docker-compose.yml        Orchestrates MCP server + Caddy + oauth_state volume
├── Dockerfile                Builds the MCP server image (Python 3.12 + browser deps)
├── pyproject.toml            pytest configuration
├── requirements.txt          Python dependencies
├── .env.example              Environment variable template (includes OIDC vars)
├── LICENSE                   MIT
└── .gitignore
```

### How It Works

```
                    claude.ai
                       │
                       │ HTTPS (Streamable HTTP MCP)
                       ▼
                ┌─────────────┐
                │    Caddy    │  Auto HTTPS + IP allowlist (160.79.104.0/21)
                │   :80/:443  │  header_up Host localhost:8000
                └──────┬──────┘
                       │
                       ▼
              ┌──────────────────┐
              │  shark-no-kari   │  FastMCP server (uvicorn :8000)
              │                  │
              │  fetch_page()    │  → Scrapling Fetcher (stealth HTTP)
              │  stealth_fetch() │  → Scrapling StealthyFetcher (headless browser)
              │  extract_elems() │  → Multi-selector structured extraction
              │  yt_transcript() │  → YouTube transcript API
              │                  │
              │  html2text       │  → Markdown conversion + truncation
              └────────┬─────────┘
                       │ PROXY_URL fallback (on direct fetch failure)
                       ▼
              ┌──────────────────┐
              │  nordlynx-proxy  │  NordVPN WireGuard tunnel (sidecar)
              │  kari-nordlynx   │  dante SOCKS5 :1080 + tinyproxy :8888
              └──────────────────┘
```

---

## Configuration

### Environment Variables

| Variable      | Default | Description                                                         |
| ------------- | ------- | ------------------------------------------------------------------- |
| `MCP_API_KEY` | _(empty)_ | Bearer token for auth. Empty = disabled (use Caddy IP allowlist). Cannot be set together with `OIDC_ENABLED=true`. |
| `PROXY_URL`   | `socks5h://kari-nordlynx:1080` | SOCKS5 proxy fallback — retries via proxy when direct requests fail. Defaults to the bundled `nordlynx-proxy` sidecar container |
| `NORDVPN_TOKEN` | _(empty)_ | NordVPN access token from [Nord Account > Manual setup](https://my.nordaccount.com/dashboard/nordvpn/manual-configuration/). Required for proxy fallback via `nordlynx-proxy` |
| `NORDVPN_COUNTRY` | `Germany` | NordVPN server country used by `nordlynx-proxy` for the WireGuard tunnel |
| `HOST`        | `0.0.0.0` | Server bind address                                               |
| `PORT`        | `8000`    | Server port                                                       |
| `OIDC_ENABLED` | `false` | Set to `true` to activate OAuth 2.1 via OIDC. All `OIDC_*` vars and `JWT_SIGNING_KEY`, `STORAGE_ENCRYPTION_KEY` are required when enabled. |
| `OIDC_CONFIG_URL` | _(empty)_ | URL of the OIDC provider's discovery document (e.g. `https://id.example.com/.well-known/openid-configuration`) |
| `OIDC_CLIENT_ID` | _(empty)_ | Client ID from your Pocket ID application |
| `OIDC_CLIENT_SECRET` | _(empty)_ | Client secret from your Pocket ID application |
| `OIDC_BASE_URL` | _(empty)_ | Public base URL of this server (e.g. `https://kari.snowy-burbot.com`). Used for redirect URIs. |
| `JWT_SIGNING_KEY` | _(empty)_ | Secret for signing JWTs issued to MCP clients. Generate with `openssl rand -hex 32`. |
| `STORAGE_ENCRYPTION_KEY` | _(empty)_ | Fernet key for encrypting the on-disk OAuth client store. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. |

### Caddyfile

The Caddyfile is mounted read-only into the Caddy container. Edit it to change your domain or IP allowlist:

```
kari.snowy-burbot.com {
    @blocked not remote_ip 160.79.104.0/21
    respond @blocked 403

    reverse_proxy shark-no-kari:8000 {
        header_up Host localhost:8000
    }
}
```

---

## Local Development

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
scrapling install    # Downloads browser binaries (Camoufox, Playwright)

# Run the server (no auth for local dev)
python src/server.py
# Server starts on http://localhost:8000/mcp
```

Test with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
```

---

## Docker

### Run

```bash
docker compose up -d            # Pull and start in background
docker compose logs -f          # View logs
docker compose down             # Stop
```

Images are built automatically by CI and pushed to `ghcr.io/hainick/shark-no-kari`.

### Services

| Service          | Image              | Ports     | Purpose                          |
| ---------------- | ------------------ | --------- | -------------------------------- |
| `shark-no-kari`  | `ghcr.io/hainick/shark-no-kari:latest` | 8000 (internal) | MCP server |
| `nordlynx-proxy` | `edgd1er/nordlynx-proxy:latest` | 1080, 8888 (internal) | NordVPN WireGuard tunnel + local SOCKS5/HTTP proxy |
| `caddy`          | `caddy:2-alpine`   | 80, 443   | Reverse proxy, auto HTTPS, ACL   |

### Dockerfile

Multi-step build:

1. Install system libraries required by headless browsers (NSS, GTK, etc.)
2. Install Python dependencies from `requirements.txt`
3. Run `scrapling install` to download browser binaries (Camoufox, Playwright)
4. Copy `src/` and start with `python src/server.py`

The container uses `shm_size: 512mb` for headless browser shared memory.

---

## Testing

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run the test suite
pytest tests/ -v
```

The test suite covers all four tools with mocked external calls (no network requests needed).

---

## Resource Usage

| State                        | RAM         |
| ---------------------------- | ----------- |
| Idle                         | ~80 MB      |
| During `fetch_page`          | ~120 MB     |
| During `stealth_fetch_page`  | ~400-600 MB |

1 GB RAM handles this fine for personal use. For concurrent stealth requests, consider 2 GB+.

---

## Troubleshooting

### Build fails downloading browser binaries

The `scrapling install` step downloads ~200 MB of browser binaries. If it times out, retry:

```bash
docker compose build --no-cache
```

### `stealth_fetch_page` crashes with shared memory errors

Ensure `shm_size: 512mb` is set in `docker-compose.yml` (it is by default). Headless browsers need more shared memory than Docker's default 64 MB.

### Caddy returns 403

Your IP is not in the allowlist. If testing from your machine, temporarily add your IP to the Caddyfile:

```
@blocked not remote_ip 160.79.104.0/21 YOUR.IP.HERE/32
respond @blocked 403
```

### MCP SDK rejects requests with "Host header mismatch"

The `header_up Host localhost:8000` directive in the Caddyfile handles this. If you've customised the Caddyfile, ensure the header rewrite is present. See [DNS Rebinding Protection Workaround](#dns-rebinding-protection-workaround).

### Sites block requests with HTTP/2 PROTOCOL_ERROR

Some sites (e.g. xda-developers.com) reject requests from datacenter IPs at the protocol level. The stack ships with a bundled `nordlynx-proxy` sidecar container that runs the NordVPN Linux client internally, opens a NordLynx (WireGuard) tunnel, and exposes a local SOCKS5 proxy on port 1080 that only the `shark-no-kari` container can reach over the Docker network. Requests are first tried directly, and only retried through the proxy if the direct request fails or returns a non-200 status.

To enable it, set a NordVPN access token in `.env` (get one from [Nord Account > Manual setup](https://my.nordaccount.com/dashboard/nordvpn/manual-configuration/) by clicking "Get Access token"):

```bash
NORDVPN_TOKEN=your-access-token-here
NORDVPN_COUNTRY=Germany
PROXY_URL=socks5h://kari-nordlynx:1080
```

Use `socks5h://` (not `socks5://`) so the proxy handles DNS resolution. If you don't want to run a proxy, leave `NORDVPN_TOKEN` empty and remove or comment out the `nordlynx-proxy` service and the `depends_on` block in `docker-compose.yml`.

### nordlynx-proxy fails to connect

- Check logs: `docker compose logs kari-nordlynx` for auth errors
- Verify the token is valid at https://my.nordaccount.com/dashboard/nordvpn/manual-configuration/
- Try a different country in `.env`: `NORDVPN_COUNTRY=Netherlands`
- The container needs `privileged: true`, `NET_ADMIN` + `SYS_MODULE` capabilities, and the `net.ipv6.conf.all.disable_ipv6` + `net.ipv4.conf.all.rp_filter` sysctls (all preconfigured in `docker-compose.yml`). Privileged mode is required by the Debian-based nordlynx-proxy image because the NordVPN client writes sysctls itself at connect time

### Claude doesn't see the tools

1. Verify the server is running: `curl -s https://your-domain.com/mcp | head`
2. Check the connector status in claude.ai **Settings** -> **Connectors**
3. Try removing and re-adding the connector

---

## Acknowledgements

- [Scrapling](https://github.com/D4Vinci/Scrapling) — the scraping engine that powers both tools (stealth HTTP + headless browser via Camoufox)
- [FastMCP](https://github.com/modelcontextprotocol/python-sdk) — official Python MCP SDK that makes building MCP servers painless
- [Caddy](https://caddyserver.com) — automatic HTTPS and dead-simple reverse proxy config
- [html2text](https://github.com/Alir3z4/html2text) — clean HTML-to-Markdown conversion
- [uvicorn](https://www.uvicorn.org) — fast ASGI server
- [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) — YouTube transcript/caption fetching
- [nordlynx-proxy](https://github.com/edgd1er/nordlynx-proxy) — NordVPN WireGuard tunnel in Docker with local SOCKS5/HTTP proxy

---

## License

This project is licensed under the [MIT License](LICENSE).
