"""Regression for the manifest gate: `pip install -r`, bare `npm install`,
option-value skipping, and private-index handling.

Extraction-only (no network) — asserts which (kind, identifier) pairs the parser
routes to the resolvers. The write-a-manifest-then-install-it flow used to
bypass the gate entirely; these lock the fix.
"""
import os
import tempfile

import hook

checks = []


def check(label, cond, detail=""):
    checks.append(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))


def main():
    d = tempfile.mkdtemp(prefix="vaporcheck_manifest_")

    # --- pip install -r requirements.txt (the flagship bypass) ---
    req = os.path.join(d, "requirements.txt")
    with open(req, "w", encoding="utf-8") as f:
        f.write(
            "# a comment\n"
            "requests\n"
            "reqeusts-slop-xyz-9931-zzz==1.0   # inline comment\n"
            "flask>=2 ; python_version >= '3.8'\n"
            "-e .\n"
            "./local/path\n"
            "\n"
        )
    # forward slashes: the Bash tool runs a POSIX shell, so paths arrive that way
    got = hook.find_install_invocations(f"pip install -r {req.replace(os.sep, '/')}", d)
    check("pip install -r reads the file",
          got == [("pypi", "requests"), ("pypi", "reqeusts-slop-xyz-9931-zzz"), ("pypi", "flask")],
          str(got))

    got = hook.find_install_invocations("pip install -r requirements.txt", d)
    check("relative -r resolves against cwd", ("pypi", "reqeusts-slop-xyz-9931-zzz") in got, str(got))

    # --- bare npm install reads package.json ---
    pj = os.path.join(d, "package.json")
    with open(pj, "w", encoding="utf-8") as f:
        f.write('{"dependencies": {"express": "^4"}, '
                '"devDependencies": {"expresss-fake-zzz-0001": "^1"}}')
    got = hook.find_install_invocations("npm install", d)
    check("bare npm install reads package.json",
          sorted(got) == [("npm", "express"), ("npm", "expresss-fake-zzz-0001")], str(got))

    # explicit package -> do NOT also slurp package.json
    got = hook.find_install_invocations("npm install express", d)
    check("npm install <pkg> does not read package.json", got == [("npm", "express")], str(got))

    # --- option values must not be mistaken for packages ---
    got = hook.find_install_invocations("pip install --target mydir requests", d)
    check("--target value skipped, package still caught", got == [("pypi", "requests")], str(got))

    # --- private index: cannot verify publicly, so extract nothing (no false deny) ---
    got = hook.find_install_invocations("pip install -i https://mirror.local/simple internal-pkg", d)
    check("private index -> no extraction (no false deny)", got == [], str(got))

    got = hook.find_install_invocations("npm install --registry https://npm.local foo-bar-pkg", d)
    check("npm private registry -> no extraction", got == [], str(got))

    print(f"\n{sum(checks)}/{len(checks)} manifest cases passed")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
