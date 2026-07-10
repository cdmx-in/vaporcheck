"""Prove the cache: cold vs warm latency, status-aware TTLs, no caching of errors."""
import time

import cache
import verifier

checks = []


def check(label, cond, detail=""):
    checks.append(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))


cache.clear()

# 1) cold miss then warm hit
t = time.time(); v1 = verifier.verify_pypi("requests"); cold = (time.time() - t) * 1000
t = time.time(); v2 = verifier.verify_pypi("requests"); warm = (time.time() - t) * 1000
check("cold call is a live miss", v1.cached is False, f"{cold:.0f}ms")
check("warm call is a cache hit", v2.cached is True, f"{warm:.0f}ms")
check("warm hit is >=10x faster", warm < cold / 10 + 1, f"cold {cold:.0f}ms vs warm {warm:.1f}ms")
check("hit preserves verdict", v2.status == v1.status == "exists")

# 2) status-aware TTL: not-found expires much sooner than exists
verifier.verify_pypi("reqeusts-slop-xyz-9931-zzz")        # not-found -> short TTL
nf = cache.peek("package:pypi", "reqeusts-slop-xyz-9931-zzz")
ex = cache.peek("package:pypi", "requests")
nf_ttl = nf["expires"] - time.time()
ex_ttl = ex["expires"] - time.time()
check("not-found cached briefly (<=10min)", 0 < nf_ttl <= 600 + 5, f"{nf_ttl:.0f}s")
check("exists cached long (>1 day)", ex_ttl > 24 * 3600, f"{ex_ttl/3600:.0f}h")
check("not-found TTL << exists TTL", nf_ttl < ex_ttl / 100)

# 3) cannot-verify must NOT be cached (transient errors shouldn't stick)
orig = verifier.urllib.request.urlopen
verifier.urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(OSError("down"))
v = verifier.verify_pypi("flask")
verifier.urllib.request.urlopen = orig
check("network error -> cannot-verify", v.status == "cannot-verify")
check("cannot-verify NOT cached", cache.peek("package:pypi", "flask") is None)

passed = sum(checks)
print(f"\n{passed}/{len(checks)} cache checks passed")
raise SystemExit(0 if passed == len(checks) else 1)
