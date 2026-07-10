# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versioning is [SemVer](https://semver.org/).

## [Unreleased]

### Added
- **Claude Code plugin + marketplace support**: `/plugin marketplace add cdmx-in/vaporcheck`
  then `/plugin install vaporcheck@cdmx` installs the fail-closed hook (Bash + Edit)
  and the MCP server in one step (`.claude-plugin/`, `hooks/hooks.json`).
- **Manifest gate**: `pip install -r requirements.txt` now reads the file and a bare
  `npm install` reads `package.json`, so the common "write a manifest, then install it"
  flow is verified instead of bypassed.

### Fixed
- **npm false "exists"**: unpublished and security-holding packages (HTTP 200 with no
  live versions / `time.unpublished`) were reported as `exists` and cached for 7 days —
  exactly the malware-shaped names the tool targets. They are now `not-found`.
- **Deprecated no longer auto-approves**: the hook emitted `permissionDecision: "allow"`
  for deprecated packages, which *skipped* the user's normal permission prompt (less
  friction than a healthy install). It now emits `additionalContext` only, leaving the
  normal permission flow intact.
- **Fewer false denies**: option values (`--target dir`, `-i url`, …) are no longer
  mistaken for package names, and installs against a private index/registry are skipped
  rather than denied against the public registry.

### Tests
- New suites `test_manifest.py` (7) and `test_verdicts.py` (7); `run_spike.py` gains a
  manifest-deny end-to-end case. 53 checks across 6 suites.

## [0.1.0] — 2026-07-10

First public release, on PyPI as [`vaporcheck`](https://pypi.org/project/vaporcheck/).

### Changed (since the internal 2026-06-14 MVP below)
- **Renamed the project to `vaporcheck`** (was `verify-identifiers`; name availability
  verified across PyPI / npm / GitHub / trademarks). Code moved from `spike/` to
  `vaporcheck/`; MCP server name and console script renamed accordingly
  (`verify-mcp` → `vaporcheck` / `vaporcheck-mcp`).
- Published under **Codemax IT Solutions Pvt. Ltd.** (LICENSE / NOTICE / pyproject).
- Modules namespaced under the `vaporcheck` package (dual-mode imports keep the
  files runnable as plain scripts for the hook / MCP config).
- README: added install instructions (`pip install vaporcheck` or clone).

## [0.1.0-mvp] — 2026-06-14

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
