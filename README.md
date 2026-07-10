# vaporcheck

> **Does that identifier actually exist?** Fail-closed existence verification for model-emitted identifiers — catch hallucinated and slop-squatted package names, dead file paths, and nonexistent API/tool names *before* an AI agent acts on them. Vaporware you `pip install` is somebody else's payload.

[![PyPI](https://img.shields.io/pypi/v/vaporcheck)](https://pypi.org/project/vaporcheck/)
[![Python](https://img.shields.io/pypi/pyversions/vaporcheck)](https://pypi.org/project/vaporcheck/)
[![CI](https://github.com/cdmx-in/vaporcheck/actions/workflows/ci.yml/badge.svg)](https://github.com/cdmx-in/vaporcheck/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
![deps](https://img.shields.io/badge/runtime%20deps-0-brightgreen)

```
pip install vaporcheck
```

## See it in action

An agent confidently tries to install a package that doesn't exist. The hook denies it **before pip runs**:

```
Agent:  Bash("pip install reqeusts-slop-xyz")
                    │
                    ▼  PreToolUse hook (~1 ms warm, ~300 ms cold)
        ⛔ DENIED — reqeusts-slop-xyz (package:pypi): NOT FOUND

Agent:  "That package doesn't exist — I meant `requests`."
        Bash("pip install requests")     ✅ allowed, silently
```

Real packages, real file edits, and plain commands pass through with zero friction — the gate only speaks up when the referent doesn't exist.

## Why

LLM coding agents confidently emit identifiers that don't exist: a USENIX Security 2025 study found **19.7% of LLM-recommended packages were hallucinated** — an open door for *slopsquatting* (an attacker registers the hallucinated name and waits). The same failure shows up as dead file paths, deprecated/removed APIs, and calls to tools that were never registered.

The root cause — model **overconfidence** — is not fixable by a wrapper. So vaporcheck doesn't try. It replaces the unanswerable question *"is the model confident?"* with a deterministic one:

> **"Does the referent actually exist in its authoritative source?"**

That's a binary lookup (a registry, the filesystem, a symbol table) — testable, cheap, and hard to argue with.

## How it works

A small **resolver core** answers `exists / not-found / deprecated / cannot-verify` for one identifier, shipped through two delivery vehicles that share the same resolvers and cache:

```mermaid
flowchart LR
    A["AI agent emits an identifier"] --> B["MCP tool call<br/><i>advisory</i>"]
    A --> C["PreToolUse hook<br/><i>fail-closed</i>"]
    B --> D["resolver core<br/>+ SQLite cache"]
    C --> D
    D --> E[("PyPI · npm · filesystem")]
    D --> F{"verdict"}
    F -->|"exists / deprecated"| G["✅ proceed"]
    F -->|"not-found"| H["⛔ deny"]
    F -->|"cannot-verify"| I["❓ ask<br/><i>no false blocks</i>"]
```

| Vehicle | What it is | Guarantee |
|---------|-----------|-----------|
| **MCP server** (`verify_identifier` tool) | Any MCP client can ask "does this exist?" | Agent-callable, advisory |
| **PreToolUse hook** | A Claude Code hook that denies the tool call | **Fail-closed** — the agent can't proceed |

Standalone, the MCP is advisory (the model may ignore it); paired with the hook (or any gateway that can block), it becomes a hard gate.

### The honest boundary

A hook sees **tool calls, not generated text**. So today this gates the two classes that surface at the tool boundary:

- **package installs** (`pip install`, `npm install`, …) — verified against PyPI / npm
- **file paths** (`Edit` of a missing file) — verified against the filesystem

Tool-names and API-symbols buried in generated code are *verify-on-write / verify-on-run* (gate the `Edit` or test that introduces them), not mid-sentence interception. This is a deliberate, documented limit — see [docs/SPIKE-FINDINGS.md](docs/SPIKE-FINDINGS.md).

## Install

Requires **Python 3.10+**. **Zero runtime dependencies** (stdlib only — fitting for an anti-supply-chain-risk tool).

### Option A — pip (adds the `vaporcheck-mcp` console command)

```bash
pip install vaporcheck
```

### Option B — clone (if you want the hook/MCP config to point at source files)

```bash
git clone https://github.com/cdmx-in/vaporcheck.git
cd vaporcheck
python vaporcheck/test_parse.py   # offline smoke test — should print 10/10 PASS
```

## Configure

### As an MCP server (any MCP client)

```jsonc
// .mcp.json (project scope) — pip-installed
{
  "mcpServers": {
    "vaporcheck": { "command": "vaporcheck-mcp" }
  }
}
```

<details>
<summary>Running from a clone instead</summary>

```jsonc
{
  "mcpServers": {
    "vaporcheck": { "command": "python", "args": ["/path/to/vaporcheck/vaporcheck/server.py"] }
  }
}
```

(On Windows, `"command": "py", "args": ["-3", ...]` also works.)

</details>

Then call the `verify_identifier` tool:

```json
{ "kind": "pypi", "value": "reqeusts" }
// -> { "status": "not-found", ... }   (a slopsquat — blocked)
```

### As a fail-closed Claude Code hook

```jsonc
// .claude/settings.json (or settings.local.json)
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "python /path/to/vaporcheck/vaporcheck/hook.py", "timeout": 15 }] }
    ]
  }
}
```

Restart Claude Code to load the hook. Now `pip install <hallucinated-package>` is **denied before it runs**, with a reason the model can self-correct from. On network failure the hook degrades to *ask* instead of falsely blocking.

## Status

**v0.1.0 on [PyPI](https://pypi.org/project/vaporcheck/) — working, tested, dogfooded.** Resolvers: PyPI, npm, filesystem paths. Shared SQLite cache (warm lookups ~1 ms) with status-aware TTLs and a token-bucket throttle. The published wheel is eval'd end-to-end: library API, MCP handshake via the console script, and live registry verdicts.

### Roadmap

- [ ] More package ecosystems: crates.io, Go, RubyGems, Maven
- [ ] **Tool-name** resolver (against the live tool registry) — greenfield, no incumbent
- [ ] **API-symbol** resolver (via LSP / compiler) — greenfield
- [ ] Citations resolver (last; the crowded class — breadth, not headline)
- [x] Namespace the modules under a package; publish to PyPI

## Tests

38 checks across 4 suites — all hitting real registries / filesystem, no mocks:

```bash
python vaporcheck/run_spike.py    # hook behavior (10)
python vaporcheck/test_parse.py   # shell-aware install parser (10)
python vaporcheck/test_mcp.py     # MCP client handshake (9)
python vaporcheck/test_cache.py   # cache latency / TTL / errors (9)
```

## Provenance

This repo is the product of a structured research → validation → build effort. The full record — pain-point research, web-verified go/no-go, and the live-dogfooding spike that found and fixed two real parser bugs — is in [docs/](docs/).

## License

[Apache-2.0](LICENSE) © 2026 [Codemax IT Solutions Pvt. Ltd.](https://cdmx.in)
