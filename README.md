# vaporcheck

**Stops AI coding assistants from using things that don't exist.**

[![PyPI](https://img.shields.io/pypi/v/vaporcheck)](https://pypi.org/project/vaporcheck/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

AI assistants sometimes invent package names, file paths, and function names that look real but aren't. Research found that almost **1 in 5 packages recommended by AI didn't exist** — and attackers register those fake names to spread malware (this is called *slopsquatting*).

vaporcheck is a simple safety net: before your AI assistant installs a package or touches a file, it checks — **does this actually exist?** If not, it blocks the action and tells the assistant why, so it can correct itself.

## What it looks like

```
AI:  pip install reqeusts-slop-xyz        ← a package that doesn't exist

     ⛔ BLOCKED by vaporcheck — that package was not found

AI:  "Oops — I meant `requests`."
     pip install requests                 ✅ goes through normally
```

Real packages and real files pass through instantly. You'll never notice vaporcheck until it saves you.

## Install

**If you use Claude Code** — two commands, done:

```
/plugin marketplace add cdmx-in/vaporcheck
/plugin install vaporcheck@cdmx
```

That installs both the protection (the blocker) and the `verify_identifier` tool your assistant can use to double-check things itself.

**If you use any other AI tool that supports MCP:**

```bash
pip install vaporcheck
```

then add this to your tool's MCP config:

```json
{
  "mcpServers": {
    "vaporcheck": { "command": "vaporcheck-mcp" }
  }
}
```

Works on Windows, Mac, and Linux. No other dependencies.

Not sure it's working? Run `python -m vaporcheck.doctor`.

## What it checks today

- ✅ Python packages (PyPI) — including whole `requirements.txt` files
- ✅ JavaScript packages (npm) — including `package.json`
- ✅ File paths on your computer

Coming next: more package ecosystems (Rust, Go, Ruby, Java) and code symbols.

## More

Developers and the curious can find everything else — how it works, the research behind it — in [docs/](docs/).

## License

[Apache-2.0](LICENSE) © 2026 [Codemax IT Solutions Pvt. Ltd.](https://cdmx.in)
