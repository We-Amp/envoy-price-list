"""Wave 5 track H: per-task speculation control (spec_ctrl), the speculation status probe, the boot
state record and check, the wave5h configs, the cross-boot and defer tables, and the one-shot boot
entry generator."""
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from epl import evidence, experiment, sysprobe

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "..", "examples", "wave5h")
CFG = os.path.join(EX, "bench-x86_64")
SHA = "1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bootstate = _load("wave5h_bootstate", os.path.join(EX, "bootstate.py"))
table = _load("wave5h_table", os.path.join(EX, "table.py"))


def cfg(name):
    return experiment.load(os.path.join(CFG, name))


class SpecCtrlTest(unittest.TestCase):
    def test_calls(self):
        self.assertEqual(sysprobe.spec_ctrl_calls({"store_bypass": "disable"}), [(53, 0, 4)])
        self.assertEqual(sysprobe.spec_ctrl_calls({"indirect_branch": "disable", "store_bypass": "disable"}),
                         [(53, 1, 4), (53, 0, 4)])
        self.assertEqual(sysprobe.spec_ctrl_calls(None), [])
        for bad in ({"l1d_flush": "disable"}, {"store_bypass": "enable"}, {"store_bypass": 1}):
            with self.assertRaises(ValueError):
                sysprobe.spec_ctrl_calls(bad)

    def test_validate(self):
        exp = cfg("h-spec.json")
        self.assertEqual(experiment.validate(exp, allow_short=True), [])
        for bad in ({}, {"store_bypass": "on"}, "disable", {"retbleed": "disable"}):
            e = copy.deepcopy(exp)
            e["arms"][1]["spec_ctrl"] = bad
            self.assertTrue(any("spec_ctrl" in x for x in experiment.validate(e, allow_short=True)), bad)

    def test_preexec_without_calls_runs_then(self):
        seen = []
        sysprobe.spec_ctrl_preexec({}, then=lambda: seen.append(1))()
        self.assertEqual(seen, [1])

    def test_status(self):
        with tempfile.TemporaryDirectory() as d:
            for tid, ssb in (("10", "thread mitigated"), ("11", "thread mitigated")):
                os.makedirs(os.path.join(d, "10", "task", tid))
                with open(os.path.join(d, "10", "task", tid, "status"), "w") as f:
                    f.write("Name:\tenvoy\nSpeculation_Store_Bypass:\t%s\nSpeculationIndirectBranch:\tconditional enabled\n" % ssb)
            st = sysprobe.speculation_status(10, root=d)
            self.assertEqual(st, {"store_bypass": "thread mitigated", "indirect_branch": "conditional enabled", "threads": 2})
            with open(os.path.join(d, "10", "task", "11", "status"), "w") as f:
                f.write("Speculation_Store_Bypass:\tthread vulnerable\n")
            st = sysprobe.speculation_status(10, root=d)
            self.assertEqual(st["store_bypass"], "mixed: thread mitigated | thread vulnerable")
            self.assertEqual(sysprobe.speculation_status(99, root=d)["store_bypass"], "unreadable")
        m = {"envoy_speculation": {"store_bypass": "thread mitigated"}}
        it = {"stat": "envoy_speculation.store_bypass", "scope": "field", "equals": "thread mitigated"}
        self.assertTrue(evidence.check_item(m, it)["ok"])
        self.assertFalse(evidence.check_item({"envoy_speculation": {"store_bypass": "thread vulnerable"}}, it)["ok"])


VUL_ON = {"meltdown": "Mitigation: PTI", "mds": "Mitigation: Clear CPU buffers; SMT vulnerable",
          "spectre_v2": "Mitigation: Retpolines; IBPB: conditional", "spec_store_bypass":
          "Mitigation: Speculative Store Bypass disabled via prctl", "tsx_async_abort": "Mitigation: Clear CPU buffers",
          "mmio_stale_data": "Mitigation: Clear CPU buffers", "l1tf": "Mitigation: PTE Inversion", "srbds": "Not affected"}
VUL_OFF = dict(VUL_ON, meltdown="Vulnerable", mds="Vulnerable; SMT vulnerable", spectre_v2="Vulnerable",
               spec_store_bypass="Vulnerable", tsx_async_abort="Vulnerable", mmio_stale_data="Vulnerable")


def fake_root(d, vul, cmdline, boot_id, c6_disable="0", gov="performance"):
    def w(p, v):
        p = os.path.join(d, p)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(v + "\n")
    for n, v in vul.items():
        w("sys/devices/system/cpu/vulnerabilities/" + n, v)
    w("proc/cmdline", cmdline)
    w("proc/sys/kernel/random/boot_id", boot_id)
    w("proc/cpuinfo", "processor\t: 0\nmicrocode\t: 0xb000040\n")
    w("proc/version", "Linux version 6.8.0-151-generic")
    for c in (0, 1):
        w("sys/devices/system/cpu/cpu%d/cpufreq/scaling_governor" % c, gov)
        w("sys/devices/system/cpu/cpu%d/cpufreq/scaling_max_freq" % c, "2300000")
        for i, (name, dis) in enumerate((("POLL", "0"), ("C1", "0"), ("C3", "1"), ("C6", c6_disable))):
            w("sys/devices/system/cpu/cpu%d/cpuidle/state%d/name" % (c, i), name)
            w("sys/devices/system/cpu/cpu%d/cpuidle/state%d/disable" % (c, i), dis)
            w("sys/devices/system/cpu/cpu%d/cpuidle/state%d/latency" % (c, i), str(i))
    w("sys/devices/system/cpu/intel_pstate/no_turbo", "1")


CMD = "BOOT_IMAGE=/vmlinuz-6.8.0-151-generic root=/dev/mapper/vg-lv ro"


class BootStateTest(unittest.TestCase):
    def rec(self, **kw):
        with tempfile.TemporaryDirectory() as d:
            fake_root(d, **kw)
            return bootstate.record(d)

    def test_on_off_and_ref(self):
        a = self.rec(vul=VUL_ON, cmdline=CMD, boot_id="aaa")
        self.assertEqual(a["boot_image"], "/vmlinuz-6.8.0-151-generic")
        self.assertEqual(a["cpuidle"]["states"]["state2"], {"name": "C3", "latency_us": "2", "disable_over_cpus": {"1": 2}})
        self.assertEqual(bootstate.check(a, "on")[0], 0)
        b = self.rec(vul=VUL_OFF, cmdline=CMD + " mitigations=off", boot_id="bbb")
        self.assertEqual(b["kernel_cmdline_mitigation_args"], ["mitigations=off"])
        self.assertEqual(bootstate.check(b, "off", ref=a, others=[a])[0], 0)
        # off expected, but the boot came up with the default line
        self.assertEqual(bootstate.check(a, "off")[0], 13)
        # mitigations=off on the line but one mitigation still active
        half = self.rec(vul=dict(VUL_OFF, mds=VUL_ON["mds"]), cmdline=CMD + " mitigations=off", boot_id="ccc")
        self.assertEqual(bootstate.check(half, "off")[0], 13)
        # on expected: an on-boot with a different mitigation text than the reference
        c = self.rec(vul=dict(VUL_ON, spectre_v2="Mitigation: IBRS"), cmdline=CMD, boot_id="ddd")
        self.assertEqual(bootstate.check(c, "on", ref=a)[0], 13)
        # on expected, but a mitigation argument on the line
        self.assertEqual(bootstate.check(self.rec(vul=VUL_ON, cmdline=CMD + " nopti", boot_id="e"), "on")[0], 13)

    def test_not_comparable_and_no_reboot(self):
        a = self.rec(vul=VUL_ON, cmdline=CMD, boot_id="aaa")
        c6 = self.rec(vul=VUL_ON, cmdline=CMD, boot_id="bbb", c6_disable="1")
        rc, msgs = bootstate.check(c6, "on", ref=a)
        self.assertEqual(rc, 14)
        self.assertTrue(any("cpuidle.states.state3.disable_over_cpus" in m for m in msgs), msgs)
        gov = self.rec(vul=VUL_ON, cmdline=CMD, boot_id="bbb", gov="powersave")
        self.assertEqual(bootstate.check(gov, "on", ref=a)[0], 14)
        other_root = self.rec(vul=VUL_ON, cmdline=CMD.replace("vg-lv", "sdb1"), boot_id="bbb")
        self.assertEqual(bootstate.check(other_root, "on", ref=a)[0], 14)
        same = self.rec(vul=VUL_ON, cmdline=CMD, boot_id="aaa")
        self.assertEqual(bootstate.check(same, "on", ref=a, others=[a])[0], 15)


VUL_K_ON = {"meltdown": "Not affected", "mds": "Not affected", "l1tf": "Not affected",
            "spectre_v1": "Mitigation: usercopy/swapgs barriers and __user pointer sanitization",
            "spectre_v2": "Mitigation: Enhanced / Automatic IBRS; IBPB: conditional; PBRSB-eIBRS: SW sequence; BHI: BHI_DIS_S",
            "spec_store_bypass": "Mitigation: Speculative Store Bypass disabled via prctl"}
VUL_K_OFF = dict(VUL_K_ON, spectre_v1="Vulnerable: __user pointer sanitization and usercopy barriers only; no swapgs barriers",
                 spectre_v2="Vulnerable; IBPB: disabled; PBRSB-eIBRS: Vulnerable; BHI: Vulnerable", spec_store_bypass="Vulnerable")


class BootStateGeneralRuleTest(unittest.TestCase):
    def rec(self, **kw):
        with tempfile.TemporaryDirectory() as d:
            fake_root(d, **kw)
            return bootstate.record(d)

    def test_general(self):
        a = self.rec(vul=VUL_K_ON, cmdline=CMD, boot_id="a")
        self.assertEqual(a["cpu"].get("cpu_family"), None)  # the fake cpuinfo has no family line
        self.assertEqual(bootstate.check(a, "on", rule="general")[0], 0)
        self.assertEqual(bootstate.check(a, "on", rule="h")[0], 13)  # H's rule wants meltdown mitigated
        b = self.rec(vul=VUL_K_OFF, cmdline=CMD + " mitigations=off", boot_id="b")
        self.assertEqual(bootstate.check(b, "off", ref=a, others=[a], rule="general")[0], 0)
        self.assertEqual(bootstate.check(b, "off", rule="general")[0], 13)  # needs the reference
        half = self.rec(vul=dict(VUL_K_OFF, spectre_v1=VUL_K_ON["spectre_v1"]), cmdline=CMD + " mitigations=off", boot_id="c")
        self.assertEqual(bootstate.check(half, "off", ref=a, rule="general")[0], 13)
        newly = self.rec(vul=dict(VUL_K_OFF, mds="Vulnerable"), cmdline=CMD + " mitigations=off", boot_id="d")
        self.assertEqual(bootstate.check(newly, "off", ref=a, rule="general")[0], 13)
        c = self.rec(vul=VUL_K_ON, cmdline=CMD, boot_id="e")
        self.assertEqual(bootstate.check(c, "on", ref=a, others=[a, b], rule="general")[0], 0)
        none = self.rec(vul={"meltdown": "Not affected"}, cmdline=CMD, boot_id="f")
        self.assertEqual(bootstate.check(none, "on", rule="general")[0], 13)


class Wave6kConfigsTest(unittest.TestCase):
    def test_k_configs(self):
        k = os.path.join(HERE, "..", "examples", "wave6k", "c4-32")
        for n, seed in (("h-pl", 611), ("h-c1", 612), ("h-spec", 613)):
            for fn in (n + ".json", "smoke-" + n + ".json"):
                exp = experiment.load(os.path.join(k, fn))
                self.assertEqual(experiment.validate(exp, allow_short=True), [], fn)
                self.assertEqual(exp["order_seed"], seed)
                self.assertEqual(exp["validity"]["max_steal_share"], 0.02)
                self.assertEqual(exp["cpus"], {"sut": "0-3", "client": "4-11,20-27", "origin": "12-15,28-30", "harness": "31"})
            h = experiment.load(os.path.join(CFG, n + ".json"))
            kk = experiment.load(os.path.join(k, n + ".json"))
            # H's arms and shapes verbatim
            self.assertEqual(kk["arms"], h["arms"])
            self.assertEqual(kk["shapes"], h["shapes"])
            self.assertEqual(kk["rounds"], h["rounds"])


class Wave5hConfigsTest(unittest.TestCase):
    NAMES = ("h-pl", "h-c1", "h-spec", "h-defer-deep", "h-defer-c1only")

    def test_configs(self):
        for n in self.NAMES:
            for fn in (n + ".json", "smoke-" + n + ".json"):
                exp = cfg(fn)
                self.assertEqual(experiment.validate(exp, allow_short=True), [], fn)
                names = [a["name"] for a in exp["arms"]]
                for a in exp["arms"]:
                    self.assertEqual(evidence.validate_items(a["evidence"], names), [], (fn, a["name"]))
                    self.assertEqual(a["source_sha256"], SHA)
                self.assertEqual(exp["idle"]["procs"], [], fn)  # no process matched by its command line
                self.assertTrue(exp["client"]["binary"].endswith("/nighthawk-dogfood/bazel-bin/nighthawk_client"))
                if not fn.startswith("smoke"):
                    self.assertEqual(exp["order"], "williams")
                    self.assertEqual(exp["rounds"], 6)
                    self.assertEqual(exp["rounds"] % experiment.order_period(exp), 0)
                    self.assertEqual(exp["warmup_legs"], 1)

    def test_shapes_and_rates(self):
        pl = cfg("h-pl.json")
        self.assertEqual([(s["name"], s["rps"]) for s in pl["shapes"]], [("s", 5200), ("fh", 8000)])
        self.assertTrue(pl["envoy"]["exact_balance"])
        self.assertEqual([(s["name"], s["rps"]) for s in cfg("h-spec.json")["shapes"]], [("s", 5200)])
        for n in ("h-c1", "h-defer-deep", "h-defer-c1only"):
            c = cfg(n + ".json")
            self.assertEqual([(s["name"], s["rps"]) for s in c["shapes"]], [("s", 1600)])
            self.assertFalse(c["envoy"]["exact_balance"])
            self.assertEqual(c["envoy"]["listener_fanout"], 16)

    def test_rate_fallback(self):
        mk = _load("wave5h_make", os.path.join(EX, "make.py"))
        box = json.load(open(os.path.join(HERE, "..", "examples", "stats-flush", "boxes", "bench-x86_64.json")))
        c = mk.configs(box, {"h-pl.s": 4000, "h-pl.fh": 6400, "h-c1": 800})
        self.assertEqual([s["rps"] for s in c["h-pl.json"]["shapes"]], [4000, 6400])
        self.assertEqual([s["rps"] for s in c["smoke-h-pl.json"]["shapes"]], [4000, 6400])
        self.assertEqual(c["h-c1.json"]["shapes"][0]["rps"], 800)
        self.assertEqual(c["h-spec.json"]["shapes"][0]["rps"], 5200)
        # the configs in the tree are the default rates
        self.assertEqual(c["h-spec.json"], json.load(open(os.path.join(CFG, "h-spec.json"))))
        for bad in ({"h-pl.s": 4001}, {"h-xx": 800}):
            with self.assertRaises(SystemExit):
                mk.configs(box, bad)

    def test_arms_differ_only_as_named(self):
        strip = lambda a, extra=(): {k: v for k, v in a.items() if k not in ("name", "evidence") + tuple(extra)}  # noqa: E731
        pl = {a["name"]: a for a in cfg("h-pl.json")["arms"]}
        self.assertEqual(strip(pl["base"]), strip(pl["base-A2"]))
        self.assertNotIn("spec_ctrl", pl["base"])
        sp = {a["name"]: a for a in cfg("h-spec.json")["arms"]}
        self.assertEqual(sp["ssbd"]["spec_ctrl"], {"store_bypass": "disable"})
        self.assertEqual(sp["ibp"]["spec_ctrl"], {"indirect_branch": "disable"})
        for n in ("ssbd", "ibp"):
            self.assertEqual(strip(sp[n], ("spec_ctrl",)), strip(sp["base"]))
        ev = lambda a: {i["stat"]: i["equals"] for i in a["evidence"] if i["stat"].startswith("envoy_speculation")}  # noqa: E731
        self.assertEqual(ev(sp["base"]), {"envoy_speculation.store_bypass": "thread vulnerable",
                                          "envoy_speculation.indirect_branch": "conditional enabled"})
        self.assertEqual(ev(sp["ssbd"])["envoy_speculation.store_bypass"], "thread mitigated")
        self.assertEqual(ev(sp["ibp"])["envoy_speculation.indirect_branch"], "conditional disabled")
        # h-c1 is track E's e-plain, arm for arm
        e3 = json.load(open(os.path.join(HERE, "..", "examples", "wave3e", "bench-x86_64", "e-plain.json")))
        self.assertEqual(cfg("h-c1.json")["arms"], experiment.load(
            os.path.join(HERE, "..", "examples", "wave3e", "bench-x86_64", "e-plain.json"))["arms"])
        self.assertEqual([a["name"] for a in e3["arms"]], ["ka", "ka-A2", "c1"])

    def test_defer_runs(self):
        d, p = cfg("h-defer-deep.json"), cfg("h-defer-c1only.json")
        self.assertEqual([a["name"] for a in d["arms"]], ["c1", "c1-A2", "c1-defer"])
        for x, y in zip(d["arms"], p["arms"]):
            self.assertEqual({k: v for k, v in x.items() if k != "evidence"}, {k: v for k, v in y.items() if k != "evidence"})
            idle = lambda a: [i for i in a["evidence"] if i["stat"].startswith("cpuidle_residency")]  # noqa: E731
            rest = lambda a: [i for i in a["evidence"] if not i["stat"].startswith("cpuidle_residency")]  # noqa: E731
            self.assertEqual(rest(x), rest(y))
            self.assertEqual([i["stat"] for i in idle(x)], ["cpuidle_residency.sum.C6.entries_per_s"])
            self.assertEqual(sorted(i["stat"] for i in idle(y)), ["cpuidle_residency.sum.C1E.entries_per_s",
                                                                  "cpuidle_residency.sum.C6.entries_per_s"])
        defer = next(a for a in d["arms"] if a["name"] == "c1-defer")
        self.assertEqual(defer["settings"], {"tcp_defer_accept_s": 1})
        strip = {k: v for k, v in d.items() if k not in ("name", "machine_label", "order_seed", "_config_text")}
        strip2 = {k: v for k, v in p.items() if k not in ("name", "machine_label", "order_seed", "_config_text")}
        strip.pop("arms"), strip2.pop("arms")
        self.assertEqual(strip, strip2)
        self.assertIn("C1E and C6 disabled", p["machine_label"])
        m = {"cpuidle_residency": {"sum": {"C6": {"entries_per_s": 0.0}, "C1E": {"entries_per_s": 0.0}}}}
        for it in [i for i in next(a for a in p["arms"]).get("evidence") if i["stat"].startswith("cpuidle")]:
            self.assertTrue(evidence.check_item(m, it)["ok"], it)


def write_legs(path, rows):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "legs.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def leg(rnd, shape, arm, cyc, instr_u=200000.0, p50=400.0, valid=True, **kw):
    m = {"round": rnd, "shape": shape, "arm": arm, "leg_id": "r%02d-%s-%s" % (rnd, shape, arm),
         "verdict": {"valid": valid}, "latency_us": {"p50": p50, "p99": p50 * 1.5},
         "per_req": {"cycles_total": cyc, "cycles_u": cyc * 0.55, "cycles_k": cyc * 0.45, "instructions_u": instr_u,
                     "instructions_k": cyc * 0.2}}
    m.update(kw)
    return m


def block_dir(root, name, level, noise=0.002, instr_u=200000.0):
    pl, c1 = [], []
    for r in range(1, 7):
        j = 1 + noise * (1 if r % 2 else -1)
        for a in ("base", "base-A2"):
            pl.append(leg(r, "s", a, 400000 * level * j, instr_u))
            pl.append(leg(r, "fh", a, 300000 * level * j, instr_u))
        c1 += [leg(r, "s", "ka", 630000 * level * j, instr_u), leg(r, "s", "ka-A2", 630000 * level * j, instr_u),
               leg(r, "s", "c1", 870000 * level * j, instr_u)]
    pl.append({"supersede": ["r01-s-base"]})
    pl.append(leg(1, "s", "base", 400000 * level, instr_u, leg_id="r01-s-base.rr1"))
    pl.append(leg(1, "s", "base", 9e9, instr_u, warmup=True, superseded=True, leg_id="r01-s-warmup-base"))
    write_legs(os.path.join(root, name, "h-pl"), pl)
    write_legs(os.path.join(root, name, "h-c1"), c1)
    return os.path.join(root, name)


class CrossTableTest(unittest.TestCase):
    def test_finding(self):
        with tempfile.TemporaryDirectory() as d:
            a, b, c = block_dir(d, "A", 1.0), block_dir(d, "B", 0.95), block_dir(d, "C", 1.001)
            x = table.cross([a, b, c])
            self.assertTrue(all(v.startswith("finding") for v in x["verdicts"].values()), x["verdicts"])
            self.assertTrue(x["kill"].startswith("a price row"))
            row = next(r for r in x["rows"] if r["run"] == "h-pl" and r["shape"] == "s" and r["metric"] == "cycles_total")
            self.assertAlmostEqual(row["P_pct"], 100 * ((1.0 * 1.001) ** 0.5 / 0.95 - 1), places=1)

    def test_kill_inconclusive_withheld(self):
        with tempfile.TemporaryDirectory() as d:
            x = table.cross([block_dir(d, "A", 1.0), block_dir(d, "B", 0.995), block_dir(d, "C", 1.0)])
            self.assertTrue(x["kill"].startswith("killed"), x)
        with tempfile.TemporaryDirectory() as d:
            x = table.cross([block_dir(d, "A", 1.0), block_dir(d, "B", 0.9), block_dir(d, "C", 1.03)])
            self.assertTrue(all(v.startswith("inconclusive") for v in x["verdicts"].values()), x["verdicts"])
            self.assertTrue(x["kill"].startswith("open"))
        with tempfile.TemporaryDirectory() as d:
            x = table.cross([block_dir(d, "A", 1.0), block_dir(d, "B", 0.9, instr_u=202000.0), block_dir(d, "C", 1.0)])
            self.assertTrue(all(v.startswith("withheld") for v in x["verdicts"].values()), x["verdicts"])

    def test_pl_off_block_d(self):
        # B's h-pl A/A fails; block D (a second off boot) replaces B's h-pl, B's h-c1 stays
        with tempfile.TemporaryDirectory() as d:
            b = block_dir(d, "B", 0.97)
            rows = [json.loads(ln) for ln in open(os.path.join(b, "h-pl", "legs.jsonl"))]
            for m in rows:
                if m.get("arm") == "base-A2" and m.get("shape") == "fh":
                    m["per_req"]["cycles_total"] *= 1.05
            write_legs(os.path.join(b, "h-pl"), rows)
            a, c = block_dir(d, "A", 1.0), block_dir(d, "C", 1.0)
            x = table.cross([a, b, c])
            self.assertTrue(x["verdicts"]["h-pl/fh"].startswith("invalid"), x["verdicts"])
            dd = block_dir(d, "D", 0.95)
            y = table.cross([a, b, c], pl_off=dd)
            self.assertTrue(y["verdicts"]["h-pl/fh"].startswith("finding"), y["verdicts"])
            row = next(r for r in y["rows"] if r["run"] == "h-pl" and r["shape"] == "s" and r["metric"] == "cycles_total")
            self.assertAlmostEqual(row["P_pct"], 100 * (1 / 0.95 - 1), places=1)
            c1 = next(r for r in y["rows"] if r["run"] == "h-c1" and r["shape"] == "c1" and r["metric"] == "cycles_total")
            self.assertAlmostEqual(c1["P_pct"], 100 * (1 / 0.97 - 1), places=1)

    def test_failed_block_aa(self):
        with tempfile.TemporaryDirectory() as d:
            a = block_dir(d, "A", 1.0)
            rows = [json.loads(ln) for ln in open(os.path.join(a, "h-pl", "legs.jsonl"))]
            for m in rows:
                if m.get("arm") == "base-A2" and m.get("shape") == "s":
                    m["per_req"]["cycles_total"] *= 1.05
            write_legs(os.path.join(a, "h-pl"), rows)
            x = table.cross([a, block_dir(d, "B", 0.9), block_dir(d, "C", 1.0)])
            self.assertTrue(x["verdicts"]["h-pl/s"].startswith("invalid"), x["verdicts"])


class DeferTableTest(unittest.TestCase):
    def runs(self, d, deep_shift, pinned_shift):
        for run, sh in (("h-defer-deep", deep_shift), ("h-defer-c1only", pinned_shift)):
            rows = []
            for r in range(1, 7):
                j = 1 + 0.004 * (1 if r % 2 else -1)
                rows += [leg(r, "s", "c1", 870000, p50=425 * j), leg(r, "s", "c1-A2", 870000, p50=425 * j),
                         leg(r, "s", "c1-defer", 866000, p50=425 * j * (1 + sh) * (1 + 0.01 * ((r % 3) - 1)))]
            write_legs(os.path.join(d, run), rows)
        return table.defer(d)

    def test_verdicts(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(self.runs(d, 0.127, 0.01)["verdict"].startswith("supported"))
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(self.runs(d, 0.127, 0.12)["verdict"].startswith("rejected"))
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(self.runs(d, 0.127, 0.08)["verdict"].startswith("partly"))
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(self.runs(d, 0.02, 0.0)["verdict"].startswith("not replicated"))


GRUB_SAMPLE = """set default="0"
if [ "${next_entry}" ] ; then
   set default="${next_entry}"
   set next_entry=
   save_env next_entry
   set boot_once=true
fi
menuentry 'Ubuntu' --class ubuntu --class os $menuentry_id_option 'gnulinux-simple-1234' {
	recordfail
	load_video
	insmod ext2
	search --no-floppy --fs-uuid --set=root abcd
	linux	/vmlinuz-6.8.0-151-generic root=/dev/mapper/vg-lv ro
	initrd	/initrd.img-6.8.0-151-generic
}
submenu 'Advanced options for Ubuntu' $menuentry_id_option 'gnulinux-advanced-1234' {
	menuentry 'Ubuntu, with Linux 6.8.0-151-generic' --class ubuntu $menuentry_id_option 'x' {
		linux	/vmlinuz-6.8.0-151-generic root=/dev/mapper/vg-lv ro
	}
}
"""


@unittest.skipUnless(shutil.which("bash") and shutil.which("awk"), "needs bash and awk")
class OneshotEntriesTest(unittest.TestCase):
    def test_two_linux_lines(self):
        # cloud images: the default entry boots without an initrd first and falls back to one
        cfg_txt = ("set default=\"0\"\nmenuentry 'Ubuntu' --class ubuntu $menuentry_id_option 'gnulinux-simple-9' {\n"
                   "\trecordfail\n\tif [ \"${initrdfail}\" = 1 ]; then\n"
                   "\t\tlinux\t/vmlinuz-7 root=PARTUUID=x ro  console=ttyS0\n\t\tinitrd\t/initrd.img-7\n"
                   "\telse\n\t\tlinux\t/vmlinuz-7 root=PARTUUID=x ro  console=ttyS0 panic=-1\n\tfi\n}\n")
        self.assertIn("panic=-1", cfg_txt)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "grub.cfg")
            with open(p, "w") as f:
                f.write(cfg_txt)
            r = subprocess.run(["bash", os.path.join(EX, "oneshot-boot.sh"), "entries"], capture_output=True, text=True,
                               env=dict(os.environ, GRUB_CFG=p))
            self.assertEqual(r.returncode, 0, r.stderr)
            off = r.stdout.split("'epl-oneshot-off'")[1]
            on = r.stdout.split("menuentry 'EPL one-shot: mitigations=off'")[0]
            self.assertIn("ro  console=ttyS0 mitigations=off\n", off)
            self.assertIn("ro  console=ttyS0 panic=-1 mitigations=off\n", off)
            self.assertEqual(on.count("mitigations"), 0)

    def test_entries(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "grub.cfg")
            with open(p, "w") as f:
                f.write(GRUB_SAMPLE)
            r = subprocess.run(["bash", os.path.join(EX, "oneshot-boot.sh"), "entries"], capture_output=True, text=True,
                               env=dict(os.environ, GRUB_CFG=p))
            self.assertEqual(r.returncode, 0, r.stderr)
            blocks = [b for b in r.stdout.split("}\n") if b.strip()]
            self.assertEqual(len(blocks), 2, r.stdout)
            on, off = blocks
            self.assertIn("'EPL one-shot: default command line'", on)
            self.assertIn("$menuentry_id_option 'epl-oneshot-on' {", on)
            self.assertIn("$menuentry_id_option 'epl-oneshot-off' {", off)
            self.assertIn("\tlinux\t/vmlinuz-6.8.0-151-generic root=/dev/mapper/vg-lv ro\n", on)
            self.assertIn("\tlinux\t/vmlinuz-6.8.0-151-generic root=/dev/mapper/vg-lv ro mitigations=off\n", off)
            self.assertNotIn("mitigations", on)
            # apart from title, id and the one argument, both are the default entry verbatim
            body = lambda b: [ln for ln in b.splitlines()[1:] if not ln.lstrip().startswith("linux")]  # noqa: E731
            dflt = GRUB_SAMPLE.split("menuentry 'Ubuntu'")[1].split("\n}\n")[0]
            self.assertEqual(body(on), body("x" + dflt))
            self.assertEqual(body(off), body(on))
            self.assertNotIn("submenu", r.stdout)

    def test_refuses_without_entry(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "grub.cfg")
            with open(p, "w") as f:
                f.write("set default=0\n")
            r = subprocess.run(["bash", os.path.join(EX, "oneshot-boot.sh"), "entries"], capture_output=True, text=True,
                               env=dict(os.environ, GRUB_CFG=p))
            self.assertNotEqual(r.returncode, 0)


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class ScriptsSyntaxTest(unittest.TestCase):
    def test_bash_n(self):
        for fn in ("chain-h.sh", "run-h.sh", "box-start.sh", "cstate.sh", "oneshot-boot.sh"):
            r = subprocess.run(["bash", "-n", os.path.join(EX, fn)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, (fn, r.stderr))

    def test_no_process_matching(self):
        # the session scripts never match processes by their command line and never pkill/killall
        for fn in ("chain-h.sh", "run-h.sh", "box-start.sh", "cstate.sh", "oneshot-boot.sh"):
            txt = open(os.path.join(EX, fn)).read()
            for bad in ("pgrep", "pkill", "killall", "ps -e", "ps aux"):
                self.assertNotIn(bad, txt, (fn, bad))


if __name__ == "__main__":
    unittest.main()
