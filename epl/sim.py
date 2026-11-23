"""Simulated backend for dry runs: exercises schedule, validity gates, statistics and reports
without touching the machine.

Per arm, `sim_factor` (default 1.0) scales the true cost and `sim_cycles_factor`
scales cycles only. Noise per leg: `sim_ins_noise` (default 0.2%) on
instructions, `sim_cycles_noise` (default 1.4%, about the v2 bench box) on user and kernel cycles, plus a
run-position effect so the order matters.
`sim_faults` maps a leg id to one fault: rate, overflow, headroom, port, idle,
non2xx, uneven (one worker idle), noworkers (no wrk: thread), nosched (no
/proc/schedstat), evidence (an evidence item fails); that leg comes back with the
matching field set. Evidence is not evaluated in a dry run (no counters).
"""

import random

from . import validity

BASE = {"instructions_u": 170e3, "instructions_k": 60e3, "cycles_u": 150e3, "cycles_k": 120e3}


class SimBackend:
    def __init__(self, exp, run_dir, log, seed=None):
        self.exp = exp
        self.log = log
        self.rng = random.Random(exp.get("sim_seed", 1) if seed is None else seed)
        self.faults = exp.get("sim_faults", {})
        self.pos = 0

    def metadata(self, exp, btxt):
        return {"harness": "dry-run", "machine": {"cpu_model": "simulated"}, "cpus": exp["cpus"],
                "arms": {a["name"]: {"md5": "sim", "version": "sim"} for a in exp["arms"]},
                "started_utc": "sim"}

    def run_idle_leg(self, arm, shape, rnd, leg_id):
        """An idle leg of the stats row: the main thread at 0.5 ms/s plus `sim_flush_ms` per
        flush (arm; default 10 ms) at the arm's flush interval; flush-off has no flushes."""
        r = self.rng
        sf = (arm.get("settings") or {}).get("stats_flush") or {}
        interval = None if sf.get("on_admin") else float(sf.get("interval_s", 5))
        d = float(arm.get("sim_flush_ms", 10.0)) * r.gauss(1.0, float(self.exp.get("sim_cycles_noise", 0.014)))
        base = 0.5 * r.gauss(1.0, 0.01)
        main = {"samples": 1000, "bursts": 0, "sampler_missing": 0}
        if interval:
            per = interval + d / 1e3
            main.update(bursts=int(20 // per), periods=int(20 // per) - 1, period_s=per,
                        run_ms_per_period=d + base * per, run_ms_per_s=d / per + base,
                        stall_ms_p50=d, stall_ms_max=d * 1.1, burst_count_error=0)
        else:
            main["run_ms_per_s"] = base
        cps = main["run_ms_per_s"] * 2.3e6
        k = ((arm.get("settings") or {}).get("stats_clusters") or {}).get("count", 0)
        m = {"leg_id": leg_id, "arm": arm["name"], "shape": shape["name"], "round": rnd, "idle_leg": True,
             "target_rps": 0,
             "idle_ok": True, "preflight_ok": True, "pinning_ok": True, "perf_ok": True, "main_tid_ok": True,
             "sut_foreign_cpus": 0.0, "sut_sibling_cpus": 0.0, "envoy_exit": 0, "perf_min_running_pct": 100.0,
             "flush_interval_s": interval, "main": main, "stats_total": 110 * k + 300,
             "main_perf": {"cycles_per_s": cps, "cycles_u_per_s": cps * 0.7, "cycles_k_per_s": cps * 0.3,
                           "cycles_per_period": cps * main.get("period_s", 1.0)},
             "ready": {"max_ms": 2.0 + d}, "memory": {"vm_hwm_kb_after": 100000 + k * 50}}
        if arm.get("evidence") is not None:
            m["evidence"] = {"ok": True, "gate": False, "simulated": True, "items": [], "failed": []}
        m["verdict"] = validity.verdict(m, self.exp["validity"])
        return m

    def run_leg(self, arm, shape, rnd, bootstrap_path, leg_id):
        if shape.get("kind") == "idle":
            return self.run_idle_leg(arm, shape, rnd, leg_id)
        f = float(arm.get("sim_factor", 1.0))
        fc = f * float(arm.get("sim_cycles_factor", 1.0))
        ni = float(self.exp.get("sim_ins_noise", 0.002))
        nc = float(self.exp.get("sim_cycles_noise", 0.014))
        self.pos += 1
        drift = 1.0 + 0.02 * ((self.pos % 2) - 0.5)  # alternating position effect
        r = self.rng
        iu = BASE["instructions_u"] * f * r.gauss(1.0, ni)
        cu = BASE["cycles_u"] * fc * drift * r.gauss(1.0, nc)
        ck = BASE["cycles_k"] * fc * drift * r.gauss(1.0, nc)
        tgt = shape["rps"]
        m = {"leg_id": leg_id, "arm": arm["name"], "shape": shape["name"], "round": rnd, "target_rps": tgt,
             "idle_ok": True, "preflight_ok": True, "pinning_ok": True, "perf_ok": True,
             "responses": int(tgt * 20), "sut_rate_2xx": tgt * r.gauss(1.0, 0.001), "sut_non2xx": 0,
             "client_overflow": {}, "client_non2xx": {}, "client_headroom": 0.7, "sut_busy": 0.3,
             "per_req": {"instructions_u": iu, "instructions_k": BASE["instructions_k"], "cycles_u": cu,
                         "cycles_k": ck, "cycles_total": cu + ck, "task_clock_us": (cu + ck) / 2300.0},
             "latency_us": {"p50": 200 * f * r.gauss(1, 0.02), "p99": 400 * f * r.gauss(1, 0.05)},
             "sut_foreign_cpus": 0.002, "sut_sibling_cpus": 0.0}
        nw = int(self.exp["envoy"]["workers"])
        m.update(envoy_workers=nw, envoy_worker_max_share=round(1.02 / nw, 4),
                 envoy_worker_min_share=round(0.98 / nw, 4))
        fault = self.faults.get(leg_id)
        if fault == "rate":
            m["sut_rate_2xx"] = tgt * 0.97
        elif fault == "overflow":
            m["client_overflow"] = {"benchmark.pool_overflow": 3}
        elif fault == "headroom":
            m["client_headroom"] = 0.05
        elif fault == "port":
            m["preflight_ok"] = False
            m["preflight_detail"] = "port 10110 already in use"
        elif fault == "idle":
            m["idle_ok"] = False
        elif fault == "uneven":
            m.update(envoy_worker_max_share=round(1.0 / (nw - 1), 4), envoy_worker_min_share=0.0)
        elif fault == "noworkers":
            m.update(envoy_worker_max_share=None, envoy_worker_min_share=None,
                     envoy_worker_probe="no wrk: thread in /proc/1/task")
        elif fault == "nosched":
            m.update(sut_foreign_cpus=None, sut_sibling_cpus=None, sched_probe="simulated: no /proc/schedstat")
        elif fault == "non2xx":
            m["client_non2xx"] = {"benchmark.http_5xx": 2}
            m["sut_non2xx"] = 2
        # a dry run has no steal time to read; report none, so a steal gate (cloud VMs) passes as on an idle host
        m.setdefault("steal_share", 0.0)
        if arm.get("evidence") is not None:
            # no counters in a dry run: evidence is recorded as not evaluated, never gated,
            # unless the fault "evidence" asks for a failing item
            m["evidence"] = {"ok": fault != "evidence", "gate": fault == "evidence", "simulated": True, "items": [],
                             "failed": ["simulated: evidence item failed"] if fault == "evidence" else []}
        m["verdict"] = validity.verdict(m, self.exp["validity"])
        return m
