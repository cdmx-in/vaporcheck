# What vaporcheck does and doesn't guarantee

vaporcheck is a useful safety layer, not a sandbox. Its whole design is honest
about one thing: it verifies **existence**, not intent. This page states exactly
where the gate is enforced, where it is only advisory, and the routes it cannot
see — so nobody relies on a guarantee it doesn't make.

## Enforcement matrix

| Surface | Behaviour | Enforced? |
|---------|-----------|-----------|
| **Claude Code PreToolUse hook** | Denies the tool call before it runs | ✅ **Fail-closed** |
| Cursor / other agents with a shell/tool hook | Same, once wired to the hook | ✅ Fail-closed (adapter-dependent) |
| **MCP server** (`verify_identifier`) | Answers when the model asks | ⚠️ **Advisory** — the model may not call it |
| Pure-MCP client with no hook/gateway | Advisory only | ⚠️ Not enforced |

The gate is only as strong as the surface it runs on. In Claude Code it blocks;
in a bare MCP client it informs. We never claim otherwise.

## What is checked

- **Package installs** — `pip`/`pip3.x`/`pipx`/`uv`/`poetry`/`pdm`/`pipenv` (PyPI)
  and `npm`/`yarn`/`pnpm`/`bun` (npm), including one-off executors (`npx`, `uvx`,
  `pnpm dlx`, `pipx run`) and manifest installs (`pip install -r requirements.txt`,
  bare `npm install` reading `package.json`).
- **File paths** — an `Edit` of a path that does not exist.

On a not-found verdict the call is denied; on a network failure it degrades to
**ask** (never a false block); a deprecated package is allowed through the normal
permission prompt with a warning (it is not auto-approved).

## Known limitations (by design)

These are consequences of verifying at the tool boundary, not bugs:

1. **Generated text is not scanned.** The hook sees tool calls, not the model's
   prose or code. A hallucinated *API symbol* inside written code is caught when
   the code is run/edited, not mid-sentence.
2. **Dynamically constructed commands are unresolvable.** `pip install $PKG`,
   `$(cat names)`, `echo cGtn | base64 -d | sh`, and similar hide the identifier
   from any static parser. We do not guess; these pass. (Documented, not silently
   ignored.)
3. **Private indexes are trusted, not verified.** `pip install -i <private-url> x`
   and `npm --registry <url>` are skipped rather than checked against the public
   registry — otherwise a legitimate internal package would be falsely denied.
4. **Registered slopsquats still "exist".** If an attacker has already registered
   a hallucinated name, an existence check passes it. Typosquat heuristics are on
   the roadmap; today existence ≠ safety.
5. **Windows backslash paths in shell commands** may be mangled by the POSIX
   tokenizer. In practice the Bash tool runs a POSIX shell with forward slashes,
   so this rarely bites — but absolute `C:\...` paths passed literally are a known
   gap.

If the hook seems silently inactive, run `python -m vaporcheck.doctor`.

## How it relates to other tools

vaporcheck is **complementary** to registry-side scanners, not a competitor:

| | vaporcheck | Socket / DepShield / guarddog / SafeDep |
|---|---|---|
| Where it runs | Client-side, in the agent loop | Registry/CI side |
| When | Before the install command executes | On publish / in CI / on resolve |
| Question | "Does this identifier exist?" | "Is this package malicious / vulnerable?" |
| Dependencies | Zero | Vary |

Use both: vaporcheck stops the agent from ever reaching for a name that isn't
real; a scanner judges whether a real package is safe.
