"""
Batch processing — Rate limiting + response caching.

Handles rate limits for API models and caches responses
to avoid re-running expensive calls.
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass


@dataclass
class CachedResponse:
    """A cached LLM response."""
    model_id: str
    prompt_hash: str
    response: str
    timestamp: float


class ResponseCache:
    """Simple file-based response cache."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _hash_key(self, model_id: str, prompt: str, mode: str) -> str:
        """Create a deterministic hash for a (model, prompt, mode) triple."""
        key = f"{model_id}|{mode}|{prompt}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def get(self, model_id: str, prompt: str, mode: str) -> Optional[str]:
        """Get a cached response, or None if not cached."""
        h = self._hash_key(model_id, prompt, mode)
        cache_file = self.cache_dir / f"{h}.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text())
            return data.get("response")
        return None

    def put(self, model_id: str, prompt: str, mode: str, response: str):
        """Cache a response."""
        h = self._hash_key(model_id, prompt, mode)
        cache_file = self.cache_dir / f"{h}.json"
        data = {
            "model_id": model_id,
            "mode": mode,
            "prompt_hash": h,
            "response": response,
            "timestamp": time.time(),
        }
        cache_file.write_text(json.dumps(data))

    def clear(self):
        """Clear all cached responses."""
        for f in self.cache_dir.glob("*.json"):
            f.unlink()

    @property
    def size(self) -> int:
        """Number of cached responses."""
        return len(list(self.cache_dir.glob("*.json")))


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, rpm: int = 0):
        """
        Args:
            rpm: Requests per minute. 0 = unlimited.
        """
        self.rpm = rpm
        self._timestamps: list[float] = []

    def wait_if_needed(self):
        """Block until we're within rate limits."""
        if self.rpm <= 0:
            return

        now = time.time()
        # Remove timestamps older than 60 seconds
        self._timestamps = [t for t in self._timestamps if now - t < 60]

        if len(self._timestamps) >= self.rpm:
            # Wait until the oldest timestamp falls out of the window
            sleep_time = 60 - (now - self._timestamps[0]) + 0.1
            if sleep_time > 0:
                time.sleep(sleep_time)

        self._timestamps.append(time.time())
