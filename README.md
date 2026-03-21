# Shark-no-Kari (狩り - the hunt)

A remote MCP (Model Context Protocol) server that gives Claude the ability to
fetch web pages using [Scrapling](https://github.com/D4Vinci/Scrapling) --
bypassing anti-bot protections that cause Claude's built-in `web_fetch` to fail.

Deploy it on any VPS with Docker (tested on Hetzner Cloud CPX22 in Falkenstein),
add the URL as a custom connector in claude.ai, and Claude gains two new tools:

- **fetch_page** -- fast HTTP request with stealth headers (static pages, GitHub, docs)
- **stealth_fetch_page** -- real headless browser with anti-bot evasion (Cloudflare, JS-rendered pages)

## Project structure

```
shark-no-kari/
  src/
    server.py          # MCP server (FastMCP + Scrapling)
  scripts/
    setup-vps.sh       # Bootstrap script for a fresh Ubuntu VPS
  Caddyfile            # Reverse proxy config (auto HTTPS + IP allowlist)
  docker-compose.yml   # Orchestrates MCP server + Caddy
  Dockerfile           # Builds the MCP server image
  requirements.txt     # Python dependencies
  .env.example         # Environment variable template
  .gitignore
```

## Prerequisites

- A VPS running Ubuntu 24.04 (1 GB+ RAM)
- A domain name (or subdomain) you can point to the server
- Claude Pro/Max account (free accounts get 1 custom connector)

## Deployment

### 1. Provision a VPS

Any provider works (Hetzner, DigitalOcean, Vultr, Linode, etc.). Requirements:

- OS: Ubuntu 24.04
- RAM: 1 GB minimum (the headless browser needs ~512 MB)
- Recommended: Hetzner Cloud CPX22 in Falkenstein for low latency to Anthropic EU

### 2. Point your domain

Create an A record for your chosen subdomain (e.g. `kari.snowy-burbot.com`) pointing
to the server's IPv4 address. Wait for DNS propagation.

### 3. Bootstrap the VPS

```bash
ssh root@<server-ip>
curl -sSL https://raw.githubusercontent.com/HaiNick/shark-no-kari/main/scripts/setup-vps.sh | bash
```

Or run the commands from `scripts/setup-vps.sh` manually. This installs Docker and
creates the project directory at `/opt/shark-no-kari`.

### 4. Deploy the project

```bash
cd /opt/shark-no-kari

# Clone the repo
git clone https://github.com/HaiNick/shark-no-kari.git .

# Configure environment
cp .env.example .env
# .env ships with auth disabled -- Caddy IP allowlist handles security (see below)

# Build and start
docker compose up -d --build
```

First build takes 3-5 minutes (downloading browser binaries). After that:

```bash
# Check logs
docker compose logs -f shark-no-kari

# Verify it is running
curl -s https://kari.snowy-burbot.com/mcp | head
```

### 5. Connect to Claude

1. Open [claude.ai](https://claude.ai)
2. Go to **Settings** -> **Connectors**
3. Click **Add custom connector**
4. Enter the URL: `https://kari.snowy-burbot.com/mcp`
5. Click **Add**

The tools now appear in the **Search and tools** menu in any conversation.

## Usage in Claude

Once connected, Claude can call the tools automatically when `web_fetch` fails,
or you can ask directly:

> "Use the scrapling fetcher to get the contents of https://github.com/user/repo/blob/main/README.md"

> "Stealth-fetch https://example.com and extract all elements matching .product-card"

## Security

Authentication is disabled (`MCP_API_KEY` is empty). Instead, Caddy restricts
access to Anthropic's outbound IP range (`160.79.104.0/21`) via an IP allowlist.
Only requests from claude.ai's servers can reach the MCP endpoint; all others
receive a 403.

See [Anthropic's IP ranges documentation](https://support.claude.com/en/articles/11503834)
for the latest list.

### DNS rebinding protection workaround

The MCP SDK includes DNS rebinding protection that rejects requests where the
`Host` header doesn't match the server's expected hostname. Since Caddy proxies
to the Docker container as `shark-no-kari:8000`, the `Host` header won't match.
The Caddyfile includes `header_up Host localhost:8000` to rewrite the `Host`
header, which satisfies the SDK's check.

## Running locally (for development)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
scrapling install

# Run without auth for local testing
python src/server.py
# Server starts on http://localhost:8000/mcp
```

Test with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
```

## Resource usage

On a 1 GB VPS:

- Idle: ~80 MB (Python + uvicorn)
- During `fetch_page`: ~120 MB
- During `stealth_fetch_page`: ~400-600 MB (headless browser)

1 GB RAM handles this fine for personal use. If you plan to make many
concurrent stealth requests, consider 2 GB+ RAM.

## License

MIT
