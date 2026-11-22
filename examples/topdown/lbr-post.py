#!/usr/bin/env python3
"""Post-run, on the bench box: summarise the lbr-a perf.data files (run it when no measurement runs).

python3 -I lbr-post.py [--perf PERF] <lbr-data dir> <lbr run dir (legs.jsonl)> <out.json>

PERF: perf binary (default: the PERF environment variable, else `perf` on PATH).

Per file (one leg = arm x shape): sample counts per event, whether branch stacks decode, the top
leaf symbols of the cycles:u samples, and the attribution of cycles:u samples to the upstream
filter-manager machinery (how much a bypass of that machinery could save at most):
  fm     the upstream filter-manager machinery: a sample whose leaf-most deciding frame is one of
         UpstreamFilterManager / UpstreamRequestFilterManagerCallbacks / UpstreamCodecFilter /
         CodecBridge / the UpstreamRequest constructor or destructor, or a generic FilterManager /
         ActiveStream*Filter / StreamInfoImpl frame whose next Router frame upward is UpstreamRequest
         (not Router::Filter or the connection manager). Frames that decide nothing (allocator, std::,
         header map, libc) pass through, so allocations the machinery makes count to it. A codec,
         network, buffer, event-loop or router-filter frame met first means "other".
  ur     self work of other UpstreamRequest methods (kept by a bypass, reported apart)
  incl   any UpstreamRequest/upstream-FM frame anywhere in the chain (upper bound, includes the
         downstream response path that runs under UpstreamRequest::decodeHeaders)
"""
import argparse
import json
import os
import re
import subprocess
from collections import Counter

_ap = argparse.ArgumentParser(description="Summarise the lbr-a perf.data files.")
_ap.add_argument("--perf", default=os.environ.get("PERF") or "perf", help="perf binary (default: $PERF or perf)")
_ap.add_argument("lbr_dir")
_ap.add_argument("run_dir")
_ap.add_argument("out")
_args = _ap.parse_args()
PERF = _args.perf
lbr_dir, run_dir, out = _args.lbr_dir, _args.run_dir, _args.out

SPEC = re.compile(r"UpstreamFilterManager|UpstreamRequestFilterManagerCallbacks|UpstreamCodecFilter|CodecBridge|"
                  r"Router::UpstreamRequest::UpstreamRequest\(|Router::UpstreamRequest::~UpstreamRequest")
GEN = re.compile(r"Http::FilterManager::|ActiveStreamDecoderFilter|ActiveStreamEncoderFilter|ActiveStreamFilterBase|"
                 r"StreamInfo::StreamInfoImpl|UpstreamInfoImpl")
UR = re.compile(r"Router::UpstreamRequest::")
DOWN = re.compile(r"Router::Filter::|ConnectionManagerImpl")
WORK = re.compile(r"Http1::|Http2::|Router::Filter::|ConnectionManagerImpl|Network::|Event::|Buffer::|"
                  r"Envoy::Ssl|Upstream::|ConnectionPool|Http::CodecClient")
INCL = re.compile(r"Router::UpstreamRequest::|UpstreamFilterManager|UpstreamCodecFilter|CodecBridge")


def classify(frames):
    for i, f in enumerate(frames):
        if SPEC.search(f):
            return "fm"
        if GEN.search(f):
            for g in frames[i + 1:]:
                if UR.search(g):
                    return "fm"
                if DOWN.search(g):
                    return "other"
            return "other"
        if UR.search(f):
            return "ur"
        if WORK.search(f):
            return "other"
    return "other"


pid_leg = {}
for line in open(os.path.join(run_dir, "legs.jsonl")):
    m = json.loads(line)
    pid_leg[str(m.get("envoy_pid"))] = {"leg_id": m["leg_id"], "arm": m["arm"], "shape": m["shape"],
                                        "valid": m["verdict"]["valid"], "responses": m.get("responses")}
res = {}
for fn in sorted(os.listdir(lbr_dir)):
    if not fn.endswith(".data"):
        continue
    pid = fn[len("lbr-"):-len(".data")]
    path = os.path.join(lbr_dir, fn)
    p = subprocess.Popen([PERF, "script", "-i", path, "-F", "event,ip,sym", "--no-inline"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors="replace")
    ev_count = Counter()
    cls = Counter()
    leaf = Counter()
    incl = 0
    cur_ev, frames = None, []

    def flush():
        global incl
        if cur_ev is None:
            return
        ev_count[cur_ev] += 1
        if "cycles" in cur_ev:
            cls[classify(frames)] += 1
            if any(INCL.search(f) for f in frames):
                incl += 1
            if frames:
                leaf[frames[0][:160]] += 1

    for line in p.stdout:
        if not line.strip():
            continue
        if not line.startswith("\t"):
            # header (space-padded): "cpu/cycles,period=1000003/u:" or "cpu/event=0xc4,...:"
            flush()
            # header: "cpu/cycles,period=1000003/u:" or "cpu/event=0xc4,umask=0x20,period=100003/upp:"
            cur_ev = "cycles" if "cycles" in line else "br_inst_retired.near_taken"
            frames = []
            continue
        parts = line.strip().split(None, 1)
        frames.append(parts[1] if len(parts) > 1 else parts[0])
    flush()
    p.wait()
    br = subprocess.run([PERF, "script", "-i", path, "-F", "brstack"], capture_output=True, text=True,
                        errors="replace", timeout=900).stdout.splitlines()[:200]
    br_ok = sum(1 for x in br if "/P/" in x or "/M/" in x)
    n = cls["fm"] + cls["ur"] + cls["other"]
    res[fn] = {"pid": pid, "leg": pid_leg.get(pid), "bytes": os.path.getsize(path), "samples": dict(ev_count),
               "brstack_lines_ok_of_200": br_ok,
               "cycles_samples": n, "fm_share": cls["fm"] / n if n else None, "ur_share": cls["ur"] / n if n else None,
               "incl_upper_share": incl / n if n else None,
               "top_leaf": [(s, c / n) for s, c in leaf.most_common(30)] if n else []}
    print(fn, json.dumps({k: v for k, v in res[fn].items() if k != "top_leaf"}), flush=True)
json.dump(res, open(out, "w"), indent=1)
