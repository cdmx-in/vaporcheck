"""Regression for command normalization and the expanded install-verb set.

Extraction-only (no network). Covers: sudo/env/VAR= prefixes, path- and
version-suffixed interpreters (pip3.12, python3.11, py -3), the poetry/pdm/
pipenv/uv/bun package managers, and one-off executors (npx/uvx/pnpm dlx) where
only the RUN TARGET is a package, not its arguments.
"""
import hook

checks = []


def check(label, got, expected):
    ok = got == expected
    checks.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + ("" if ok else f"  expected {expected}, got {got}"))


CASES = [
    # prefixes stripped
    ("sudo pip install slop-pkg-zzz",              [("pypi", "slop-pkg-zzz")]),
    ("PIP_INDEX=x pip install foo-pkg-zzz",        [("pypi", "foo-pkg-zzz")]),
    ("sudo -H pip install bar-pkg-zzz",            [("pypi", "bar-pkg-zzz")]),
    # versioned / path-prefixed / launcher interpreters
    ("pip3.12 install ver-pkg-zzz",                [("pypi", "ver-pkg-zzz")]),
    ("python3.11 -m pip install mpkg-zzz",         [("pypi", "mpkg-zzz")]),
    ("py -3 -m pip install winpkg-zzz",            [("pypi", "winpkg-zzz")]),
    ("/usr/bin/pip install abspkg-zzz",            [("pypi", "abspkg-zzz")]),
    # more python package managers
    ("poetry add poetrypkg-zzz",                   [("pypi", "poetrypkg-zzz")]),
    ("pdm add pdmpkg-zzz",                         [("pypi", "pdmpkg-zzz")]),
    ("pipenv install envpkg-zzz",                  [("pypi", "envpkg-zzz")]),
    ("uv add uvpkg-zzz",                           [("pypi", "uvpkg-zzz")]),
    # more js package managers
    ("bun add bunpkg-zzz",                         [("npm", "bunpkg-zzz")]),
    ("pnpm add pnpmpkg-zzz",                       [("npm", "pnpmpkg-zzz")]),
    # one-off executors: only the FIRST package (run target), not its args
    ("npx create-react-app my-app",               [("npm", "create-react-app")]),
    ("npx -y cowsay-zzz hello there",             [("npm", "cowsay-zzz")]),
    ("uvx ruff-zzz check .",                       [("pypi", "ruff-zzz")]),
    ("pnpm dlx create-thing-zzz --flag arg",       [("npm", "create-thing-zzz")]),
    ("pipx run pipxtool-zzz --version",            [("pypi", "pipxtool-zzz")]),
    # not an install -> nothing
    ("pip download somepkg",                       []),
    ("poetry lock",                                []),
]


def main():
    for cmd, expected in CASES:
        check(cmd, hook.find_install_invocations(cmd), expected)
    print(f"\n{sum(checks)}/{len(checks)} verb cases passed")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
