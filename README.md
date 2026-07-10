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

```bash
pip install vaporcheck
```

That's it — no other dependencies, works on Windows, Mac, and Linux.

## Set up

**If you use Claude Code** — add this to `.claude/settings.json` in your project, then restart:

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "python /path/to/vaporcheck/vaporcheck/hook.py", "timeout": 15 }] }
    ]
  }
}
```

**If you use any other AI tool that supports MCP** — add this to your MCP config:

```json
{
  "mcpServers": {
    "vaporcheck": { "command": "vaporcheck-mcp" }
  }
}
```

Your assistant then gets a `verify_identifier` tool it can use to double-check anything before acting on it.

## What it checks today

- ✅ Python packages (PyPI)
- ✅ JavaScript packages (npm)
- ✅ File paths on your computer

Coming next: more package ecosystems (Rust, Go, Ruby, Java), tool names, and code symbols.

## More

Developers and the curious can find everything else — how it works, the research behind it — in [docs/](docs/).

## License

[Apache-2.0](LICENSE) © 2026 [Codemax IT Solutions Pvt. Ltd.](https://cdmx.in)
