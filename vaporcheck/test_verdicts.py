"""Regression for registry-response edge cases and the deprecated decision.

Two correctness bugs this locks down:
  1. npm returns HTTP 200 for UNPUBLISHED names (and security takedowns) — those
     must be not-found, not exists (else the gate green-lights malware-shaped names).
  2. A DEPRECATED package must NOT auto-approve the tool call — the hook emits
     additionalContext only, leaving the user's normal permission prompt intact.

_live_npm is exercised with a stubbed _get so the cases are deterministic and
offline (real unpublished packages are too unstable to depend on).
"""
import contextlib
import io
import json
import sys

import hook
import verifier

checks = []


def check(label, cond, detail=""):
    checks.append(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))


def with_get(payload):
    """Return a fake verifier._get that yields (status, data)."""
    return lambda url: payload


def main():
    real_get = verifier._get
    try:
        # --- npm response-shape logic (verifier._live_npm) ---
        verifier._get = with_get((404, None))
        check("404 -> not-found", verifier._live_npm("x").status == "not-found")

        verifier._get = with_get((200, {"name": "x", "time": {"unpublished": {"time": "..."}},
                                         "versions": {}}))
        check("200 unpublished -> not-found", verifier._live_npm("x").status == "not-found",
              verifier._live_npm("x").status)

        verifier._get = with_get((200, {"name": "x", "versions": {}}))
        check("200 no versions -> not-found", verifier._live_npm("x").status == "not-found")

        verifier._get = with_get((200, {"name": "x", "dist-tags": {"latest": "1.0.0"},
                                         "versions": {"1.0.0": {}}}))
        check("200 with a real version -> exists", verifier._live_npm("x").status == "exists")

        verifier._get = with_get((200, {"name": "x", "dist-tags": {"latest": "1.0.0"},
                                         "versions": {"1.0.0": {"deprecated": "security holding"}}}))
        check("200 deprecated latest -> deprecated", verifier._live_npm("x").status == "deprecated")
    finally:
        verifier._get = real_get

    # --- deprecated must not auto-approve (hook decision) ---
    real_verify = verifier.verify_npm
    verifier.verify_npm = lambda n: verifier.Verdict(n, "package:npm", "deprecated", n, "old")
    real_stdin = sys.stdin
    try:
        event = {"tool_name": "Bash", "tool_input": {"command": "npm install foo"}, "cwd": "."}
        sys.stdin = io.StringIO(json.dumps(event))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            hook.main()
        out = json.loads(buf.getvalue() or "{}").get("hookSpecificOutput", {})
    finally:
        verifier.verify_npm = real_verify
        sys.stdin = real_stdin
    check("deprecated does NOT emit permissionDecision (no auto-approve)",
          "permissionDecision" not in out, str(out))
    check("deprecated surfaces additionalContext warning", "additionalContext" in out, str(out))

    # --- a crash inside the gate must fail to ASK, never silently allow ---
    real_extract = hook.extract_identifiers
    hook.extract_identifiers = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    sys.stdin = io.StringIO(json.dumps({"tool_name": "Bash",
                                        "tool_input": {"command": "pip install x"}, "cwd": "."}))
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            hook.main()
        crash_out = json.loads(buf.getvalue() or "{}").get("hookSpecificOutput", {})
    finally:
        hook.extract_identifiers = real_extract
        sys.stdin = real_stdin
    check("internal crash -> ask (never silent allow)",
          crash_out.get("permissionDecision") == "ask", str(crash_out))

    print(f"\n{sum(checks)}/{len(checks)} verdict cases passed")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
