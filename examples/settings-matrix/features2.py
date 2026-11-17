#!/usr/bin/env python3
"""Feature rows, session 2: new filters, each against the settings-matrix baseline, with
evidence on every leg.

    python3 examples/settings-matrix/features2.py [write] [RATES_JSON]
    python3 examples/settings-matrix/features2.py budget SMOKE_ROOT
    python3 examples/settings-matrix/features2.py cap RUN SMOKE_ROOT
    python3 examples/settings-matrix/features2.py has-floor RUN_DIR

RATES_JSON (from calibration) may set the rates of j16, j16-a, j16-b, j16-c, s-9600,
fh-13600 and `f_warmup_s` (run F's warm-up, 5 s unless the JIT check asks for 15).

Configs (in features2/):

  aa-2.json        the A/A of the session, run first: base and base-A2 on s, fh and j16;
                   16 rounds minimum, blocks of 4, cap 32, until every row is at 1.0%.
  run-f.json       rows 15 and 16 in one run: filter-off, lua-empty, lua-header,
                   wasm-empty, wasm-header on s and fh; 20/10/30; 0.8% on s, 1.5% on fh.
  14-compression.json   comp-off, gzip, brotli, zstd on j4 and j16 (synthetic JSON,
                   Accept-Encoding: gzip, br, zstd on every arm); 16/8/24; 1.5%; minor
                   faults counted per request.
  lc-j16.json      the j16 reference (comp-off and a second copy) at three higher rates,
                   j16-a, j16-b, j16-c; 12 fixed rounds; sizes row 14's load gap
                   (internal, exploratory).
  14b.json         gzip in the chain on the stock s body (not a compressible type), client
                   sends Accept-Encoding; 16/4/32; 0.8%. Optional.
  lc-sfh.json      base and base-A2 at s-9600 and fh-13600; 12 fixed rounds. Optional, cut first.
  jit-check.json   lua-header and wasm-header with a 5 s and a 30 s warm-up, 2 rounds;
                   compared on user instructions per request (features_table2.py jit).
  smoke-*.json     two rounds of every arm of every run, evidence recorded, not gated.

Order seed 22. Rows 15, 16 and 14 take the floor from AA-2's base-A2 arm (same session,
an earlier run); j4 and s-ae borrow the s A/A (stated in the tables). Evidence counter
names are the best reading of v1.40.2's stats; the smoke's saved /stats is the source of
truth. Items with a `ref` are frozen from the smoke legs by `epl evidence-check --freeze`
(run-session-2.sh does it) and the queue runs the frozen configs.
"""

import json
import os
import sys

import features as F
import make

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "features2")
REL = "examples/settings-matrix/features2"  # relative to the harness root, as configs carry it
RUNS = "~/epl/runs/wk5-s2"
ORDER_SEED = 22
AA_FLOOR = {"floor_from": RUNS + "/aa-2/results.json", "floor_arm": "base-A2"}
ACCEPT = ["--request-header", "accept-encoding:gzip, br, zstd"]
MANDATORY = ["aa-2", "run-f", "14-compression", "lc-j16"]
OPTIONAL = ["14b", "lc-sfh"]  # run in this order; lc-sfh is cut first
SESSION_STOP_S = F.SESSION_STOP_S
ASK_LEAD_ABOVE_S = F.ASK_LEAD_ABOVE_S
HEADER_BYTES = len("x-epl-filter: 1\r\n")  # 17
# the default event list plus minor page faults (a software event: no counter is used)
PERF_EVENTS_FAULTS = ("instructions:u,cycles:u,cycles:k,instructions:k,task-clock,context-switches,"
                      "cpu-migrations,minor-faults")


def _read(rel):
    with open(os.path.join(HERE, rel), "rb") as f:
        return f.read()


def sums(rel_dir, name):
    for line in _read(os.path.join(rel_dir, "SHA256SUMS")).decode().splitlines():
        h, _, n = line.strip().partition("  ")
        if n == name:
            return h
    raise KeyError(name)


BODIES = {"j4": ("j4.json", 4096), "j16": ("j16.json", 16384)}
LUA = {k: _read(os.path.join("features2", "lua", k + ".lua")).decode() for k in ("empty", "header")}
WASM = {k: {"file": "%s/wasm/out/epl_wasm_%s.wasm" % (REL, k),
            "sha256": sums("features2/wasm", "epl_wasm_%s.wasm" % k), "runtime": "envoy.wasm.runtime.v8"}
        for k in ("empty", "header")}

# ---------------------------------------------------------------- evidence

Z = F.Z
zero = F.zero
DOWN_TX = "http.ingress_http.downstream_cx_tx_bytes_total"
UP_TX = "cluster.origin.upstream_cx_tx_bytes_total"
PER_RESP = "field:responses_raw"
NO_FILTERS = [{"stat": "http.ingress_http.compressor.*", "absent": True, "label": "no compressor stats"},
              {"stat": "http.ingress_http.lua.*", "absent": True, "label": "no Lua stats"},
              {"stat": "wasm.*", "absent": True, "label": "no Wasm stats"}]
J16_SHAPES = ["j16", "j16-a", "j16-b", "j16-c"]


def body_min(shapes, size):
    return {"stat": DOWN_TX, "per": PER_RESP, "min": size, "shape": shapes,
            "label": "bytes sent downstream per request >= the %d-byte body (the origin did not compress)" % size}


EV_BASE = NO_FILTERS + [body_min(["s", "s-ae", "s-9600"], 4096), body_min(J16_SHAPES, 16384)]
EV_COMP_OFF = [{"stat": "http.ingress_http.compressor.*", "absent": True, "label": "no compressor stats"},
               body_min(["j4", "s-ae"], 4096), body_min(J16_SHAPES, 16384)]


def comp_stat(lib, name):
    return "http.ingress_http.compressor.epl.%s.%s" % (lib, name)


def ev_comp(lib):
    return [dict({"stat": comp_stat(lib, "compressed"), "per_request": 1.0, "tol": 0.002}),
            zero(comp_stat(lib, "not_compressed")),
            {"stat": comp_stat(lib, "total_uncompressed_bytes"), "per_request": 4096, "tol": 0.005, "shape": "j4"},
            {"stat": comp_stat(lib, "total_uncompressed_bytes"), "per_request": 16384, "tol": 0.005, "shape": "j16"},
            {"stat": comp_stat(lib, "total_compressed_bytes"), "ref": {"arm": "self"}, "tol": 0.02,
             "label": "compressed bytes per request within 2% of the smoke mean"}]


EV_GZIP_IDLE = [{"stat": comp_stat("gzip", "not_compressed"), "per_request": 1.0, "tol": 0.002},
                zero(comp_stat("gzip", "compressed"))]


def bytes_ref(offset):
    return [{"stat": DOWN_TX, "ref": {"arm": "filter-off", "offset": offset}, "tol_abs": 3,
             "label": "bytes sent downstream per request = filter-off %+d" % offset},
            {"stat": UP_TX, "ref": {"arm": "filter-off", "offset": offset}, "tol_abs": 3, "shape": "s",
             "label": "bytes sent upstream per request = filter-off %+d" % offset}]


EV_FILTER_OFF = NO_FILTERS + bytes_ref(0)
LUA_OK = [zero("http.ingress_http.lua.errors")]
WASM_OK = [{"stat": "wasm.envoy.wasm.runtime.v8.active", "scope": "leg", "min": 4,
            "label": "Wasm VMs active (at least one per worker)"}]
EV = {
    "base": EV_BASE, "base-A2": EV_BASE,
    "filter-off": EV_FILTER_OFF,
    "lua-empty": LUA_OK + bytes_ref(0), "lua-header": LUA_OK + bytes_ref(HEADER_BYTES),
    "wasm-empty": WASM_OK + bytes_ref(0), "wasm-header": WASM_OK + bytes_ref(HEADER_BYTES),
    "comp-off": EV_COMP_OFF, "comp-off-A2": EV_COMP_OFF,
    "gzip": ev_comp("gzip"), "brotli": ev_comp("brotli"), "zstd": ev_comp("zstd"),
}
SETTINGS = {
    "lua-empty": {"lua": {"inline": LUA["empty"]}}, "lua-header": {"lua": {"inline": LUA["header"]}},
    "wasm-empty": {"wasm": WASM["empty"]}, "wasm-header": {"wasm": WASM["header"]},
    "gzip": {"compressor": {"library": "gzip"}}, "brotli": {"compressor": {"library": "brotli"}},
    "zstd": {"compressor": {"library": "zstd"}},
}


def arm(name, ev=None):
    return F.arm(name, SETTINGS.get(name), ev=EV[name] if ev is None else ev)


# ---------------------------------------------------------------- configs

def shapes(rates):
    S = make.shapes(rates)
    r = lambda n, d: int(rates.get(n, d))  # noqa: E731
    ramp = ["--rate-limiter-plugin-config", F.rel.RAMP]

    def j(name, key, rps, extra=(), lead_in=None):
        fn, size = BODIES[key]
        sh = {"name": name, "path": "/" + key, "kind": "proxied", "body_bytes": size, "rps": rps,
              "body_file": "%s/bodies/%s" % (REL, fn), "body_sha256": sums("features2/bodies", fn),
              "content_type": "application/json", "client_extra_args": list(ACCEPT) + list(extra)}
        if lead_in:
            sh["lead_in_s"] = lead_in
        return sh

    return {
        "s": S["s"], "fh": S["fh"],
        "j4": j("j4", "j4", r("j4", 5200)),
        # calibrated: the gzip arm at or under 60% busy
        "j16": j("j16", "j16", r("j16", 2400)),
        # the j16 reference at about 30%, 45% and 60% busy (calibrated); ramped above the first
        "j16-a": j("j16-a", "j16", r("j16-a", 5200)),
        "j16-b": j("j16-b", "j16", r("j16-b", 7600), ramp, 3),
        "j16-c": j("j16-c", "j16", r("j16-c", 10400), ramp, 3),
        "s-ae": dict(S["s"], name="s-ae", client_extra_args=list(ACCEPT)),
        "s-9600": dict(S["s"], name="s-9600", rps=r("s-9600", 9600)),
        "fh-13600": dict(S["fh"], name="fh-13600", rps=r("fh-13600", 13600)),
        "s-wu5": dict(S["s"], name="s-wu5", warmup_s=5),
        "s-wu30": dict(S["s"], name="s-wu30", warmup_s=30),
    }


def base_cfg():
    b = F.base_cfg()
    b.update(workdir=RUNS, order_seed=ORDER_SEED)
    return b


def run_configs(rates):
    S = shapes(rates)
    T = lambda n, t: dict(S[n], stop_target_half_width_pct=t)  # noqa: E731
    out = {}

    def run(fname, name, arm_names, shp, **kw):
        c = base_cfg()
        c.update(name=name, base_arm=arm_names[0], arms=[arm(a) for a in arm_names], shapes=shp)
        for k, v in kw.items():
            if isinstance(v, dict) and isinstance(c.get(k), dict):
                c[k] = dict(c[k], **v)
            else:
                c[k] = v
        out[fname] = c

    fixed12 = dict(rounds=12, rounds_block=12, rounds_max=12, adaptive=False)
    run("aa-2.json", "wk5-aa-2", ["base", "base-A2"], [S["s"], S["fh"], S["j16"]],
        rounds=16, rounds_block=4, rounds_max=32, stop={"target_half_width_pct": 1.0})
    run("run-f.json", "wk5-run-f", ["filter-off", "lua-empty", "lua-header", "wasm-empty", "wasm-header"],
        [T("s", 0.8), T("fh", 1.5)],
        confirmatory=[["lua-header", "filter-off"], ["wasm-header", "filter-off"]],
        rounds=20, rounds_block=10, rounds_max=30, stop={"target_half_width_pct": 1.5, "rows": "confirmatory"},
        client=dict(make.BASE["client"], warmup_s=int(rates.get("f_warmup_s", 5))), **AA_FLOOR)
    run("14-compression.json", "wk5-compression", ["comp-off", "gzip", "brotli", "zstd"], [S["j4"], S["j16"]],
        confirmatory=[["gzip", "comp-off"], ["brotli", "comp-off"], ["zstd", "comp-off"]],
        rounds=16, rounds_block=8, rounds_max=24, stop={"target_half_width_pct": 1.5, "rows": "confirmatory"},
        measure=dict(make.BASE["measure"], perf_events=PERF_EVENTS_FAULTS), **AA_FLOOR)
    run("lc-j16.json", "wk5-lc-j16", ["comp-off", "comp-off-A2"], [S["j16-a"], S["j16-b"], S["j16-c"]], **fixed12)
    run("14b.json", "wk5-compressor-idle", ["comp-off", "gzip"], [T("s-ae", 0.8)],
        rounds=16, rounds_block=4, rounds_max=32, stop={"target_half_width_pct": 0.8}, **AA_FLOOR)
    out["14b.json"]["arms"][1]["evidence"] = json.loads(json.dumps(EV_GZIP_IDLE))
    run("lc-sfh.json", "wk5-lc-sfh", ["base", "base-A2"], [S["s-9600"], S["fh-13600"]], **fixed12)
    run("jit-check.json", "wk5-jit-check", ["lua-header", "wasm-header"], [S["s-wu5"], S["s-wu30"]],
        rounds=2, rounds_block=2, rounds_max=2, adaptive=False, evidence_mode="record")
    for a in out["jit-check.json"]["arms"]:
        a["evidence"] = [it for it in a["evidence"] if "ref" not in it]  # no smoke values to freeze from
    return out


# (smoke file, source run, arms, shapes)
SMOKES = [
    ("smoke-aa.json", "aa-2.json", ["base", "base-A2"], ["s", "fh", "j16"]),
    ("smoke-f1.json", "run-f.json", ["filter-off", "lua-empty"], ["s", "fh"]),
    ("smoke-f2.json", "run-f.json", ["lua-header", "wasm-empty"], ["s", "fh"]),
    ("smoke-f3.json", "run-f.json", ["wasm-header", "filter-off"], ["s", "fh"]),
    ("smoke-14a.json", "14-compression.json", ["comp-off", "gzip"], ["j4", "j16"]),
    ("smoke-14b.json", "14-compression.json", ["brotli", "zstd"], ["j4", "j16"]),
    ("smoke-lc.json", "lc-j16.json", ["comp-off", "comp-off-A2"], ["j16-a"]),
    ("smoke-14bidle.json", "14b.json", ["comp-off", "gzip"], ["s-ae"]),
    ("smoke-sfh.json", "lc-sfh.json", ["base", "base-A2"], ["s-9600", "fh-13600"]),
]
# the smokes each run's evidence is frozen from and checked against
CHECK = {"aa-2": ["smoke-aa"], "run-f": ["smoke-f1", "smoke-f2", "smoke-f3"],
         "14-compression": ["smoke-14a", "smoke-14b"], "lc-j16": ["smoke-lc"], "14b": ["smoke-14bidle"],
         "lc-sfh": ["smoke-sfh"]}


def configs(rates):
    out = run_configs(rates)
    for fn, src, arms, shp in SMOKES:
        c = json.loads(json.dumps(out[src]))
        c.update(name="wk5-" + fn[:-5], base_arm=arms[0],
                 arms=[a for n in arms for a in c["arms"] if a["name"] == n],
                 shapes=[s for n in shp for s in c["shapes"] if s["name"] == n],
                 rounds=2, rounds_block=2, rounds_max=2, adaptive=False, evidence_mode="record")
        for k in ("floor_from", "floor_arm", "confirmatory", "stop"):
            c.pop(k, None)
        out[fn] = c
    return out


# ---------------------------------------------------------------- session helpers

def budget(smoke_root, out=sys.stdout, cfg_dir=OUT):
    spl, n = F.seconds_per_leg(smoke_root)
    caps = {}
    out.write("seconds per leg (smoke, %d gaps): %.1f\n" % (n, spl))
    for r in MANDATORY + OPTIONAL:
        lm = F.legs_max(os.path.join(cfg_dir, r + ".json"))
        caps[r] = lm * spl
        out.write("%-16s %4d legs at the cap  worst case %5.2f h%s\n" % (
            r, lm, caps[r] / 3600, "  (optional)" if r in OPTIONAL else ""))
    mand = sum(caps[r] for r in MANDATORY)
    out.write("mandatory worst case %.2f h (ask the lead above %.2f h); with 14b %.2f h; with both optional "
              "%.2f h; stop at %.0f h\n" % (mand / 3600, ASK_LEAD_ABOVE_S / 3600, (mand + caps["14b"]) / 3600,
                                            (mand + caps["14b"] + caps["lc-sfh"]) / 3600, SESSION_STOP_S / 3600))
    return mand, caps


def main(argv):
    cmd = argv[0] if argv and argv[0] in ("write", "budget", "has-floor", "cap", "check-list") else "write"
    args = argv[1:] if argv and argv[0] == cmd else argv
    if cmd == "budget":
        mand, _ = budget(args[0], cfg_dir=args[1] if len(args) > 1 else OUT)
        return 3 if mand > ASK_LEAD_ABOVE_S else 0
    if cmd == "cap":
        spl, _ = F.seconds_per_leg(args[1])
        d = args[2] if len(args) > 2 else OUT
        print(int(F.legs_max(os.path.join(d, args[0] + ".json")) * spl))
        return 0
    if cmd == "has-floor":
        ok, why = F.has_floor(args[0])
        print(why)
        return 0 if ok else 1
    if cmd == "check-list":
        # check-list RUN: the smoke directories of that run's evidence check
        print(" ".join(CHECK[args[0]]))
        return 0
    rates = {}
    if args:
        with open(args[0]) as f:
            rates = json.load(f)
    os.makedirs(OUT, exist_ok=True)
    for fn, c in configs(rates).items():
        with open(os.path.join(OUT, fn), "w") as f:
            json.dump(c, f, indent=1)
            f.write("\n")
        print(fn)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
