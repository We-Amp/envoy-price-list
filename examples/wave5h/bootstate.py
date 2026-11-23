#!/usr/bin/env python3
"""The state of one boot, recorded and checked before a track H block runs (read only).

    bootstate.py record OUT.json
    bootstate.py check --expect on|off [--rule h|general] [--ref REF.json | --ref-advisory REF.json] [--other-boot B.json ...] OUT.json

`record` writes what a reboot could change: kernel release and build, the kernel command line, the
boot id, the CPU-vulnerability state (/sys/devices/system/cpu/vulnerabilities), the microcode
revision, the frequency setup (driver, governors, limits, turbo), the idle-state setup of every CPU
(driver, governor, and per state its exit latency and the disable flags over all CPUs), SMT,
transparent huge pages, perf access and a set of network sysctls.

`check` records, then fails closed:
  rc 13  the mitigation state is not the expected one:
         on:  no mitigation argument on the command line, and every vulnerability line that reads
              "Mitigation" in REF reads the same here (with --ref);
         off: `mitigations=off` on the command line, and the lines in OFF_REQUIRED all read
              "Vulnerable";
  rc 14  anything outside the mitigation fields differs from REF (another kernel, microcode,
         frequency or idle-state setup, ...): the boots are not comparable;
  rc 15  the boot id equals the boot id of an earlier block (--other-boot): no reboot happened.
--rule general (a CPU where most lines read "Not affected"): off = `mitigations=off` on the line AND
every line that reads "Mitigation" in REF reads "Vulnerable" here AND every "Not affected" line of REF is "Not
affected" here (needs --ref); on = no mitigation argument AND at least one line reads "Mitigation" (and, with
--ref, every "Mitigation" line of REF reads the same here). The default rule h is track H's (Broadwell).
--ref-advisory REF prints the rc-14 differences against REF as warnings and does not fail on them (block
A against the long-running boot before the series: a runtime change made in that boot must not block the
fresh-boot series; B and C are checked strictly against A). Exit 0 when every check passes.
"""

import argparse
import glob
import json
import os
import platform
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl import sysprobe  # noqa: E402

# with mitigations=off these must all read "Vulnerable..." on this class of CPU (Broadwell-EP);
# the rest (l1tf PTE inversion is unconditional, itlb_multihit is KVM's) are recorded, not gated
OFF_REQUIRED = ("meltdown", "spectre_v2", "spec_store_bypass", "mds", "tsx_async_abort", "mmio_stale_data")
SYSCTLS = ("kernel/numa_balancing", "kernel/perf_event_paranoid", "kernel/sched_autogroup_enabled",
           "net/ipv4/tcp_tw_reuse", "net/ipv4/ip_local_port_range", "net/ipv4/tcp_max_tw_buckets",
           "net/ipv4/tcp_timestamps", "net/core/somaxconn", "net/ipv4/tcp_max_syn_backlog",
           "net/netfilter/nf_conntrack_max", "net/netfilter/nf_conntrack_tcp_timeout_time_wait",
           "net/core/rmem_max", "net/core/wmem_max", "vm/swappiness")
MITIGATION_FIELDS = ("boot_id", "cmdline", "cpu_vulnerabilities", "kernel_cmdline_mitigation_args")


def _r(path, root):
    v = sysprobe._read(os.path.join(root, path.lstrip("/")))
    return v.strip() if isinstance(v, str) else v


def _values_over(paths):
    """{value: count} of a sysfs file over all CPUs."""
    out = {}
    for p in paths:
        v = sysprobe._read(p)
        v = v.strip() if isinstance(v, str) else v
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items()))


def cpu_identity(root="/"):
    """Family, model, stepping and model name of CPU 0 (a different host CPU would show here)."""
    txt = sysprobe._read(os.path.join(root, "proc/cpuinfo"), "") or ""
    out = {}
    for k in ("cpu family", "model", "stepping", "model name"):
        for ln in txt.splitlines():
            if ln.split(":")[0].strip() == k:
                out[k.replace(" ", "_")] = ln.split(":", 1)[1].strip()
                break
    return out


def record(root="/"):
    cpu = os.path.join(root, "sys/devices/system/cpu")
    bs = sysprobe.boot_state(root)
    cmd = (_r("proc/cmdline", root) or "").split()
    rec = {
        "kernel_release": platform.release() if root == "/" else None,
        "kernel_version": _r("proc/version", root),
        "cmdline": [t for t in cmd if not t.startswith("BOOT_IMAGE=")],
        "boot_image": next((t.split("=", 1)[1] for t in cmd if t.startswith("BOOT_IMAGE=")), None),
        "boot_id": bs["boot_id"],
        "cpu_vulnerabilities": bs["cpu_vulnerabilities"],
        "kernel_cmdline_mitigation_args": bs["kernel_cmdline_mitigation_args"],
        "microcode": bs["microcode"],
        "cpu": cpu_identity(root),
        # no cloud metadata is queried; the field stays in the record format, always null
        "physical_host": None,
        "online": _r("sys/devices/system/cpu/online", root),
        "smt_control": _r("sys/devices/system/cpu/smt/control", root),
        "cpufreq": {
            "driver": _values_over(glob.glob(cpu + "/cpu[0-9]*/cpufreq/scaling_driver")),
            "governor": _values_over(glob.glob(cpu + "/cpu[0-9]*/cpufreq/scaling_governor")),
            "min_khz": _values_over(glob.glob(cpu + "/cpu[0-9]*/cpufreq/scaling_min_freq")),
            "max_khz": _values_over(glob.glob(cpu + "/cpu[0-9]*/cpufreq/scaling_max_freq")),
            "no_turbo": _r("sys/devices/system/cpu/intel_pstate/no_turbo", root),
            "pstate_status": _r("sys/devices/system/cpu/intel_pstate/status", root),
        },
        "cpuidle": {
            "driver": _r("sys/devices/system/cpu/cpuidle/current_driver", root),
            "governor": _r("sys/devices/system/cpu/cpuidle/current_governor", root),
            "states": {},
        },
        "intel_idle": {os.path.basename(p): sysprobe._read(p).strip()
                       for p in sorted(glob.glob(os.path.join(root, "sys/module/intel_idle/parameters/*")))
                       if isinstance(sysprobe._read(p), str)},
        "thp": {"enabled": _r("sys/kernel/mm/transparent_hugepage/enabled", root),
                "defrag": _r("sys/kernel/mm/transparent_hugepage/defrag", root)},
        "sysctl": {k.replace("/", "."): _r("proc/sys/" + k, root) for k in SYSCTLS},
    }
    for d in sorted(glob.glob(cpu + "/cpu0/cpuidle/state*")):
        st = os.path.basename(d)
        rec["cpuidle"]["states"][st] = {
            "name": sysprobe._read(d + "/name", "").strip(),
            "latency_us": sysprobe._read(d + "/latency", "").strip(),
            "disable_over_cpus": _values_over(glob.glob(cpu + "/cpu[0-9]*/cpuidle/%s/disable" % st)),
        }
    return rec


def expect_problems(rec, expect, ref=None, rule="h"):
    p = []
    args = rec["kernel_cmdline_mitigation_args"]
    vul = rec["cpu_vulnerabilities"]
    if rule == "general":
        rv = (ref or {}).get("cpu_vulnerabilities") or {}
        if expect == "off":
            if "mitigations=off" not in args:
                p.append("command line has no mitigations=off (mitigation args: %s)" % (args or "none"))
            if not rv:
                p.append("rule general needs the on-boot reference (--ref)")
            for n, v in sorted(rv.items()):
                if (v or "").startswith("Mitigation") and not (vul.get(n) or "").startswith("Vulnerable"):
                    p.append("%s reads %r, expected Vulnerable... (reference: %r)" % (n, vul.get(n), v))
                if (v or "").startswith("Not affected") and not (vul.get(n) or "").startswith("Not affected"):
                    p.append("%s reads %r, expected Not affected as in the reference" % (n, vul.get(n)))
        elif expect == "on":
            if args:
                p.append("command line carries mitigation arguments %s" % args)
            if not any((v or "").startswith("Mitigation") for v in vul.values()):
                p.append("no vulnerability line reads Mitigation...")
            for n, v in sorted(rv.items()):
                if (v or "").startswith("Mitigation") and vul.get(n) != v:
                    p.append("%s reads %r, the reference boot %r" % (n, vul.get(n), v))
        else:
            p.append("expect must be on or off")
        return p
    if expect == "off":
        if "mitigations=off" not in args:
            p.append("command line has no mitigations=off (mitigation args: %s)" % (args or "none"))
        for n in OFF_REQUIRED:
            v = vul.get(n)
            if not (v or "").startswith("Vulnerable"):
                p.append("%s reads %r, expected Vulnerable..." % (n, v))
    elif expect == "on":
        if args:
            p.append("command line carries mitigation arguments %s" % args)
        if ref is not None:
            for n, v in sorted((ref.get("cpu_vulnerabilities") or {}).items()):
                if (v or "").startswith("Mitigation") and vul.get(n) != v:
                    p.append("%s reads %r, the reference boot %r" % (n, vul.get(n), v))
        elif not (vul.get("meltdown") or "").startswith("Mitigation"):
            p.append("meltdown reads %r, expected Mitigation..." % vul.get("meltdown"))
    else:
        p.append("expect must be on or off")
    return p


def ref_differences(rec, ref):
    """Fields outside the mitigation state that differ from the reference boot (dotted paths)."""
    out = []

    def walk(a, b, path):
        if isinstance(a, dict) and isinstance(b, dict):
            for k in sorted(set(a) | set(b)):
                walk(a.get(k), b.get(k), path + [k])
        elif a != b:
            out.append("%s: %r here, %r in the reference" % (".".join(path), a, b))

    for k in sorted(set(rec) | set(ref)):
        if k in MITIGATION_FIELDS:
            continue
        if k == "cmdline":
            continue
        walk(rec.get(k), ref.get(k), [k])
    # the command line apart from the mitigation arguments must be the same too
    strip = lambda c: [t for t in (c or []) if not sysprobe.MITIGATION_ARG.match(t)]  # noqa: E731
    if strip(rec.get("cmdline")) != strip(ref.get("cmdline")):
        out.append("cmdline (without mitigation args): %r here, %r in the reference" % (
            strip(rec.get("cmdline")), strip(ref.get("cmdline"))))
    return out


def check(rec, expect, ref=None, others=(), rule="h"):
    """(rc, messages)."""
    msgs = []
    p = expect_problems(rec, expect, ref, rule)
    if p:
        return 13, ["mitigation state is not '%s': %s" % (expect, x) for x in p]
    if ref is not None:
        d = ref_differences(rec, ref)
        if d:
            return 14, ["differs from the reference boot: " + x for x in d]
    for o in others:
        if o.get("boot_id") and o.get("boot_id") == rec.get("boot_id"):
            return 15, ["boot id %s is the boot id of an earlier block: no reboot happened" % rec["boot_id"]]
    msgs.append("boot state OK: expect %s, boot id %s, kernel %s, mitigation args %s" % (
        expect, rec.get("boot_id"), rec.get("kernel_release"), rec.get("kernel_cmdline_mitigation_args") or "none"))
    return 0, msgs


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("out")
    c = sub.add_parser("check")
    c.add_argument("--expect", required=True, choices=("on", "off"))
    c.add_argument("--ref")
    c.add_argument("--ref-advisory")
    c.add_argument("--rule", choices=("h", "general"), default="h")
    c.add_argument("--other-boot", action="append", default=[])
    c.add_argument("out")
    a = ap.parse_args()
    rec = record()
    with open(a.out, "w") as f:
        json.dump(rec, f, indent=1, sort_keys=True)
        f.write("\n")
    if a.cmd == "record":
        print("recorded %s (boot id %s)" % (a.out, rec["boot_id"]))
        return 0
    load = lambda p: json.load(open(p))  # noqa: E731
    if a.ref and a.ref_advisory:
        ap.error("--ref and --ref-advisory exclude each other")
    rc, msgs = check(rec, a.expect, load(a.ref) if a.ref else None, [load(p) for p in a.other_boot], a.rule)
    if rc == 0 and a.ref_advisory:
        adv = ref_differences(rec, load(a.ref_advisory))
        msgs += ["WARNING (advisory, not gated): differs from %s: %s" % (a.ref_advisory, x) for x in adv] or [
            "advisory reference %s: no difference outside the mitigation fields" % a.ref_advisory]
    for m in msgs:
        print(m)
    return rc


if __name__ == "__main__":
    sys.exit(main())
