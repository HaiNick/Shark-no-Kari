FROM python:3.14-slim

# System deps for browser fetchers (Scrapling/Camoufox, CloakBrowser/Chromium)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg ca-certificates \
    # Browser runtime deps
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libwayland-client0 fonts-noto-color-emoji \
    fonts-freefont-ttf fonts-unifont fonts-ipafont-gothic fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

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
