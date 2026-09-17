"""Bounded retries for transient Gemini failures, sharing the caller's time budget."""

import json
import random
import time
import urllib.error
import urllib.request


def post_json(request, *, timeout_s: float, opener=None):
    deadline = time.monotonic() + timeout_s
    opener = opener or urllib.request.urlopen
    for attempt in range(3):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Provider time budget exhausted")
        try:
            with opener(request, timeout=remaining) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code not in {500, 502, 503, 504} or attempt == 2:
                raise
            delay = 2**attempt + random.uniform(0, 0.25)
            remaining = deadline - time.monotonic()
            if remaining <= delay:
                raise
            exc.close()
            time.sleep(delay)
