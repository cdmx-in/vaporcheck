"""Regression for the shell-redirect parse bug found during live dogfooding.

The live hook once flagged a bogus package "2" because the redirect 2>&1 was
tokenized and >-split. These cases lock in the fix. (Install strings live HERE,
in a file, not on a Bash command line — otherwise the live hook gates the test
command itself, which is finding #2.)
"""
import hook

CASES = [
    # command, expected extracted (kind, identifier) list
    ("python -m pip install reqeusts-slop-xyz-9931-zzz --quiet 2>&1 | head -5",
     [("pypi", "reqeusts-slop-xyz-9931-zzz")]),                       # no bogus "2"
    ("pip install requests 2>&1 | tee log.txt",
     [("pypi", "requests")]),
    ("npm install express && echo done | cat",
     [("npm", "express")]),
    ("pip install requests==2.31.0 flask>=2 2> err.log",
     [("pypi", "requests"), ("pypi", "flask")]),                      # pins stripped, redirect ignored
    ("npm install @scope/pkg",
     [("npm", "@scope/pkg")]),                                        # scoped npm name kept
    # --- finding #2: install strings as DATA must NOT be gated ---
    ('echo "pip install sloppkg-zzz-not-real"', []),                  # quoted arg, not a command
    ("grep 'npm install' notes.txt", []),                            # grep pattern
    ("git commit -m 'chore: run pip install boguspkg-xyz'", []),      # commit message
    ("python - <<'PY'\nx = 'pip install slop-data-pkg-zzz'\nPY", []),  # heredoc body
    # genuine install AFTER an unrelated command still detected
    ("echo starting && pip install reqeusts-slop-xyz-9931-zzz",
     [("pypi", "reqeusts-slop-xyz-9931-zzz")]),
]

if __name__ == "__main__":
    ok = 0
    for cmd, expected in CASES:
        got = hook.extract_identifiers("Bash", {"command": cmd})
        passed = got == expected
        ok += passed
        print(f"[{'PASS' if passed else 'FAIL'}] {cmd}")
        if not passed:
            print(f"        expected {expected}\n        got      {got}")
    print(f"\n{ok}/{len(CASES)} parse cases passed")
    raise SystemExit(0 if ok == len(CASES) else 1)
