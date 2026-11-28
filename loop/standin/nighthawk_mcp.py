#!/usr/bin/env python3
"""Stand-in nighthawk_mcp for the loop's local tests: newline-delimited JSON-RPC 2.0 on stdio (the fork's transport,
protocol 2025-06-18), with the tools the daemon forwards (start_run, steer, cancel_run, get_status, echo) and the
nighthawk://series resource (benchmark.http_2xx, cumulative, each point stamped with monotonic_ns). Steering moves
the stand-in Envoy's 2xx rate through its /standin_rate, so the merged timeline shows the change.

    nighthawk_mcp.py --service-address A --max-rps N --admin-base http://127.0.0.1:P"""
import json
import sys
import threading
import time
import urllib.request


def mono_ns():
    if hasattr(time, "clock_gettime_ns") and hasattr(time, "CLOCK_MONOTONIC"):
        return time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    return time.monotonic_ns()

args = sys.argv[1:]
max_rps = int(args[args.index("--max-rps") + 1]) if "--max-rps" in args else 100000
admin = args[args.index("--admin-base") + 1] if "--admin-base" in args else None
st = {"run": None, "rate": 0.0, "count": 0.0, "t": time.monotonic(), "points": [], "epoch": 0}
lock = threading.Lock()


def advance():
    now = time.monotonic()
    st["count"] += st["rate"] * (now - st["t"])
    st["t"] = now


def set_rate(r):
    with lock:
        advance()
        st["rate"] = float(r)
    if admin:
        try:
            urllib.request.urlopen(urllib.request.Request("%s/standin_rate?rps=%d" % (admin, int(r)), data=b"",
                                                          method="POST"), timeout=2).read()
        except OSError:
            pass


def sampler():
    while True:
        with lock:
            advance()
            if st["run"] is not None:
                st["points"].append({"monotonic_ns": mono_ns(), "value": int(st["count"]),
                                     "phase_id": "p0", "epoch_id": str(st["epoch"])})
        time.sleep(0.5)


def err(i, code, msg):
    return {"jsonrpc": "2.0", "id": i, "error": {"code": code, "message": msg}}


def tool_result(obj, is_error=False):
    return {"content": [{"type": "text", "text": json.dumps(obj)}], "structuredContent": obj, "isError": is_error}


def call(name, a):
    if name == "echo":
        return tool_result({"message": a.get("message")})
    if name == "start_run":
        if st["run"] is not None:
            return tool_result({"error": "a run is in flight"}, True)
        rps = int(a.get("rps", 0))
        if rps <= 0 or rps > max_rps:
            return tool_result({"error": "rps must be a positive integer under the ceiling %d" % max_rps}, True)
        st["run"] = {"uri": a.get("uri"), "rps": rps, "args": a}
        set_rate(rps)
        return tool_result({"run_started": True, "session": "standin", "resolved_target": a.get("uri")})
    if name == "steer":
        if st["run"] is None:
            return tool_result({"error": "no run in flight"}, True)
        rps = int(a.get("rps", 0))
        if rps <= 0 or rps > max_rps:
            return tool_result({"error": "rps must be a positive integer under the ceiling %d" % max_rps}, True)
        st["epoch"] += 1
        st["run"]["rps"] = rps
        set_rate(rps)
        return tool_result({"applied": True, "epoch_id": str(st["epoch"]), "monotonic_ns": mono_ns()})
    if name == "cancel_run":
        if st["run"] is None:
            return tool_result({"error": "no run in flight"}, True)
        st["run"] = None
        set_rate(0)
        return tool_result({"cancelled": True, "session": "standin"})
    if name == "get_status":
        return tool_result({"in_flight": st["run"] is not None, "run": st["run"], "epoch": st["epoch"]})
    return None


def main():
    threading.Thread(target=sampler, daemon=True).start()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
        except ValueError:
            continue
        i, meth, params = m.get("id"), m.get("method"), m.get("params") or {}
        if i is None:
            continue
        if meth == "initialize":
            out = {"jsonrpc": "2.0", "id": i, "result": {"protocolVersion": "2025-06-18", "capabilities": {
                "tools": {}, "resources": {}}, "serverInfo": {"name": "nighthawk-mcp-standin", "version": "0"}}}
        elif meth == "tools/call":
            r = call(params.get("name"), params.get("arguments") or {})
            out = err(i, -32602, "unknown tool") if r is None else {"jsonrpc": "2.0", "id": i, "result": r}
        elif meth == "resources/read":
            if params.get("uri") != "nighthawk://series":
                out = err(i, -32602, "unknown resource")
            else:
                with lock:
                    body = {"series": [{"name": "benchmark.http_2xx", "points": list(st["points"])}]}
                out = {"jsonrpc": "2.0", "id": i, "result": {"contents": [
                    {"uri": "nighthawk://series", "mimeType": "application/json", "text": json.dumps(body)}]}}
        else:
            out = err(i, -32601, "method not found")
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
