"""
key_pool.py: a small, explicit pool of Groq API keys for long, resumable runs.

Keys are read from the environment (loaded from .env by the caller) as GROQ_API_KEY,
GROQ_API_KEY_2, ... and used IN ORDER. The pool advances to the next key only when the
current one is out of daily quota or is rejected; a per-minute throttle is NOT a reason to
switch (the caller waits and retries on the same key). When every key is spent the pool
reports it and the run stops with its checkpoint intact, to be resumed later.

Only variable NAMES are ever printed or stored; key values never leave this object.
"""
from __future__ import annotations

import os
from typing import Mapping

NAMES = ["GROQ_API_KEY"] + [f"GROQ_API_KEY_{i}" for i in range(2, 21)]


def classify_error(message: str) -> str:
    """Map an error message to what the caller should do about it."""
    m = (message or "").lower()
    if "invalid api key" in m or "invalid_api_key" in m or "error code: 401" in m:
        return "invalid"
    if "413" in m or "request too large" in m or "request_too_large" in m:
        return "too_large"           # a single request over the model's limit: rotation cannot fix it
    if "429" in m or "rate limit" in m or "rate_limit" in m:
        if "per day" in m or "tokens per day" in m or "tpd" in m or "requests per day" in m or "rpd" in m:
            return "daily_cap"
        return "rate_minute"         # per-minute throttle: wait and retry the same key
    return "other"


class KeyPool:
    def __init__(self, env: Mapping[str, str] | None = None):
        env = os.environ if env is None else env
        self._items = [(n, env[n].strip()) for n in NAMES if env.get(n, "").strip()]
        self._spent: dict[str, str] = {}      # name -> reason
        self._i = 0

    def __len__(self) -> int:
        return len(self._items)

    @property
    def names(self) -> list[str]:
        return [n for n, _ in self._items]

    @property
    def exhausted(self) -> bool:
        return all(n in self._spent for n, _ in self._items)

    def current(self) -> tuple[str, str]:
        """(name, key) of the key to use now. Raises if none is left."""
        for _ in range(len(self._items)):
            name, key = self._items[self._i % len(self._items)]
            if name not in self._spent:
                return name, key
            self._i += 1
        raise RuntimeError("all keys are spent")

    def retire(self, reason: str) -> str | None:
        """Mark the current key spent (reason: 'daily_cap' or 'invalid'); return the next key's NAME or None."""
        name, _ = self.current()
        self._spent[name] = reason
        self._i += 1
        return None if self.exhausted else self.current()[0]

    def status(self) -> str:
        parts = [f"{n}={'spent:' + self._spent[n] if n in self._spent else 'ok'}" for n, _ in self._items]
        return ", ".join(parts) if parts else "no keys set"
