# Shark-no-Kari (狩り - the hunt)

A remote MCP (Model Context Protocol) server that gives Claude the ability to
fetch web pages using [Scrapling](https://github.com/D4Vinci/Scrapling) --
bypassing anti-bot protections that cause Claude's built-in `web_fetch` to fail.

Deploy it on a $4-6/mo DigitalOcean Droplet, add the URL as a custom connector
in claude.ai, and Claude gains two new tools:

- **fetch_page** -- fast HTTP request with stealth headers (static pages, GitHub, docs)
- **stealth_fetch_page** -- real headless browser with anti-bot evasion (Cloudflare, JS-rendered pages)

## Project structure

```
shark-no-kari/
  src/
    server.py          # MCP server (FastMCP + Scrapling)
  scripts/
    setup-droplet.sh   # Bootstrap script for a fresh Ubuntu Droplet
  Caddyfile            # Reverse proxy config (auto HTTPS)
  docker-compose.yml   # Orchestrates MCP server + Caddy
  Dockerfile           # Builds the MCP server image
  requirements.txt     # Python dependencies
  .env.example         # Environment variable template
  .gitignore
```

## Prerequisites

- A domain name (or subdomain) you can point to the Droplet
- A DigitalOcean account (or any VPS provider)
- Claude Pro/Max account (free accounts get 1 custom connector)

## Deployment on DigitalOcean

### 1. Create a Droplet

- Image: Ubuntu 24.04
- Plan: Basic, $6/mo (1 GB RAM) -- the headless browser needs ~512 MB
- Region: closest to you (or Frankfurt for lower latency to Anthropic EU)
- Auth: SSH key

### 2. Point your domain

Create an A record for your chosen subdomain (e.g. `kari.snowy-burbot.com`) pointing
to the Droplet's IPv4 address. Wait for DNS propagation.

### 3. Bootstrap the Droplet

```bash
ssh root@<droplet-ip>
curl -sSL https://raw.githubusercontent.com/<you>/shark-no-kari/main/scripts/setup-droplet.sh | bash
```

Or run the commands from `scripts/setup-droplet.sh` manually.

### 4. Deploy the project

```bash
cd /opt/shark-no-kari

# Copy files (scp, git clone, etc.)
git clone https://github.com/<you>/shark-no-kari.git .

# Configure environment
cp .env.example .env
nano .env
# Set MCP_API_KEY to a random secret:  openssl rand -hex 32
# Set DOMAIN to your subdomain:       kari.snowy-burbot.com

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
5. (If using auth) Click **Advanced settings** and add your bearer token
6. Click **Add**

The tools now appear in the **Search and tools** menu in any conversation.

## Usage in Claude

Once connected, Claude can call the tools automatically when `web_fetch` fails,
or you can ask directly:

> "Use the scrapling fetcher to get the contents of https://github.com/user/repo/blob/main/README.md"

> "Stealth-fetch https://example.com and extract all elements matching .product-card"

## Authentication

If `MCP_API_KEY` is set in `.env`, every request to the MCP server must include
a `Authorization: Bearer <key>` header. Claude sends this automatically if you
configure it in the connector's advanced settings.

If `MCP_API_KEY` is empty, the server runs without authentication. Fine for
testing but not recommended for production.

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

On the $6 Droplet (1 GB RAM):

- Idle: ~80 MB (Python + uvicorn)
- During `fetch_page`: ~120 MB
- During `stealth_fetch_page`: ~400-600 MB (headless browser)

The 1 GB Droplet handles this fine for personal use. If you plan to make many
concurrent stealth requests, consider the $12/mo tier (2 GB RAM).

## License

MIT
