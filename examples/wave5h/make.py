#!/usr/bin/env python3
"""Write the configs of wave 5 track H: the CPU price of the Linux CPU-vulnerability mitigations, and a
check of the TCP_DEFER_ACCEPT latency shift against the CPU idle states.

Official v1.40.2 binary (~/epl/bin/envoy-1.40.2, sha256 enforced) in every arm.

    python3 examples/wave5h/make.py [--box BOX_JSON] [--rates '{"h-pl.s": 4000, "h-pl.fh": 6400, "h-c1": 800}']

--rates is the smoke fallback fixed before the run (a rate or kernel gate fails): keys RUN.SHAPE or RUN (every
shape of the run); every rate must divide by the 16 client workers. A changed rate goes into all three boots.

Boot-time mitigations (page-table isolation, CPU buffer clearing, retpolines) are set when the kernel
boots, so on and off cannot alternate inside one run. The same configs therefore run unchanged in three
boots, A (mitigations on), B (`mitigations=off`, a one-shot boot entry) and C (on again); a run's own
arms are same-boot copies (A/A), and the price is the difference between boots, with A against C as the
boot-to-boot noise floor (table.py cross). Per-task mitigations that Linux can switch per process
(prctl PR_SET_SPECULATION_CTRL) are priced within one boot (h-spec).

Configs (in a directory named after the box), each with its one-round smoke:
  h-pl            the price list's shapes s (4 KB proxied, 5,200 req/s) and fh (direct response with 57
                  request and 52 response headers added, 8,000 req/s) on the published keep-alive rig:
                  base, base-A2 (A/A). Every boot.
  h-c1            plaintext HTTP/1.1, one request per connection (track E's churn rig, 1,600 req/s, 16
                  loopback addresses): ka (keep-alive, base), ka-A2 (A/A), c1. The syscall-heavy shape,
                  and the per-connection price (c1 - ka) in each boot. Every boot.
  h-spec          shape s at 5,200 req/s: base, ssbd (Speculative Store Bypass disabled for Envoy:
                  prctl PR_SPEC_STORE_BYPASS, PR_SPEC_DISABLE), ibp (indirect branch speculation disabled
                  for Envoy: STIBP while it runs and IBPB when switching to it). Within one boot (C).
  h-defer-deep    track E2b's TCP_DEFER_ACCEPT arms at 1,600 req/s, default idle states: c1 (base),
                  c1-A2 (A/A), c1-defer. Evidence: Envoy's CPUs enter C6.
  h-defer-c1only  the same arms, with C1E and C6 disabled on Envoy's CPUs and their SMT siblings for the
                  run (chain-h.sh sets and restores them; the harness only records the state). Evidence:
                  no C1E or C6 entry on Envoy's CPUs. Same boot as h-defer-deep.

The idle check of every config matches no process by its command line (`idle.procs` empty): idleness is
the load, the CPU busy share and the SUT CPUs' busy share, and the listener and admin ports must be free.
"""

import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)


def _load(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


e3 = _load("wave3e_make", os.path.join(ROOT, "examples", "wave3e", "make.py"))  # track E: churn rig, arms, evidence

RUNS = "~/epl/runs/wave5h"
CLIENT = e3.CLIENT  # Nighthawk 0.3.0, md5 310df412
ROUNDS = 6
SEEDS = {"h-pl": 101, "h-c1": 102, "h-spec": 103, "h-defer-deep": 104, "h-defer-c1only": 105}
PL_SHAPES = [
    {"name": "s", "kind": "proxied", "path": "/s", "body_bytes": 4096, "rps": 5200},
    {"name": "fh", "kind": "direct_headers", "path": "/fh", "body_bytes": 128, "request_headers_added": 57,
     "response_headers_added": 52, "rps": 8000},
]
KA = ["--prefetch-connections", "--max-pending-requests", "1000", "--experimental-h1-connection-reuse-strategy", "lru"]
EV_2XX = [{"stat": "http.ingress_http.downstream_rq_2xx", "scope": "leg", "min": 1}]
# /proc/<pid>/task/*/status, every Envoy thread (sysprobe.speculation_status), on a boot with the
# default mitigations: per-task control (prctl) for both features, off unless the task asks
SPEC_DEFAULT = {"store_bypass": "thread vulnerable", "indirect_branch": "conditional enabled"}
SPEC_ARMS = {"ssbd": {"store_bypass": "disable"}, "ibp": {"indirect_branch": "disable"}}
SPEC_WANT = {"ssbd": {"store_bypass": "thread mitigated"}, "ibp": {"indirect_branch": "conditional disabled"}}
# idle states the c1only run disables on Envoy's CPUs and their SMT siblings (C3 is off by the driver's
# default on this box); POLL and C1 (exit latency 2 us) stay
C1ONLY_OFF = ["C1E", "C6"]


def binary(box):
    b = box["binaries"]["x86_64"]
    return {"binary": b["binary"], "source": b["source"], "source_sha256": b["source_sha256"]}


def common(box, name, label=None):
    return {
        "name": name, "machine_label": label or box["machine_label"], "workdir": RUNS,
        "cpus": dict(box["cpus"]),
        "idle": {"max_load1": 8.0, "max_busy_pct": 2.0, "procs": []},
        "origin": {"mode": "docker", "port": 8092, "workers": 8, "image": box["origin_image"],
                   "platform": box["image_platform"]},
        "primary_metric": "cycles_total", "comparisons": "base", "adaptive": False, "warmup_legs": 1,
        "order": "williams", "order_seed": SEEDS[name.replace("smoke-", "")],
    }


def pl_base(box, name):
    c = common(box, name)
    c.update({
        "envoy": {"workers": 4, "listener_port": 10110, "admin_port": 9921, "exact_balance": True,
                  "log_level": "warn", "codec_type": "HTTP1"},
        "client": {"binary": CLIENT, "concurrency": 16, "connections_per_worker": 32, "warmup_s": 5,
                   "duration_s": 25, "idle_strategy": "poll", "open_loop": True, "extra_args": list(KA)},
        "measure": {"lead_in_s": 2, "window_s": 20, "perf": box["perf"], "kernel_net": True},
        "shapes": copy.deepcopy(PL_SHAPES),
    })
    return c


def pl_arm(box, name, spec=None):
    a = dict(binary(box), name=name, evidence=copy.deepcopy(EV_2XX))
    if spec:
        a["spec_ctrl"] = dict(SPEC_ARMS[spec])
    return a


def spec_evidence(arm_name):
    want = dict(SPEC_DEFAULT, **SPEC_WANT.get(arm_name, {}))
    return [{"stat": "envoy_speculation." + k, "scope": "field", "equals": v, "label": "every Envoy thread: " + v}
            for k, v in sorted(want.items())]


def c1_base(box, name, label=None):
    c = e3.base(box, name, 1600)
    c.update(common(box, name, label))
    c["client"]["binary"] = CLIENT
    return c


IDLE_DEEP = [{"stat": "cpuidle_residency.sum.C6.entries_per_s", "scope": "field", "min": 100,
              "label": "Envoy's CPUs enter C6 (default idle states)"}]
IDLE_C1ONLY = [{"stat": "cpuidle_residency.sum.%s.entries_per_s" % s, "scope": "field", "equals": 0, "tol_abs": 0,
                "label": "no %s entry on Envoy's CPUs (disabled for the run)" % s} for s in C1ONLY_OFF]


def runs(box):
    out = {}
    # h-pl: the published shapes, a same-boot A/A
    pl = [pl_arm(box, "base"), pl_arm(box, "base-A2")]
    out["h-pl"] = ("base", pl_base, pl, None)
    # h-c1: track E's e-plain arms, verbatim (ka base, ka-A2, c1)
    c1 = [e3.arm(box, "ka", churn=False), e3.arm(box, "ka-A2", churn=False), e3.arm(box, "c1")]
    out["h-c1"] = ("ka", c1_base, c1, None)
    # h-spec: per-task speculation control on shape s, within one boot
    sp = [pl_arm(box, "base"), pl_arm(box, "ssbd", "ssbd"), pl_arm(box, "ibp", "ibp")]
    for a in sp:
        a["evidence"] += spec_evidence(a["name"])
    out["h-spec"] = ("base", pl_base, sp, [s for s in PL_SHAPES if s["name"] == "s"])
    # TCP_DEFER_ACCEPT against the idle states: E2b's arms without ka
    e2b = {a["name"]: a for a in e3.runs(box)["e2b-plain"][1]}
    deep = [copy.deepcopy(e2b[n]) for n in ("c1", "c1-A2", "c1-defer")]
    for a in deep:
        a["evidence"] += copy.deepcopy(IDLE_DEEP)
    pinned = [copy.deepcopy(e2b[n]) for n in ("c1", "c1-A2", "c1-defer")]
    for a in pinned:
        a["evidence"] += copy.deepcopy(IDLE_C1ONLY)
    out["h-defer-deep"] = ("c1", c1_base, deep, None)
    out["h-defer-c1only"] = ("c1", c1_base, pinned, None)
    return out


def c1only_label(box):
    return box["machine_label"].replace("default idle states", "C1E and C6 disabled on Envoy's CPUs and their "
                                        "SMT siblings for this run (C1 only; C3 off by the driver's default)")


def apply_rates(c, stem, rates):
    for sh in c["shapes"]:
        r = (rates or {}).get("%s.%s" % (stem, sh["name"]), (rates or {}).get(stem))
        if r is not None:
            if int(r) % 16:
                raise SystemExit("rate %s for %s.%s does not divide by the 16 client workers" % (r, stem, sh["name"]))
            sh["rps"] = int(r)


def configs(box, rates=None):
    known = set(runs(box))
    for k in rates or {}:
        if k.split(".")[0] not in known:
            raise SystemExit("--rates: unknown run %r" % k)
    out = {}
    for stem, (b, mk, arms, shapes) in runs(box).items():
        for smoke in (True, False):
            name = ("smoke-" if smoke else "") + stem
            c = mk(box, name, c1only_label(box)) if stem == "h-defer-c1only" else mk(box, name)
            if shapes is not None:
                c["shapes"] = copy.deepcopy(shapes)
            apply_rates(c, stem, rates)
            n = 1 if smoke else ROUNDS
            c.update(arms=copy.deepcopy(arms), base_arm=b, rounds=n, rounds_block=n, rounds_max=n)
            if smoke:
                c.update(smoke=True, evidence_mode="record", order="fixed")
            out[name + ".json"] = c
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", default=os.path.join(ROOT, "examples", "stats-flush", "boxes", "bench-x86_64.json"))
    ap.add_argument("--rates", default=None, help="JSON {RUN.SHAPE or RUN: req/s}")
    a = ap.parse_args()
    with open(a.box) as f:
        box = json.load(f)
    d = os.path.join(HERE, box["name"])
    os.makedirs(d, exist_ok=True)
    cfgs = configs(box, json.loads(a.rates) if a.rates else None)
    for fn, c in sorted(cfgs.items()):
        with open(os.path.join(d, fn), "w") as f:
            json.dump(c, f, indent=1, sort_keys=True)
            f.write("\n")
    print("%s: %d configs (%s)" % (box["name"], len(cfgs), ", ".join(sorted(cfgs))))


if __name__ == "__main__":
    main()
