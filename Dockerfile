# Two stages: Node builds the bundle, Python runs the server. The database is built at image build
# time so the container needs no network and no volume to answer a request -- the same offline
# guarantee the project makes everywhere else.

FROM node:22-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS app
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
