"""Identifier existence-verifier — core resolvers.

Each resolver answers one question against an authoritative source:
"does this referent exist?" -> exists | not-found | deprecated | cannot-verify

This is the deterministic half of the project. It has no opinion about
enforcement; hook.py decides what to do with a verdict.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

try:
    from . import cache  # installed package
except ImportError:
    import cache  # run as a plain script from the source tree

TIMEOUT_S = 8
_UA = {"User-Agent": "vaporcheck/0.1"}


@dataclass
class Verdict:
    identifier: str
    kind: str                 # package:pypi | package:npm | path
    status: str               # exists | not-found | deprecated | cannot-verify
    canonical: Optional[str] = None
    note: str = ""
    cached: bool = False

    def as_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "kind": self.kind,
            "status": self.status,
            "canonical": self.canonical,
            "note": self.note,
            "cached": self.cached,
        }


def _get(url: str):
    """Return (http_status, parsed_json_or_None). Raises on network failure."""
    req = urllib.request.Request(url, headers=_UA, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            body = r.read()
            try:
                return r.status, json.loads(body)
            except json.JSONDecodeError:
                return r.status, None
    except urllib.error.HTTPError as e:
        return e.code, None


def verify_pypi(name: str) -> Verdict:
    hit = cache.get("package:pypi", name)
    if hit:
        return Verdict(hit["identifier"], "package:pypi", hit["status"],
                       hit["canonical"], hit["note"], cached=True)
    cache.throttle()
    v = _live_pypi(name)
    if v.status != "cannot-verify":
        cache.put("package:pypi", v.identifier, v.status, v.canonical, v.note)
    return v


def _live_pypi(name: str) -> Verdict:
    try:
        status, data = _get(f"https://pypi.org/pypi/{urllib.parse.quote(name)}/json")
    except Exception as e:  # network/DNS/timeout -> cannot-verify (fail-open policy lives in hook)
        return Verdict(name, "package:pypi", "cannot-verify", note=f"{type(e).__name__}")
    if status == 404:
        return Verdict(name, "package:pypi", "not-found")
    if status == 200 and data:
        info = data.get("info", {})
        canonical = info.get("name", name)
        # all releases yanked => effectively gone
        releases = data.get("releases", {})
        if releases and all(
            all(f.get("yanked") for f in files) for files in releases.values() if files
        ):
            return Verdict(name, "package:pypi", "deprecated", canonical, "all releases yanked")
        return Verdict(name, "package:pypi", "exists", canonical)
    return Verdict(name, "package:pypi", "cannot-verify", note=f"http {status}")


def verify_npm(name: str) -> Verdict:
    hit = cache.get("package:npm", name)
    if hit:
        return Verdict(hit["identifier"], "package:npm", hit["status"],
                       hit["canonical"], hit["note"], cached=True)
    cache.throttle()
    v = _live_npm(name)
    if v.status != "cannot-verify":
        cache.put("package:npm", v.identifier, v.status, v.canonical, v.note)
    return v


def _live_npm(name: str) -> Verdict:
    try:
        status, data = _get(f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='@/')}")
    except Exception as e:
        return Verdict(name, "package:npm", "cannot-verify", note=f"{type(e).__name__}")
    if status == 404:
        return Verdict(name, "package:npm", "not-found")
    if status == 200 and data:
        versions = data.get("versions") or {}
        # npm returns 200 for UNPUBLISHED names too (body carries time.unpublished
        # and no live versions). Treating that as "exists" would green-light the
        # exact malware-shaped names this tool exists to catch — so it's not-found.
        if not versions or data.get("time", {}).get("unpublished"):
            return Verdict(name, "package:npm", "not-found", note="unpublished")
        latest = data.get("dist-tags", {}).get("latest")
        if latest and versions.get(latest, {}).get("deprecated"):
            return Verdict(name, "package:npm", "deprecated", name,
                           str(versions[latest]["deprecated"])[:120])
        return Verdict(name, "package:npm", "exists", name)
    return Verdict(name, "package:npm", "cannot-verify", note=f"http {status}")


def verify_path(path: str, cwd: str = "") -> Verdict:
    target = path if os.path.isabs(path) else os.path.join(cwd or os.getcwd(), path)
    if os.path.exists(target):
        return Verdict(path, "path", "exists", os.path.abspath(target))
    return Verdict(path, "path", "not-found", note="no such file or directory")
