<div align="center">

# Shark-no-Kari (狩り - the hunt)

**Remote MCP server for web scraping with anti-bot evasion**

Stealth HTTP fetching · Headless browser · Cloudflare bypass · CSS selectors · Markdown conversion

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-Streamable_HTTP-8A2BE2)](https://modelcontextprotocol.io)
[![Scrapling](https://img.shields.io/pypi/v/scrapling?label=Scrapling&color=green)](https://github.com/D4Vinci/Scrapling)

_Claude's built-in `web_fetch` fails on GitHub blob URLs, Cloudflare-protected sites, and JS-rendered pages._
**Shark-no-Kari** is a remote MCP server that gives Claude two new tools powered by [Scrapling](https://github.com/D4Vinci/Scrapling) — a fast HTTP fetcher with stealth headers and a real headless browser with anti-bot evasion. Deploy it on any VPS with Docker, add the URL as a custom connector in claude.ai, and Claude can fetch pages that were previously unreachable.

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

Both tools support:

- **`css_selector`** — extract specific elements instead of the full page
- **`to_markdown`** — convert HTML to readable Markdown (default: `true`)
- Automatic truncation at 80,000 characters

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/HaiNick/Shark-no-Kari.git
cd Shark-no-Kari

# Configure
cp .env.example .env

# Build and start
docker compose up -d --build
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
git clone https://github.com/HaiNick/Shark-no-Kari.git .

# Configure environment
cp .env.example .env
# Auth is disabled by default — Caddy IP allowlist handles security (see below)

# Build and start
docker compose up -d --build
```

First build takes 3-5 minutes (downloading browser binaries). Verify:

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

---

## Architecture

### Tech Stack

| Layer           | Technology                                                       | Why                                           |
| --------------- | ---------------------------------------------------------------- | --------------------------------------------- |
| **MCP Server**  | [FastMCP](https://github.com/modelcontextprotocol/python-sdk)    | Official Python MCP SDK, streamable HTTP      |
| **Scraping**    | [Scrapling](https://github.com/D4Vinci/Scrapling)               | Stealth headers + headless browser (Camoufox) |
| **HTML→MD**     | [html2text](https://github.com/Alir3z4/html2text)               | Clean Markdown conversion                     |
| **ASGI Server** | [uvicorn](https://www.uvicorn.org)                               | Fast async Python server                      |
| **Reverse Proxy** | [Caddy](https://caddyserver.com)                              | Auto HTTPS, IP allowlisting                   |
| **Deployment**  | Docker + Docker Compose                                          | Single command setup                          |

### Project Structure

```
Shark-no-Kari/
├── src/
│   └── server.py            MCP server (FastMCP + Scrapling tools + auth middleware)
├── scripts/
│   └── setup-vps.sh         Bootstrap script for a fresh Ubuntu VPS
├── Caddyfile                 Reverse proxy config (auto HTTPS + IP allowlist)
├── docker-compose.yml        Orchestrates MCP server + Caddy
├── Dockerfile                Builds the MCP server image (Python 3.12 + browser deps)
├── requirements.txt          Python dependencies
├── .env.example              Environment variable template
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
              │                  │
              │  html2text       │  → Markdown conversion + truncation
              └──────────────────┘
```

---

## Configuration

### Environment Variables

| Variable      | Default | Description                                                         |
| ------------- | ------- | ------------------------------------------------------------------- |
| `MCP_API_KEY` | _(empty)_ | Bearer token for auth. Empty = disabled (use Caddy IP allowlist)  |
| `PROXY_URL`   | _(empty)_ | SOCKS5 proxy fallback — retries via proxy when direct requests fail. Format: `socks5://user:pass@host:port` |
| `HOST`        | `0.0.0.0` | Server bind address                                               |
| `PORT`        | `8000`    | Server port                                                       |

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

### Build and Run

```bash
docker compose up -d --build    # Build and start in background
docker compose logs -f          # View logs
docker compose down             # Stop
```

### Services

| Service          | Image              | Ports     | Purpose                          |
| ---------------- | ------------------ | --------- | -------------------------------- |
| `shark-no-kari`  | Built from `Dockerfile` | 8000 (internal) | MCP server                |
| `caddy`          | `caddy:2-alpine`   | 80, 443   | Reverse proxy, auto HTTPS, ACL   |

### Dockerfile

Multi-step build:

1. Install system libraries required by headless browsers (NSS, GTK, etc.)
2. Install Python dependencies from `requirements.txt`
3. Run `scrapling install` to download browser binaries (Camoufox, Playwright)
4. Copy `src/` and start with `python src/server.py`

The container uses `shm_size: 512mb` for headless browser shared memory.

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

Some sites (e.g. xda-developers.com) reject requests from datacenter IPs at the protocol level. Set `PROXY_URL` in `.env` to enable automatic proxy fallback — requests are first tried directly, and only retried through the proxy if the direct request fails or returns a non-200 status:

```bash
# NordVPN SOCKS5 example (get credentials from NordVPN dashboard > Services > Service credentials)
PROXY_URL=socks5://user:pass@amsterdam.socks.nordhold.net:1080
```

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

---

## License

This project is licensed under the [MIT License](LICENSE).
