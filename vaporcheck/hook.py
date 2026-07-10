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
import os
import re
import shlex
import sys
import time
from concurrent.futures import ThreadPoolExecutor

try:
    from . import verifier  # installed package
except ImportError:
    import verifier  # run as a plain script from the source tree

# overall budget for verifying one tool call — kept under the hook's own timeout
# (Claude Code fail-OPENS if the hook times out, so we must finish first).
DEADLINE_S = 12.0

# strip version pins / extras: requests==2.0, requests>=2, pkg[extra], left@1.2.3
_VERSION_SPLIT = re.compile(r"[=<>!~\[]|@(?=[\d^~v])")
# a plausible registry package name (must contain a letter; excludes bare numbers like "2")
_VALID_NAME = re.compile(r"^@?[A-Za-z0-9._/-]+$")
# control operators that separate one command from the next
_CONTROL = {";", "|", "||", "&&", "&", "(", ")", "|&", "\n"}
# install options that consume the FOLLOWING token as a value (so it is not a package)
_OPT_WITH_VALUE = {
    "-r", "--requirement", "-i", "--index-url", "--extra-index-url", "-c",
    "--constraint", "-f", "--find-links", "--proxy", "--python", "--prefix",
    "--target", "-t", "--root", "--platform", "--abi", "--implementation",
    "--registry", "--save-exact",
}
# a custom package index means we cannot verify names against the public registry
_PRIVATE_INDEX = {"-i", "--index-url", "--extra-index-url", "--registry"}
# manifest files whose contents route through the same resolvers
_REQ_FLAGS = {"-r", "--requirement"}
# command prefixes to skip before the real command (sudo pip …, VAR=x npm …)
_PREFIX_CMDS = {"sudo", "env", "nice", "time", "exec"}
_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# interpreter/tool basenames, version-suffixed (pip3.12, python3.11)
_PIP_RE = re.compile(r"^pip[0-9.]*$")
_PY_RE = re.compile(r"^python[0-9.]*$")
# legacy fallback patterns (used only if shell tokenization fails)
_PY_INSTALL = re.compile(r"\b(?:pip[0-9.]*|pipx|uv(?:\s+pip)?|python[0-9.]*\s+-m\s+pip)\s+install\b", re.I)
_NPM_INSTALL = re.compile(r"\b(?:npm\s+(?:i|install|add)|yarn\s+add|pnpm\s+add|bun\s+add)\b", re.I)


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


def _strip_prefixes(seg):
    """Drop leading sudo/env/nice wrappers and VAR=value assignments."""
    i, skipped = 0, False
    while i < len(seg):
        tok = seg[i]
        if tok in _PREFIX_CMDS or _ASSIGN.match(tok):
            skipped = True; i += 1; continue
        if skipped and tok.startswith("-"):             # flags belonging to sudo/env
            i += 1; continue
        break
    return seg[i:]


def _norm(tok):
    """Basename, lowercased, no .exe — so /usr/bin/pip3.12 and PIP.EXE normalize."""
    base = tok.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return base[:-4] if base.endswith(".exe") else base


def _classify(seg):
    """Return (ecosystem, args, mode, manifest) or None.

    args     = the token list AFTER the install verb
    mode     = 'all'   -> every arg may be a package (installers)
               'first' -> only the first package (one-off executors: npx/uvx/…)
    manifest = 'package.json' if a bare install of it should be read, else None
    """
    t = _strip_prefixes(seg)
    if not t:
        return None
    f = _norm(t[0])

    # python -m pip install …  (also `py -3 -m pip install`, python3.11, …)
    if f == "py" or f == "python" or _PY_RE.match(f):
        idx = 1
        while idx < len(t) and t[idx].startswith("-") and t[idx] != "-m":
            idx += 1
        if idx + 2 < len(t) and t[idx] == "-m" and t[idx + 1] == "pip" and t[idx + 2] == "install":
            return ("pypi", t[idx + 3:], "all", None)
        return None

    # pip / pip3 / pip3.12 / pipx
    if f == "pipx":
        if len(t) >= 2 and t[1] == "install":
            return ("pypi", t[2:], "all", None)
        if len(t) >= 2 and t[1] == "run":
            return ("pypi", t[2:], "first", None)
        return None
    if f == "pip" or _PIP_RE.match(f):
        if len(t) >= 2 and t[1] == "install":
            return ("pypi", t[2:], "all", None)
        return None

    # uv / uvx
    if f == "uv":
        if len(t) >= 3 and t[1] == "pip" and t[2] == "install":
            return ("pypi", t[3:], "all", None)
        if len(t) >= 2 and t[1] == "add":
            return ("pypi", t[2:], "all", None)
        return None
    if f == "uvx":
        return ("pypi", t[1:], "first", None)

    # poetry / pdm / pipenv
    if f == "poetry" and len(t) >= 2 and t[1] == "add":
        return ("pypi", t[2:], "all", None)
    if f == "pdm" and len(t) >= 2 and t[1] == "add":
        return ("pypi", t[2:], "all", None)
    if f == "pipenv" and len(t) >= 2 and t[1] == "install":
        return ("pypi", t[2:], "all", None)

    # npm / yarn / pnpm / bun
    if f == "npm" and len(t) >= 2 and t[1] in ("install", "i", "add"):
        return ("npm", t[2:], "all", "package.json" if t[1] != "add" else None)
    if f == "yarn":
        if len(t) >= 2 and t[1] == "add":
            return ("npm", t[2:], "all", None)
        if len(t) >= 2 and t[1] == "dlx":
            return ("npm", t[2:], "first", None)
        return None
    if f == "pnpm":
        if len(t) >= 2 and t[1] in ("add", "install", "i"):
            return ("npm", t[2:], "all", "package.json" if t[1] != "add" else None)
        if len(t) >= 2 and t[1] == "dlx":
            return ("npm", t[2:], "first", None)
        return None
    if f == "bun":
        if len(t) >= 2 and t[1] == "add":
            return ("npm", t[2:], "all", None)
        if len(t) >= 2 and t[1] in ("install", "i"):
            return ("npm", t[2:], "all", "package.json")
        return None

    # one-off executors: download-AND-run (strictly worse than install)
    if f == "npx" or f == "bunx":
        return ("npm", t[1:], "first", None)

    return None


def _parse_requirements(path: str):
    """Extract package names from a pip requirements file (best-effort)."""
    names = []
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return names                                    # unreadable -> nothing to gate here
    for raw in lines:
        line = raw.split("#", 1)[0].strip()             # drop comments
        if not line or line.startswith("-"):            # blank / -e / -r / --flag
            continue
        line = line.split(";", 1)[0].strip()            # drop env markers
        parts = line.split()
        if parts:
            name = _is_pkg(parts[0])
            if name:
                names.append(name)
    return names


def _parse_package_json(path: str):
    """Extract dependency names from a package.json (all dependency sections)."""
    names = []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return names
    if not isinstance(data, dict):
        return names
    for field in ("dependencies", "devDependencies",
                  "optionalDependencies", "peerDependencies"):
        deps = data.get(field)
        if isinstance(deps, dict):
            for nm in deps:
                name = _is_pkg(nm)
                if name:
                    names.append(name)
    return names


def find_install_invocations(cmd: str, cwd: str = ""):
    """Shell-aware: only genuine install COMMANDS yield packages.

    Install strings that appear as DATA (quoted args, heredoc bodies, grep
    patterns) are ignored, because the install verb is not at a command
    position. This is the fix for the live-dogfooding false-positive where a
    command that merely *contained* an install string got blocked.

    Beyond explicit package args, this also expands manifest installs:
    `pip install -r requirements.txt` reads the file, and a bare `npm install`
    reads package.json — so the common "write a manifest, then install it" flow
    is gated rather than bypassed.
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
    base = cwd or os.getcwd()
    found = []
    for seg in segs:
        c = _classify(seg)
        if not c:
            continue
        eco, args, mode, manifest = c
        if any(a in _PRIVATE_INDEX for a in args):
            continue                                    # custom index: can't verify publicly, don't false-deny
        req_files, got_pkg, i = [], False, 0
        while i < len(args):
            tok = args[i]
            if "<" in tok or ">" in tok:                # redirect => end of args
                break
            if eco == "pypi" and tok in _REQ_FLAGS and i + 1 < len(args):
                req_files.append(args[i + 1]); i += 2; continue
            if tok in _OPT_WITH_VALUE:                  # option + its value: skip both
                i += 2; continue
            if tok.startswith("-"):                     # boolean flag
                i += 1; continue
            name = _is_pkg(tok)
            if name:
                found.append((eco, name)); got_pkg = True
                if mode == "first":                     # executor: only the run target is a package
                    break
            i += 1
        for rf in req_files:
            path = rf if os.path.isabs(rf) else os.path.join(base, rf)
            found.extend(("pypi", n) for n in _parse_requirements(path))
        if manifest == "package.json" and not got_pkg:
            found.extend(("npm", n) for n in _parse_package_json(os.path.join(base, "package.json")))
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


def extract_identifiers(tool_name: str, tool_input: dict, cwd: str = ""):
    """Return list of (kind, identifier) for the actual tool call."""
    work = []
    if tool_name == "Bash":
        cmd = tool_input.get("command", "") or ""
        work.extend(find_install_invocations(cmd, cwd))
    elif tool_name == "Edit":
        # Editing a file that does not exist is a hallucinated-path failure.
        fp = tool_input.get("file_path")
        if fp:
            work.append(("path", fp))
    # Write is intentionally skipped: a new file legitimately does not exist yet.
    return work


def run(kind, ident, cwd):
    if kind == "pypi":
        return verifier.verify_pypi(ident)
    if kind == "npm":
        return verifier.verify_npm(ident)
    if kind == "path":
        return verifier.verify_path(ident, cwd)
    return None


def verify_all(work, cwd):
    """Verify every (kind, ident) concurrently within one overall deadline.

    Anything not resolved in time becomes cannot-verify -> the hook asks a human,
    rather than letting the whole call slip past a hard timeout (fail-open)."""
    verdicts = []
    deadline = time.monotonic() + DEADLINE_S
    with ThreadPoolExecutor(max_workers=min(8, len(work))) as ex:
        futs = [(ex.submit(run, kind, ident, cwd), kind, ident) for kind, ident in work]
        for fut, kind, ident in futs:
            try:
                v = fut.result(timeout=max(0.1, deadline - time.monotonic()))
            except Exception:
                v = verifier.Verdict(ident, kind, "cannot-verify", note="verification timed out")
            if v:
                verdicts.append(v)
    return verdicts


def _main() -> int:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return 0  # not our concern; let the call proceed
    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {}) or {}
    cwd = event.get("cwd", "")

    work = extract_identifiers(tool_name, tool_input, cwd)
    if not work:
        return 0  # nothing to verify -> allow normal flow

    verdicts = verify_all(work, cwd)
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
        # Surface a warning WITHOUT auto-approving: emit additionalContext only,
        # no permissionDecision, so the user's normal permission prompt still
        # applies. (Emitting "allow" here would give deprecated installs LESS
        # friction than healthy ones — the opposite of the intent.)
        warn = "; ".join(f"{v.identifier} is DEPRECATED ({v.note})" for v in deprecated)
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": f"vaporcheck: {warn}. Prefer a maintained alternative.",
        }}))
        return 0

    return 0  # all verified exists -> allow normal flow


def main() -> int:
    # Non-ASCII paths arrive mojibake'd if the pipe defaults to cp1252 (Windows);
    # force UTF-8 so we don't false-deny a valid path we merely mis-decoded.
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        return _main()
    except Exception as e:
        # A bug in the gate must never silently fail OPEN — surface to a human.
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": f"vaporcheck internal error ({type(e).__name__}); verify manually.",
        }}))
        return 0


if __name__ == "__main__":
    sys.exit(main())
