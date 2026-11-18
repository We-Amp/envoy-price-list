"""Portability check of the stats row's configs across machines (box descriptions).

A config directory holds `box.json` (the machine: architecture, CPU sets, perf path and
event list, labels, client binary) and the configs rendered for that box. The check fails
when:

- a config of one box carries a literal that belongs to another box (a CPU set, the perf
  path, the label, a binary path or release asset of another architecture, its event list);
- any config carries a literal that is specific to one CPU family and is not in its own
  box description (Intel event names, a clock figure, a processor brand);
- the boxes do not have the same configs, or a config renders a different Envoy bootstrap
  on two boxes (the bootstrap must not depend on the machine);
- an arm's per-architecture binary does not resolve for the box, or a config's `box`
  block is not the directory's box.json.
"""

import glob
import json
import os
import re
import tempfile

from . import envoy_config, experiment

# family-specific literals no config may carry unless its own box description does
FAMILY_LITERALS = [r"uops_", r"idq_", r"topdown", r"br_misp_retired", r"mem_load_uops", r"dtlb_load_misses",
                   r"icache\.", r"itlb_misses", r"dsb2mite", r"int_misc", r"armv8_pmuv3", r"[0-9.]+ ?GHz",
                   r"Xeon", r"Graviton", r"Ampere", r"Neoverse", r"\bturbo\b"]
BOX_KEYS_LITERAL = ("label", "machine_label", "perf", "client_binary")


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


def box_literals(box):
    """Strings that identify a box: CPU sets, perf path, labels, client binary, event list,
    and every binary path and asset name of its architecture."""
    out = set()
    for v in (box.get("cpus") or {}).values():
        out.add(str(v))
    for k in BOX_KEYS_LITERAL:
        if box.get(k):
            out.add(str(box[k]))
    if box.get("perf_events"):
        out.add(box["perf_events"])
    for b in list((box.get("binaries") or {}).values()) + list((box.get("fix_binaries") or {}).values()):
        for k in ("binary", "source"):
            if b.get(k):
                out.add(b[k])
    return {s for s in out if s}


def load_dir(d):
    with open(os.path.join(d, "box.json")) as f:
        box = json.load(f)
    cfgs = {}
    for p in sorted(glob.glob(os.path.join(d, "*.json"))):
        if os.path.basename(p) == "box.json":
            continue
        with open(p) as f:
            cfgs[os.path.basename(p)] = (p, f.read())
    return box, cfgs


def bootstraps(path, box):
    exp = experiment.load(path, {"box": box})
    out = {}
    with tempfile.TemporaryDirectory() as d:
        for a in exp["arms"]:
            # the generated clusters capped at two: the structure is what must not depend on the box
            out[a["name"]] = envoy_config.bootstrap_text(
                exp["shapes"], experiment.small_clusters(experiment.arm_envoy(exp, a, "/run")),
                exp["origin"]["port"], "/run/certs")
    return exp, out


def check_dirs(dirs):
    problems = []
    loaded = {d: load_dir(d) for d in dirs}
    lits = {d: box_literals(b) for d, (b, _) in loaded.items()}
    names = {d: {fn for fn, (_, t) in c.items() if not json.loads(t).get("box_specific")}
             for d, (_, c) in loaded.items()}
    ref = dirs[0]
    for d in dirs[1:]:
        if names[d] != names[ref]:
            problems.append("%s and %s have different configs: %s" % (
                os.path.basename(d), os.path.basename(ref), sorted(names[d] ^ names[ref])))
    boots = {}
    for d, (box, cfgs) in loaded.items():
        own = lits[d]
        foreign = set()
        for o in dirs:
            if o != d:
                foreign |= lits[o]
        foreign -= own  # a literal two boxes share is not foreign
        for fn, (path, text) in cfgs.items():
            raw = json.loads(text)
            if raw.get("box_specific"):
                # a config only this box has (own builds for it): checked for foreign literals
                # and family literals, not compared with the other boxes
                pass
            if raw.get("box") != box:
                problems.append("%s/%s: box block differs from box.json" % (os.path.basename(d), fn))
            body = text
            for s in sorted(own, key=len, reverse=True):
                body = body.replace(json.dumps(s), '""')
            for s in sorted(foreign):
                # a whole JSON string value, so a short CPU set never matches inside another string
                if json.dumps(s) in text:
                    problems.append("%s/%s: carries another box's literal %r" % (os.path.basename(d), fn, s))
            for pat in FAMILY_LITERALS:
                mm = re.search(pat, body)
                if mm:
                    problems.append("%s/%s: family-specific literal %r outside its box description" % (
                        os.path.basename(d), fn, mm.group(0)))
            try:
                exp, bt = bootstraps(path, box)
            except (ValueError, KeyError) as e:
                problems.append("%s/%s: %s" % (os.path.basename(d), fn, e))
                continue
            for a in exp["arms"]:
                if box.get("arch") and a.get("binaries") and experiment.norm_arch(box["arch"]) not in a["binaries"]:
                    problems.append("%s/%s: arm %s has no binary for %s" % (os.path.basename(d), fn, a["name"],
                                                                             box["arch"]))
            if not raw.get("box_specific"):
                boots.setdefault(fn, {})[d] = bt
    for fn, per in boots.items():
        ds = list(per)
        for o in ds[1:]:
            if per[o] != per[ds[0]]:
                diff = sorted(a for a in per[o] if per[o].get(a) != per[ds[0]].get(a))
                problems.append("%s: the Envoy bootstrap differs between %s and %s (arms %s)" % (
                    fn, os.path.basename(ds[0]), os.path.basename(o), diff))
    return problems
