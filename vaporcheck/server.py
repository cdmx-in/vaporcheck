"""vaporcheck — a dependency-free MCP server for identifier existence verification.

Transport: stdio, JSON-RPC 2.0, newline-delimited (one JSON object per line).
Stdlib only — no SDK, no install. Reuses the resolvers in verifier.py.

Exposes one tool:
  verify_identifier(kind, value, cwd?) ->
      { identifier, kind, status: exists|not-found|deprecated|cannot-verify, canonical, note }

This is the agent-callable half of the architecture (advisory on its own).
Paired with the PreToolUse hook it becomes fail-closed; standalone it lets any
MCP client ask "does this referent actually exist?" before relying on it.
"""
import json
import sys

import verifier

SERVER_NAME = "vaporcheck"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL = "2025-06-18"

TOOLS = [{
    "name": "verify_identifier",
    "description": (
        "Check whether a model-emitted identifier actually EXISTS in its authoritative "
        "source, before you rely on it. Call this before recommending or installing a "
        "package, or before editing a file path, to catch hallucinated or slop-squatted "
        "identifiers. Returns exists / not-found / deprecated / cannot-verify."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["pypi", "npm", "path"],
                     "description": "identifier class: pypi package, npm package, or filesystem path"},
            "value": {"type": "string", "description": "the identifier to verify (package name or path)"},
            "cwd": {"type": "string", "description": "base dir for relative paths when kind=path"},
        },
        "required": ["kind", "value"],
        "additionalProperties": False,
    },
}]


def _ok(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def _verify(kind, value, cwd=""):
    if kind == "pypi":
        return verifier.verify_pypi(value)
    if kind == "npm":
        return verifier.verify_npm(value)
    if kind == "path":
        return verifier.verify_path(value, cwd)
    raise ValueError(f"unknown kind: {kind!r} (expected pypi | npm | path)")


def handle(req):
    """Return a JSON-RPC response dict, or None for notifications / no-reply."""
    method = req.get("method")
    rid = req.get("id")

    if method == "initialize":
        proto = (req.get("params") or {}).get("protocolVersion") or DEFAULT_PROTOCOL
        return _ok(rid, {
            "protocolVersion": proto,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })

    if method == "notifications/initialized":
        return None
    if method == "ping":
        return _ok(rid, {})

    if method == "tools/list":
        return _ok(rid, {"tools": TOOLS})

    if method == "tools/call":
        params = req.get("params") or {}
        if params.get("name") != "verify_identifier":
            return _err(rid, -32602, f"unknown tool: {params.get('name')!r}")
        args = params.get("arguments") or {}
        try:
            v = _verify(args.get("kind"), args.get("value"), args.get("cwd", "") or "")
        except Exception as e:
            return _err(rid, -32602, str(e))
        payload = v.as_dict()
        text = f"{payload['identifier']} ({payload['kind']}): {payload['status'].upper()}"
        if payload.get("canonical"):
            text += f" -> {payload['canonical']}"
        if payload.get("note"):
            text += f"  [{payload['note']}]"
        return _ok(rid, {
            "content": [{"type": "text", "text": text}],
            "structuredContent": payload,
            "isError": False,
        })

    if rid is not None:
        return _err(rid, -32601, f"method not found: {method}")
    return None


def main():
    # stdout is reserved for JSON-RPC; anything else must go to stderr.
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
