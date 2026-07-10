"""Self-test: is vaporcheck actually wired up and able to protect this machine?

Run it when a hook seems silently inactive:

    python -m vaporcheck.doctor      # installed
    python vaporcheck/doctor.py      # from a clone

Checks the interpreter (the #1 Windows failure is `python` resolving to the
Microsoft Store stub), the cache location, and live reachability of PyPI + npm.
Exit code 0 if everything a working gate needs is present.
"""
import os
import sys

try:
    from . import cache, verifier
except ImportError:
    import cache
    import verifier


def _line(ok, label, detail=""):
    print(f"  [{'OK ' if ok else 'XX '}] {label}" + (f" - {detail}" if detail else ""))
    return ok


def run() -> int:
    print("vaporcheck doctor\n")
    ok = True

    ok &= _line(sys.version_info >= (3, 10),
                f"Python {sys.version_info.major}.{sys.version_info.minor}", sys.executable)
    # Windows Store alias stub: a zero-byte shim under WindowsApps that exits silently
    exe = (sys.executable or "").lower()
    if os.name == "nt" and "windowsapps" in exe:
        ok &= _line(False, "interpreter",
                    "this looks like the Microsoft Store 'python' stub — install python.org "
                    "Python or point the hook at 'py'")

    writable = True
    try:
        cache.throttle()                    # exercises the real cache path
    except Exception as e:                   # noqa: BLE001 - report, don't crash
        writable = False
        detail = f"{type(e).__name__}: {e}"
    else:
        detail = cache.CACHE_PATH
    ok &= _line(writable, "cache writable", detail)

    pv = verifier.verify_pypi("pip")         # a package that always exists
    ok &= _line(pv.status == "exists", "PyPI reachable", pv.status)
    nv = verifier.verify_npm("npm")
    ok &= _line(nv.status == "exists", "npm reachable", nv.status)

    print("\n" + ("All checks passed - the gate can protect this machine."
                  if ok else "Some checks failed - see above."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(run())
