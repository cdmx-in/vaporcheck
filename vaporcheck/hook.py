"""PreToolUse hook: fail-closed identifier existence gate.

Reads the exact JSON Claude Code pipes to a PreToolUse hook on stdin,
extracts identifiers from the *actual tool call* (package names from a
Bash install command; the file_path from an Edit), verifies existence
against an authoritative registry/filesystem, and DENIES the call if a
referent does not exist.

Output contract (current Claude Code standard):
  - deny:  print hookSpecificOutput.permissionDecision="deny" + reason, exit 0
  - ask:   used for cannot-verify (graceful degradation, no false block)
  - allow: emit nothing, exit 0 -> normal permission flow proceeds
"""
from __future__ import annotations

import json
import re
import shlex
import sys

import verifier

# strip version pins / extras: requests==2.0, requests>=2, pkg[extra], left@1.2.3
_VERSION_SPLIT = re.compile(r"[=<>!~\[]|@(?=[\d^~v])")
# a plausible registry package name (must contain a letter; excludes bare numbers like "2")
_VALID_NAME = re.compile(r"^@?[A-Za-z0-9._/-]+$")
# control operators that separate one command from the next
_CONTROL = {";", "|", "||", "&&", "&", "(", ")", "|&", "\n"}
# legacy fallback patterns (used only if shell tokenization fails)
_PY_INSTALL = re.compile(r"\b(?:pip3?|pipx|uv(?:\s+pip)?|python3?\s+-m\s+pip)\s+install\b", re.I)
_NPM_INSTALL = re.compile(r"\b(?:npm\s+(?:i|install|add)|yarn\s+add|pnpm\s+add)\b", re.I)


def _strip_heredocs(cmd: str) -> str:
    """Remove heredoc bodies so install strings used as DATA aren't scanned."""
    pat = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")
    out = cmd
    while True:
        m = pat.search(out)
        if not m:
            return out
        delim = m.group(2)
        body = out[m.end():]
        em = re.search(r"\n[ \t]*" + re.escape(delim) + r"\b", body)
        out = out[:m.start()] + " " + (body[em.end():] if em else "")
        if not em:
            return out


def _is_pkg(tok: str):
    """Return a clean package name if tok looks like a registry package, else None."""
    if tok.startswith("-"):
        return None                                    # flag
    if "\\" in tok or tok.startswith(".") or tok.endswith((".txt", ".whl", ".tar.gz")):
        return None                                    # local path / requirements file
    if "/" in tok and not tok.startswith("@"):
        return None                                    # local path (keep @scope/pkg)
    name = _VERSION_SPLIT.split(tok)[0].strip()
    if name and re.search(r"[A-Za-z]", name) and _VALID_NAME.match(name):
        return name
    return None


def _classify(seg):
    """Map a command's leading tokens to (ecosystem, arg_start_index) or None."""
    t = seg
    if len(t) >= 4 and t[0] in ("python", "python3") and t[1] == "-m" and t[2] == "pip" and t[3] == "install":
        return ("pypi", 4)
    if len(t) >= 3 and t[0] == "uv" and t[1] == "pip" and t[2] == "install":
        return ("pypi", 3)
    if len(t) >= 2 and t[0] in ("pip", "pip3", "pipx") and t[1] == "install":
        return ("pypi", 2)
    if len(t) >= 2 and t[0] == "uv" and t[1] == "add":
        return ("pypi", 2)
    if len(t) >= 2 and t[0] == "npm" and t[1] in ("install", "i", "add"):
        return ("npm", 2)
    if len(t) >= 2 and t[0] in ("yarn", "pnpm") and t[1] in ("add", "install"):
        return ("npm", 2)
    return None


def find_install_invocations(cmd: str):
    """Shell-aware: only genuine install COMMANDS yield packages.

    Install strings that appear as DATA (quoted args, heredoc bodies, grep
    patterns) are ignored, because the install verb is not at a command
    position. This is the fix for the live-dogfooding false-positive where a
    command that merely *contained* an install string got blocked.
    """
    cmd = _strip_heredocs(cmd)
    try:
        lx = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lx.whitespace_split = True
        tokens = list(lx)
    except ValueError:
        return _legacy_scan(cmd)                        # unbalanced quotes, etc.
    segs, seg = [], []
    for tok in tokens:
        if tok in _CONTROL:
            if seg:
                segs.append(seg); seg = []
        else:
            seg.append(tok)
    if seg:
        segs.append(seg)
    found = []
    for seg in segs:
        c = _classify(seg)
        if not c:
            continue
        eco, start = c
        for tok in seg[start:]:
            if "<" in tok or ">" in tok:               # redirect => end of args
                break
            name = _is_pkg(tok)
            if name:
                found.append((eco, name))
    return found


def _legacy_scan(cmd: str):
    """Regex fallback used only when shell tokenization fails."""
    found = []
    for anchor, eco in ((_PY_INSTALL, "pypi"), (_NPM_INSTALL, "npm")):
        m = anchor.search(cmd)
        if not m:
            continue
        for tok in cmd[m.end():].split():
            if tok in ("&&", "||", ";", "|") or re.match(r"^(?:\d*[<>|&]|;)", tok):
                break
            name = _is_pkg(tok)
            if name:
                found.append((eco, name))
    return found


def extract_identifiers(tool_name: str, tool_input: dict):
    """Return list of (verify_fn, *args, label) for the actual tool call."""
    work = []
    if tool_name == "Bash":
        cmd = tool_input.get("command", "") or ""
        work.extend(find_install_invocations(cmd))
    elif tool_name == "Edit":
        # Editing a file that does not exist is a hallucinated-path failure.
        fp = tool_input.get("file_path")
        if fp:
            work.append(("path", fp))
    # Write is intentionally skipped: a new file legitimately does not exist yet.
    return work


def run(verify_one, kind, ident, cwd):
    if kind == "pypi":
        return verifier.verify_pypi(ident)
    if kind == "npm":
        return verifier.verify_npm(ident)
    if kind == "path":
        return verifier.verify_path(ident, cwd)
    return None


def main() -> int:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return 0  # not our concern; let the call proceed
    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {}) or {}
    cwd = event.get("cwd", "")

    work = extract_identifiers(tool_name, tool_input)
    if not work:
        return 0  # nothing to verify -> allow normal flow

    verdicts = [run(None, kind, ident, cwd) for (kind, ident) in work]
    not_found = [v for v in verdicts if v and v.status == "not-found"]
    deprecated = [v for v in verdicts if v and v.status == "deprecated"]
    unverifiable = [v for v in verdicts if v and v.status == "cannot-verify"]

    if not_found:
        reason = (
            "Identifier existence gate BLOCKED this call. The following do not exist "
            "in their authoritative source:\n"
            + "\n".join(f"  - {v.identifier} ({v.kind}): NOT FOUND ({v.note})" for v in not_found)
            + "\nDo not proceed. Re-check the exact name/path (likely a hallucinated "
              "or slop-squatted identifier) and use a verified one."
        )
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}))
        return 0

    if unverifiable:
        # graceful degradation: don't hard-block on a network failure -> ask a human
        reason = ("Identifier gate could not verify: "
                  + ", ".join(f"{v.identifier} ({v.note})" for v in unverifiable)
                  + ". Confirm manually before proceeding.")
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }}))
        return 0

    if deprecated:
        # allow but surface a warning the model can see (additionalContext)
        warn = "; ".join(f"{v.identifier} is DEPRECATED ({v.note})" for v in deprecated)
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": f"Verified, with warning: {warn}",
        }}))
        return 0

    return 0  # all verified exists -> allow normal flow


if __name__ == "__main__":
    sys.exit(main())
