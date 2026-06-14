# Spike: Can the identifier-verifier enforce FAIL-CLOSED? — FINDINGS

**Date:** 2026-06-14 · **Question:** Can a Claude Code `PreToolUse` hook + verifier actually *block* an agent from acting on an unverified identifier (fail-closed), or only advise it? This was the single load-bearing risk from the evidence check.

## Verdict: YES — fail-closed enforcement is real, at the tool boundary.

Proven end-to-end against the exact hook contract (real stdin/stdout, real subprocess, real PyPI/npm lookups — no mocks):

```
10/10 harness cases passed
  pip install <real>           -> allow      pip install <slopsquat>      -> DENY
  npm install <real>           -> allow      npm install <fake>           -> DENY
  pip install <pinned> <real>  -> allow      pip install <real> <bogus>   -> DENY
  plain bash (no identifier)   -> allow      Edit <existing path>         -> allow
  Edit <nonexistent path>      -> DENY       Write <new file>             -> allow
+ network-down                 -> ask (graceful, no false block)
+ npm 'request'                -> deprecated (richer than exists/not-found)
+ latency                      -> ~180-300ms per uncached registry check
```

The deny is a hard `permissionDecision: "deny"` with a `permissionDecisionReason` that is surfaced to the model — a real block plus a self-correction signal, not advice.

## What this answers

- **Fail-closed works without model cooperation.** The hook intercepts the *actual tool call* and denies it before execution. The agent cannot talk past it.
- **The false-positive risk is manageable.** A registry/network failure degrades to `ask` (human confirm), never a false `deny`. Legitimately-new identifiers would need the same `ask` + a grace window — designed-for, not a blocker.
- **The verdict is richer than a binary.** `exists / not-found / deprecated / cannot-verify` all demonstrated.

## The honest boundary (confirms the evidence-check memo)

A `PreToolUse` hook sees **tool inputs, not generated text.** Therefore:

| Identifier class | Enforceable fail-closed today? | Where it's caught |
|---|---|---|
| Package name | ✅ yes | the `Bash` install call |
| File path | ✅ yes | the `Edit` call |
| Tool name / API symbol *inside written code* | ⚠️ deferred | only when it hits a tool (the `Edit` that writes it, or a later build/test run) — **not at token-emission time** |

So "fail-closed" is honest for the install/edit boundary. API-symbol/tool-name verification is still valuable but lands as: verify-on-write (gate the `Edit`/`Write` that introduces the symbol) or verify-on-run, not as mid-sentence interception.

## The architecture this de-risks

Two parts, and **both are required** for the headline:
1. **Verifier (resolver core)** — ships as the **MCP** (agent-callable: "is this real?" returns `exists/not-found/deprecated/canonical`). On its own it is *advisory* — the model can ignore it.
2. **`PreToolUse` hook (enforcement wrapper)** — what makes it *fail-closed*. Wraps the same resolvers and denies the call.

Positioning that follows: **fail-closed in Claude Code (and any hook/MCP-gateway-capable harness); advisory in pure-MCP clients without a hook layer.** That is a defensible, honest claim.

## MCP server (the agent-callable half) — ✅ built & protocol-verified

`server.py` is a **dependency-free** (stdlib-only) MCP server over stdio/JSON-RPC that wraps the same resolvers and exposes one tool, `verify_identifier(kind, value, cwd?)`. Dependency-free is deliberate: an anti-slopsquatting tool that pulled in a large dependency tree would undercut its own value prop.

Driven through a real client handshake (`initialize → initialized → tools/list → tools/call`) by `test_mcp.py` — **9/9 passed** against live PyPI/npm/filesystem, incl. deprecated detection and JSON-RPC error on bad input. Both halves of the architecture now exist:
- **Hook** (`hook.py`) — fail-closed enforcement in Claude Code.
- **MCP** (`server.py`) — agent-callable, advisory-but-cross-vendor; any MCP client can ask "does this exist?"

Wired for live use in `.mcp.json` (`verify-mcp`). **Live-confirmed on restart:** the server connected and the agent called `verify_identifier` in-session — `pypi requests`→exists, `pypi <slop>`→not-found, `npm request`→deprecated, `path`→exists. The Windows stdio spawn (opportunity #7) worked first try via the `py` launcher; no `cmd /c` needed.

## Cache + rate-limit layer (prototype -> shippable) — ✅ built & verified

`cache.py` is a **stdlib-only SQLite** cache shared by both the short-lived hook processes and the long-running MCP server (an in-memory cache can't bridge the hook's per-call process). Status-aware TTLs double as false-positive protection:
- `exists` 7d · `deprecated` 1d · `not-found` **10 min** (a legitimately-new package may appear) · `cannot-verify` **never cached**.
- A token-bucket throttle caps live registry fetches so gating every turn can't flood PyPI/npm.

Measured: **cold 601 ms → warm 1.1 ms (~500×)** — this is what makes running the gate on every tool call viable. `test_cache.py` 9/9 (latency, TTL policy, no-cache-on-error).

## Files
- `verifier.py` — resolver core (PyPI, npm, filesystem), cache-aware
- `cache.py` — shared SQLite TTL cache + token-bucket rate limiter
- `hook.py` — PreToolUse fail-closed gate (shell-aware install parser)
- `server.py` — dependency-free MCP server exposing `verify_identifier`
- `run_spike.py` — hook behavior harness (exact Claude Code payloads), 10/10
- `test_parse.py` — install-command parser regression, 10/10
- `test_mcp.py` — MCP client-handshake harness, 9/9
- `test_cache.py` — cache latency/TTL/error regression, 9/9
- `../.claude/settings.local.json` — registers the live PreToolUse hook
- `../.mcp.json` — registers the live verify-mcp server

**Total: 38 checks across 4 suites, all passing.**

## Caveats / not yet covered
- Only PyPI + npm + filesystem implemented (crates/Go/citations/API-symbols are more resolvers, same pattern).
- No caching yet (a real build needs a local cache + rate-limit to run every turn cheaply).
## Live wiring (2026-06-14)

Wired into `.claude/settings.local.json` as a `PreToolUse` hook matching `Bash`:
`python "c:/Users/Roney/Documents/new-project/spike/hook.py"`.

- Verified the **exact configured command** (not just hook.py in isolation), fed the real Claude Code `PreToolUse` payload, returns `permissionDecision: "deny"` for a slopsquat install and allows a real package. End-to-end command wiring is proven.
- **Activation caveat (by design):** Claude Code loads hooks at **session start** / on explicit `/hooks` review — a mid-session settings edit does **not** activate them.

### Live confirmation (post-restart) — ✅ THE AGENT WAS BLOCKED FOR REAL

After a restart, the agent's *actual* `Bash` tool call `python -m pip install reqeusts-slop-xyz-9931-zzz` was **denied by the gate before pip ran** — real end-to-end enforcement in the live loop, not a simulation. The thesis holds in production conditions.

**Dogfooding surfaced two real parser bugs (the payoff of testing live):**
1. **FIXED — shell redirects mis-parsed.** `2>&1` was tokenized and `>`-split into a bogus package `"2"`. Fix: the install-arg parser now stops at shell operators/redirects, validates names (must contain a letter), and keeps scoped npm names (`@scope/pkg`). Locked in by `test_parse.py` (5/5).
2. **FIXED — raw-text matching false-positives.** The parser scanned the raw command string, so an install-like substring inside a heredoc / `echo` / grep pattern / commit message triggered a false block (it blocked our own test command that merely *contained* the slop string as data). Fix: shell-aware parsing (`find_install_invocations`) — strip heredoc bodies, tokenize with `shlex(punctuation_chars=True)`, split into command segments on control operators, and only treat a segment as an install when the verb is at a **command position**. Install strings used as data are ignored. Locked in by `test_parse.py` (10/10, incl. echo/grep/commit/heredoc) and live-confirmed (a command embedding the slop string as data now runs).

Both were exactly the robustness issues a real build must solve, and both were invisible until the hook ran against live agent traffic. Note: `shlex` doesn't understand every shell construct (e.g. unquoted install verbs inside an un-stripped heredoc) — the segment/command-position model covers the common cases; a full shell AST parser is the eventual production answer.

- **To remove:** delete `.claude/settings.local.json` (or just its `PreToolUse` block) and restart. With finding #2 fixed, the active gate now only blocks genuine install invocations of nonexistent packages — safe to leave on while building.
