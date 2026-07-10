"""Drive the vaporcheck MCP server through a real client handshake and assert responses.

Spawns server.py over stdio and speaks newline-delimited JSON-RPC 2.0:
initialize -> initialized -> tools/list -> tools/call(...). No mocks; the
tool calls hit real PyPI/npm/filesystem.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "server.py")


class Client:
    def __init__(self):
        self.p = subprocess.Popen(
            [sys.executable, SERVER], cwd=HERE,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1)
        self._id = 0

    def request(self, method, params=None):
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            msg["params"] = params
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        return json.loads(line)

    def notify(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()

    def close(self):
        self.p.stdin.close()
        self.p.terminate()


def call_tool(c, kind, value, cwd=""):
    args = {"kind": kind, "value": value}
    if cwd:
        args["cwd"] = cwd
    r = c.request("tools/call", {"name": "verify_identifier", "arguments": args})
    return r["result"]["structuredContent"]["status"], r["result"]["content"][0]["text"]


def main():
    c = Client()
    checks = []

    def check(label, cond, detail=""):
        checks.append(cond)
        print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))

    init = c.request("initialize", {"protocolVersion": "2025-06-18",
                                    "capabilities": {}, "clientInfo": {"name": "spike-test", "version": "0"}})
    check("initialize -> serverInfo.name == vaporcheck",
          init.get("result", {}).get("serverInfo", {}).get("name") == "vaporcheck",
          json.dumps(init.get("result", {}).get("serverInfo", {})))

    c.notify("notifications/initialized")

    tl = c.request("tools/list")
    names = [t["name"] for t in tl["result"]["tools"]]
    check("tools/list exposes verify_identifier", "verify_identifier" in names, str(names))

    s, t = call_tool(c, "pypi", "requests")
    check("pypi requests -> exists", s == "exists", t)

    s, t = call_tool(c, "pypi", "reqeusts-slop-xyz-9931-zzz")
    check("pypi slop -> not-found", s == "not-found", t)

    s, t = call_tool(c, "npm", "express")
    check("npm express -> exists", s == "exists", t)

    s, t = call_tool(c, "npm", "request")
    check("npm request -> deprecated", s == "deprecated", t)

    s, t = call_tool(c, "path", SERVER)
    check("path server.py -> exists", s == "exists", t)

    s, t = call_tool(c, "path", os.path.join(HERE, "nope_zzz.py"))
    check("path missing -> not-found", s == "not-found", t)

    bad = c.request("tools/call", {"name": "verify_identifier", "arguments": {"kind": "bogus", "value": "x"}})
    check("invalid kind -> JSON-RPC error", "error" in bad, json.dumps(bad.get("error", {})))

    c.close()
    passed = sum(checks)
    print(f"\n{passed}/{len(checks)} MCP checks passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
