FROM python:3.14-slim

# System deps for browser fetchers (Scrapling/Camoufox, CloakBrowser/Chromium)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg ca-certificates unzip \
    # Browser runtime deps
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libwayland-client0 fonts-noto-color-emoji \
    fonts-freefont-ttf fonts-unifont fonts-ipafont-gothic fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

# JS runtime yt-dlp needs to solve YouTube's signature/cipher challenge for the
# "web" player client (the client PO tokens actually apply to). Without it,
# yt-dlp silently falls back to non-JS clients (e.g. android_vr), which don't
# use PO tokens and increasingly hit their own LOGIN_REQUIRED wall.
RUN curl -fsSL https://deno.land/install.sh | sh -s -- -y \
    && mv /root/.deno/bin/deno /usr/local/bin/deno

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Refresh Scrapling browser fingerprints
RUN scrapling install --force

# Pre-download CloakBrowser binary at build time
RUN python -m cloakbrowser install

COPY pyproject.toml .
COPY src/ ./src/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf -X POST http://localhost:8000/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -d '{"jsonrpc":"2.0","id":0,"method":"ping","params":{}}' || exit 1

CMD ["python", "src/server.py"]
