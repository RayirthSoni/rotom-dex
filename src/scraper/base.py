"""
Abstract base scraper for rotom-dex.

Every scraper (PokeAPI, PokemonDB …) inherits from BaseScraper and gets
the following for free:

  - A requests.Session pre-configured with exponential-backoff retries
  - Transparent disk caching for both JSON responses and raw HTML pages
  - A fixed-interval rate limiter so we stay polite to upstream servers
  - save_json / load_json convenience helpers
  - An abstract scrape_all() contract that subclasses must implement

Why sync and not async?
  Scrapers are offline batch jobs — they run once to populate data/raw/ and
  are never in the hot-path of user requests.  Sync + optional threading is
  the simplest approach and already covered by the requests library that is
  already a dependency.  The FastAPI layer (the latency-sensitive part) is
  independently async.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------


@dataclass
class ScrapeConfig:
    """
    Configuration shared by every BaseScraper subclass.

    Parameters
    ----------
    cache_dir : Path
        Where raw HTTP responses are cached on disk.  Re-running a scraper
        that already has a warm cache makes zero HTTP requests.
    output_dir : Path
        Root directory for structured output JSON files.
    calls_per_second : float
        Maximum request rate.  PokeAPI asks for ≤ 2 req/s; PokemonDB is
        an HTML site so keep this at ≤ 1.
    max_retries : int
        How many times to retry a failed request (with exponential back-off).
    timeout : int
        Per-request timeout in seconds.
    """

    cache_dir: Path = field(default_factory=lambda: Path("data/raw/scraper_cache"))
    output_dir: Path = field(default_factory=lambda: Path("data/raw"))
    calls_per_second: float = 1.5
    max_retries: int = 3
    timeout: int = 30

    def __post_init__(self) -> None:
        # Accept plain strings so callers can write ScrapeConfig(cache_dir="…")
        self.cache_dir = Path(self.cache_dir)
        self.output_dir = Path(self.output_dir)


# ---------------------------------------------------------------------------
# Rate limiter dataclass
# ---------------------------------------------------------------------------


@dataclass
class RateLimiter:
    """
    Simple fixed-interval rate limiter.

    Tracks the timestamp of the last outbound call and sleeps just long
    enough to honour ``calls_per_second`` before each new request.
    """

    calls_per_second: float = 1.5
    # Mutable state — excluded from __init__ and __repr__
    _last_call: float = field(default=0.0, init=False, repr=False)

    def wait(self) -> None:
        """Block until it is safe to make the next request."""
        interval = 1.0 / self.calls_per_second
        now = time.monotonic()
        sleep_for = interval - (now - self._last_call)
        if sleep_for > 0:
            time.sleep(sleep_for)
        self._last_call = time.monotonic()


# ---------------------------------------------------------------------------
# Abstract base scraper
# ---------------------------------------------------------------------------


class BaseScraper(ABC):
    """
    Abstract base for all rotom-dex scrapers.

    Subclass and implement :py:meth:`scrape_all`.

    Example
    -------
    ::

        class MyScraper(BaseScraper):
            def scrape_all(self) -> dict[str, Any]:
                html = self.get_html("https://example.com/page")
                data = self.get_json("https://api.example.com/data")
                self.save_json(data, self.config.output_dir / "out.json")
                return {"example": data}
    """

    def __init__(self, config: ScrapeConfig) -> None:
        self.config = config
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        self._rate_limiter = RateLimiter(config.calls_per_second)
        self._session = self._build_session()
        self.logger = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Session setup
    # ------------------------------------------------------------------

    def _build_session(self) -> requests.Session:
        """Build a requests.Session with retry logic and a descriptive User-Agent."""
        session = requests.Session()
        retry = Retry(
            total=self.config.max_retries,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            respect_retry_after_header=True,
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers["User-Agent"] = "rotom-dex/1.0 (pokemon-rag-chatbot)"
        return session

    # ------------------------------------------------------------------
    # Cache path helpers
    # ------------------------------------------------------------------

    def _cache_path(self, url: str, suffix: str = ".json") -> Path:
        """
        Derive a filesystem-safe cache file path from a URL.

        Strips the scheme, replaces ``/`` with ``__``, and appends *suffix*.
        """
        safe = (
            url.split("://", 1)[-1]
            .strip("/")
            .replace("/", "__")
            .replace("?", "__q__")
            .replace("&", "__a__")
            .replace(":", "__c__")
        )
        # Truncate to avoid hitting OS filename length limits
        if len(safe) > 200:
            import hashlib

            safe = safe[:160] + "__" + hashlib.md5(safe.encode()).hexdigest()[:8]
        return self.config.cache_dir / f"{safe}{suffix}"

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def get_json(self, url: str, use_cache: bool = True) -> Optional[Any]:
        """
        Fetch *url* and return parsed JSON (dict or list).

        Uses a disk cache so repeated calls return the cached result without
        making an HTTP request.  Returns ``None`` on 404 or unrecoverable
        errors.

        Parameters
        ----------
        url : str
            Full URL to fetch.
        use_cache : bool
            Set to ``False`` to force a fresh HTTP request.
        """
        cache_file = self._cache_path(url, suffix=".json")

        if use_cache and cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError):
                self.logger.warning(f"Corrupt JSON cache at {cache_file} — re-fetching.")

        self._rate_limiter.wait()
        try:
            resp = self._session.get(url, timeout=self.config.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            if code == 404:
                self.logger.debug(f"404: {url}")
            else:
                self.logger.error(f"HTTP {code} fetching {url}: {exc}")
            return None
        except (requests.RequestException, ValueError) as exc:
            self.logger.error(f"Request / parse error for {url}: {exc}")
            return None

        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)

        return data

    def get_html(self, url: str, use_cache: bool = True) -> Optional[str]:
        """
        Fetch *url* and return the raw HTML as a string.

        Cached separately from JSON responses (uses ``.html`` extension).
        Returns ``None`` on 404 or unrecoverable errors.
        """
        cache_file = self._cache_path(url, suffix=".html")

        if use_cache and cache_file.exists():
            try:
                return cache_file.read_text(encoding="utf-8")
            except OSError:
                self.logger.warning(f"Unreadable HTML cache at {cache_file} — re-fetching.")

        self._rate_limiter.wait()
        try:
            resp = self._session.get(url, timeout=self.config.timeout)
            resp.raise_for_status()
            html = resp.text
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            if code == 404:
                self.logger.debug(f"404: {url}")
            else:
                self.logger.error(f"HTTP {code} fetching {url}: {exc}")
            return None
        except requests.RequestException as exc:
            self.logger.error(f"Request failed for {url}: {exc}")
            return None

        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(html, encoding="utf-8")
        return html

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def save_json(self, data: Any, path: Path) -> None:
        """Write *data* as indented JSON to *path* (creates parent dirs)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        self.logger.debug(f"Saved → {path}")

    def load_json(self, path: Path) -> Optional[Any]:
        """
        Load JSON from *path*.

        Returns ``None`` if the file is missing or contains invalid JSON
        rather than raising an exception — callers can treat ``None`` as
        "not yet scraped".
        """
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    # ------------------------------------------------------------------
    # Abstract contract
    # ------------------------------------------------------------------

    @abstractmethod
    def scrape_all(self) -> dict[str, Any]:
        """
        Run the complete scraping pipeline for this data source.

        Must save output files under ``self.config.output_dir`` and return
        a summary dict (e.g. ``{"pokemon": {...}, "gym_leaders": {...}}``).
        """
        ...
