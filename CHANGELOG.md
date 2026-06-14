# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versioning is [SemVer](https://semver.org/).

## [0.1.0] — 2026-06-14

First working MVP. Validated, dogfooded, and live-confirmed in Claude Code.

### Added
- **Resolver core** (`verifier.py`) — `exists / not-found / deprecated / cannot-verify`
  for PyPI packages, npm packages, and filesystem paths. Zero runtime dependencies.
- **MCP server** (`server.py`) — dependency-free stdio JSON-RPC server exposing the
  `verify_identifier(kind, value, cwd?)` tool. Verified against a real client handshake.
- **PreToolUse hook** (`hook.py`) — fail-closed Claude Code gate that denies a tool
  call referencing a nonexistent identifier. Shell-aware install-command parser.
- **Shared cache** (`cache.py`) — SQLite cache used by both the hook and the server,
  with status-aware TTLs (exists 7d / deprecated 1d / not-found 10 min /
  cannot-verify never) and a token-bucket rate limiter. Warm lookups ~1 ms.
- **38 tests** across 4 suites (hook behavior, install parser, MCP handshake, cache),
  all against real registries / filesystem.

### Fixed (found via live dogfooding)
- Shell redirect `2>&1` was mis-parsed into a bogus package `"2"`.
- Install strings appearing as **data** (heredocs, `echo`, grep, commit messages)
  triggered false blocks; parser is now shell-aware and only gates install verbs at a
  command position.

### Known limits
- Enforcement is at the tool-call boundary only (packages, paths); tool-names and
  API-symbols are verify-on-write / verify-on-run, not mid-generation.
- Modules are flat (not yet namespaced under a package).
