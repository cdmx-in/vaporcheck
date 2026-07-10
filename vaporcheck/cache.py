"""Shared SQLite cache + token-bucket rate limiter for the verifier.

stdlib only. The cache file is shared by BOTH the short-lived PreToolUse hook
processes and the long-running MCP server, so a result fetched by one is reused
by the other — an in-memory cache could not do this.

Status-aware TTLs double as false-positive protection:
  exists      -> long   (existence rarely changes)
  deprecated  -> medium
  not-found   -> SHORT  (a legitimately-new package may appear soon)
  cannot-verify -> never cached (transient)
"""
import os
import sqlite3
import tempfile
import time


def _default_cache_path():
    """A per-user cache location — never inside site-packages (read-only there)."""
    env = os.environ.get("VAPORCHECK_CACHE") or os.environ.get("VERIFY_CACHE")
    if env:
        return env
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    d = os.path.join(base, "vaporcheck")
    try:
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "cache.sqlite")
    except OSError:
        return os.path.join(tempfile.gettempdir(), "vaporcheck-cache.sqlite")


CACHE_PATH = _default_cache_path()

TTL = {
    "exists": 7 * 24 * 3600,
    "deprecated": 24 * 3600,
    "not-found": 600,            # 10 min — short on purpose
}

# token bucket for live registry fetches
RATE = 10.0          # tokens/sec refill
CAPACITY = 20.0      # burst
MAX_WAIT = 2.0       # never block a fetch longer than this


def _conn():
    c = sqlite3.connect(CACHE_PATH, timeout=5)
    c.execute("PRAGMA busy_timeout=3000")
    c.execute("PRAGMA journal_mode=WAL")         # concurrent hook + server without lock storms
    c.execute("CREATE TABLE IF NOT EXISTS cache ("
              "key TEXT PRIMARY KEY, kind TEXT, identifier TEXT, status TEXT, "
              "canonical TEXT, note TEXT, expires REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS bucket ("
              "id INTEGER PRIMARY KEY CHECK (id=1), tokens REAL, updated REAL)")
    return c


def _recover():
    """A corrupt cache file must not disable the gate — delete it so it rebuilds."""
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(CACHE_PATH + suffix)
        except OSError:
            pass


def _key(kind, value):
    return f"{kind}\x00{value}"


def get(kind, value):
    """Return a dict {identifier,status,canonical,note} if a fresh hit, else None.

    A cache miss and a cache failure look the same to the caller (None) — the
    verifier just does a live lookup. The gate never fails because the cache does.
    """
    now = time.time()
    try:
        with _conn() as c:
            row = c.execute(
                "SELECT identifier,status,canonical,note,expires FROM cache WHERE key=?",
                (_key(kind, value),)).fetchone()
            if not row:
                return None
            ident, status, canonical, note, expires = row
            if expires < now:
                c.execute("DELETE FROM cache WHERE key=?", (_key(kind, value),))
                return None
            return {"identifier": ident, "status": status,
                    "canonical": canonical or None, "note": note or ""}
    except (sqlite3.Error, OSError):
        _recover()
        return None


def put(kind, identifier, status, canonical, note):
    ttl = TTL.get(status)
    if ttl is None:
        return                                   # don't cache cannot-verify
    try:
        with _conn() as c:
            c.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?,?,?)",
                      (_key(kind, identifier), kind, identifier, status,
                       canonical or "", note or "", time.time() + ttl))
    except (sqlite3.Error, OSError):
        _recover()                               # best-effort; a failed write is not fatal


def throttle():
    """Consume one token before a live fetch; sleep briefly if the bucket is dry."""
    now = time.time()
    wait = 0.0
    try:
        with _conn() as c:
            row = c.execute("SELECT tokens,updated FROM bucket WHERE id=1").fetchone()
            tokens, updated = (row if row else (CAPACITY, now))
            tokens = min(CAPACITY, tokens + (now - updated) * RATE)
            if tokens < 1.0:
                wait = min(MAX_WAIT, (1.0 - tokens) / RATE)
                tokens += wait * RATE
            tokens -= 1.0
            c.execute("INSERT OR REPLACE INTO bucket (id,tokens,updated) VALUES (1,?,?)",
                      (tokens, now + wait))
    except (sqlite3.Error, OSError):
        return                                   # throttling is best-effort, never a hard failure
    if wait:
        time.sleep(wait)


# --- helpers for tests / inspection ---
def peek(kind, value):
    with _conn() as c:
        row = c.execute("SELECT status,expires FROM cache WHERE key=?",
                        (_key(kind, value),)).fetchone()
    return {"status": row[0], "expires": row[1]} if row else None


def clear():
    with _conn() as c:
        c.execute("DELETE FROM cache")
        c.execute("DELETE FROM bucket")
