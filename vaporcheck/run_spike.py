"""Spike harness: does the PreToolUse hook actually enforce fail-closed?

Feeds the hook the exact JSON Claude Code pipes on stdin for real tool
calls, captures its stdout, and checks the permission decision. No mocks:
real registry lookups, real subprocess, real stdin/stdout contract.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "hook.py")
EXISTING_FILE = HOOK                      # a path that really exists
MISSING_FILE = os.path.join(HERE, "this_path_does_not_exist_zzz.py")


def call_hook(tool_name, tool_input):
    event = {
        "session_id": "spike",
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
        "permission_mode": "default",
        "cwd": HERE,
    }
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(event),
                       capture_output=True, text=True, cwd=HERE)
    out = p.stdout.strip()
    if not out:
        return "allow(silent)", ""
    try:
        d = json.loads(out)["hookSpecificOutput"]
        return d["permissionDecision"], d.get("permissionDecisionReason", "")
    except Exception:
        return f"?? raw={out!r}", ""


CASES = [
    # (label, tool, input, expected_decision)
    ("pip install real pkg",        "Bash",  {"command": "pip install requests"},                         "allow(silent)"),
    ("pip install SLOP pkg",        "Bash",  {"command": "pip install reqeusts-slop-xyz-9931"},           "deny"),
    ("npm install real pkg",        "Bash",  {"command": "npm install express"},                          "allow(silent)"),
    ("npm install FAKE pkg",        "Bash",  {"command": "npm install expresss-fake-zzz-0001"},           "deny"),
    ("pip w/ version pin + 2 pkgs", "Bash",  {"command": "pip install requests==2.31.0 flask"},           "allow(silent)"),
    ("pip one good one BOGUS",      "Bash",  {"command": "pip install requests boguspkg-zzz-77"},         "deny"),
    ("plain bash, no identifier",   "Bash",  {"command": "ls -la && echo hi"},                            "allow(silent)"),
    ("Edit existing file",          "Edit",  {"file_path": EXISTING_FILE, "old_string": "a", "new_string": "b"}, "allow(silent)"),
    ("Edit NONEXISTENT path",       "Edit",  {"file_path": MISSING_FILE, "old_string": "a", "new_string": "b"}, "deny"),
    ("Write new (not-yet) file",    "Write", {"file_path": MISSING_FILE, "file_content": "x"},            "allow(silent)"),
]


def main():
    print(f"{'CASE':<30} {'EXPECTED':<14} {'GOT':<14} RESULT")
    print("-" * 78)
    passed = 0
    for label, tool, tin, expected in CASES:
        got, reason = call_hook(tool, tin)
        ok = got == expected
        passed += ok
        print(f"{label:<30} {expected:<14} {got:<14} {'PASS' if ok else 'FAIL'}")
        if got == "deny":
            first = reason.splitlines()[1].strip() if "\n" in reason else reason[:70]
            print(f"{'':<30} -> {first}")
    print("-" * 78)
    print(f"{passed}/{len(CASES)} cases passed")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
