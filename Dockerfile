# Node builds the web bundle and internal battle adapter; Python serves the public API.
# The game snapshot is built into the image. Reference and battle tools work offline;
# visitor-key chat and optional research contact Gemini.

FROM node:22-bookworm-slim AS battle
WORKDIR /app/battle
COPY battle/package.json battle/package-lock.json battle/.npmrc ./
RUN npm ci --omit=optional --ignore-scripts --no-audit --no-fund
COPY battle/bridge.cjs ./

FROM node:22-bookworm-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS app
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 && rm -rf /var/lib/apt/lists/*
COPY --from=battle /usr/local/bin/node /usr/local/bin/node
COPY --from=battle /app/battle /app/battle
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ROTOM_DB=/app/data/build/rotom.sqlite3 \
    ROTOM_WEB_DIST=/app/web/dist

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./
COPY rotom_dex/ ./rotom_dex/
RUN uv sync --frozen --no-dev

# The pinned source cache and the reviewed packs. Everything the import needs, and nothing else.
COPY data/sources/ ./data/sources/
COPY data/games/ ./data/games/
COPY data/mechanics/ ./data/mechanics/
COPY data/game-packs/ ./data/game-packs/
COPY data/eval/ ./data/eval/
COPY data/knowledge/ ./data/knowledge/

# Build the snapshot into the image, then prove it. A failing check fails the build.
ARG ROTOM_GAMES=all
RUN uv run rotom import --db "$ROTOM_DB" --games "$ROTOM_GAMES" > /dev/null \
 && uv run rotom check --db "$ROTOM_DB" > /dev/null

COPY --from=web /app/web/dist ./web/dist

RUN useradd --create-home --uid 10001 rotom && chown -R rotom /app
USER rotom

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["uv", "run", "rotom", "serve", "--db", "/app/data/build/rotom.sqlite3", "--host", "0.0.0.0", "--port", "8000"]
