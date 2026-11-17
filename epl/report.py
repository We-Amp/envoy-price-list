"""Short Markdown summary of a results.json."""

from .experiment import METRICS


def _k(x):
    return "-" if x is None else ("%.1fk" % (x / 1e3))


def _f(x, fmt="%.0f"):
    return "-" if x is None else fmt % x


def _p(x):
    return "-" if x is None else ("%.3f" % x)


def _effect(c):
    p = c.get("paired") or {}
    if p.get("half_width_pct") is None:
        return _f(p.get("effect_pct"), "%+.2f%%")
    return "%+.2f%% [%+.2f, %+.2f]" % (p["effect_pct"], p["lo_pct"], p["hi_pct"])


def markdown(res, floor=None):
    md = res["metadata"]
    exp = res["experiment"]
    an = res["analysis"]
    mach = md.get("machine", {})
    L = []
    L.append("# %s" % exp["name"])
    L.append("")
    L.append("- Harness: %s" % md.get("harness"))
    L.append("- Window: %s to %s" % (md.get("started_utc"), md.get("finished_utc")))
    if md.get("machine_label"):
        L.append("- Machine: %s" % md["machine_label"])
    L.append("- CPU: %s; kernel %s; governor %s; clock (kHz, one sample at start) %s" % (
        mach.get("cpu_model"), mach.get("kernel"), ",".join(mach.get("governors_in_use", []) or ["?"]),
        ",".join(mach.get("cur_khz_in_use", []) or ["?"])))
    ci = mach.get("cpuidle_sut_summary") or {}
    if ci:
        L.append("- Idle states (SUT CPUs and their SMT siblings, %s): %s; per state: %s; unchanged at the end: %s"
                 % (ci.get("cpus"), ci.get("text"), ", ".join(
                     "%s %sus %s" % (st["name"], st["latency_us"], "off" if not st["enabled_on"] else
                                     ("on" if not st["disabled_on"] else "off on %s" % st["disabled_on"]))
                     for st in ci.get("states", [])), md.get("cpuidle_unchanged", "?")))
    cl = md.get("client") or {}
    if cl:
        L.append("- Client: Nighthawk %s, md5 `%s`, commit %s" % (
            cl.get("version"), cl.get("md5"),
            "`%s`" % cl["commit"] if cl.get("commit") else "not recorded (%s)" % cl.get("commit_source", "?")))
    L.append("- CPU sets: %s" % ", ".join("%s %s" % kv for kv in sorted(md.get("cpus", {}).items())))
    e = exp["envoy"]
    c = exp["client"]
    m = exp["measure"]
    L.append("- Envoy: %d workers, exact_balance %s; client concurrency %d x %d connections, idle strategy %s, "
             "open loop %s, extra args %s; warm-up %ss, run %ss, perf window %ss after %ss lead-in" % (
                 e["workers"], e.get("exact_balance"), c["concurrency"], c["connections_per_worker"],
                 c.get("idle_strategy"), c.get("open_loop"), " ".join(c.get("extra_args") or []) or "none",
                 c.get("warmup_s"), c["duration_s"], m["window_s"], m["lead_in_s"]))
    L.append("- Rounds: %s done (minimum %d, blocks of %d, cap %d, adaptive %s), order %s; stop: %s" % (
        md.get("rounds_done", exp["rounds"]), exp["rounds"], exp.get("rounds_block", 0),
        exp.get("rounds_max", exp["rounds"]), exp.get("adaptive", False), md.get("order", exp.get("order")),
        md.get("stop_reason")))
    if md.get("aborted"):
        L.append("- **Aborted:** %s" % md["aborted"])
    if md.get("incomplete"):
        L.append("- **Incomplete, no verdict:** %s complete rounds of the minimum %d; only complete rotation "
                 "blocks are analysed and no row carries a verdict" % (md.get("rounds_complete"), exp["rounds"]))
    elif md.get("legs_after_last_complete_block"):
        L.append("- %d legs after the last complete rotation block are recorded but not analysed" %
                 md["legs_after_last_complete_block"])
    L.append("- Headline: %s. Primary metric %s, Holm across %d primary rows at alpha %.2f; every other "
             "metric is exploratory (interval only, no multiplicity control)." % (
                 an.get("headline", "paired"), an.get("primary_metric"), an.get("primary_family_size", 0),
                 an["alpha"]))
    L.append("- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's "
             "context, so cycles:k compares arms but is not what a deployment behind a NIC pays.")
    L.append("")
    L.append("| Arm | Version | md5 |")
    L.append("|---|---|---|")
    for n, a in md.get("arms", {}).items():
        L.append("| %s | %s | `%s` |" % (n, a.get("version"), a.get("md5")))
    L.append("")
    for sh in exp["shapes"]:
        s = sh["name"]
        sres = an["shapes"][s]
        L.append("## %s (`%s`, %s, %d rps)" % (s, sh["path"], sh["kind"], sh["rps"]))
        L.append("")
        L.append("Medians over valid legs; per-leg CV of total cycles in brackets.")
        L.append("")
        L.append("| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for a in exp["arms"]:
            x = sres["arms"][a["name"]]
            g = lambda k: (x.get(k) or {}).get("median")  # noqa: E731
            cv = (x.get("cycles_total") or {}).get("cv_pct")
            L.append("| %s | %d/%d | %s | %s | %s | %s (%s) | %s | %s | %s |" % (
                a["name"], x["valid"], x["legs"], _k(g("instructions_u")), _k(g("cycles_u")), _k(g("cycles_k")),
                _k(g("cycles_total")), _f(cv, "%.1f%%"), _f(g("p50_us")), _f(g("p99_us")),
                _f((x.get("sut_busy_mean") or 0) * 100, "%.1f%%") if x.get("sut_busy_mean") else "-"))
        L.append("")
        comps = sres.get("comparisons") or []
        if comps:
            L.append("Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width "
                     "(log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is "
                     "within the A/A half-width is marked \"inside the A/A floor\"; one within the far end of the "
                     "A/A interval, \"inside the A/A interval\": the A/A could not exclude a harness bias that "
                     "large, so such a row needs support from other rows to count.")
            L.append("")
            L.append("| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | "
                     "Wilcoxon p | Holm p | status |")
            L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
            for comp in comps:
                for key, label, _ in METRICS:
                    cc = comp.get(key)
                    if not cc:
                        continue
                    p = cc.get("paired") or {}
                    fl = cc.get("aa_floor_half_width_pct")
                    if fl is None and floor:
                        fl = (floor.get(s, {}).get(key) or {}).get("hw")
                    L.append("| %s vs %s | %s | %s | %s | %s | %s | %s | %d | %d/%d | %s | %s | %s | %s |" % (
                        comp["arm"], comp["ref"], label, cc.get("role", "-"), _effect(cc),
                        _f(p.get("half_width_pct"), "%.2f"), _f(fl, "%.2f"), _f(p.get("log_sd_pct"), "%.2f"),
                        cc["n"], cc["pairs_won"], cc["n"], _p(cc["sign_p"]), _p(cc["wilcoxon_p"]),
                        _p(cc.get("holm_p")), cc.get("status", "-")))
            L.append("")
    allegs = res["legs"]
    sup = [x for x in allegs if x.get("superseded")]
    inv = [x for x in allegs if not x["verdict"]["valid"]]
    L.append("## Validity")
    L.append("")
    L.append("%d legs run, %d valid; %d legs superseded by a re-run of their round." % (
        len(allegs), len(allegs) - len(inv), len(sup)))
    for x in inv:
        L.append("- %s%s: %s" % (x["leg_id"], " (superseded)" if x.get("superseded") else "",
                                 "; ".join(x["verdict"]["reasons"])))
    L.append("")
    if "aa_selftest" in res:
        aa = res["aa_selftest"]
        L.append("## A/A self-test: %s" % ("PASS" if aa["pass"] else "FAIL"))
        L.append("")
        L.append("Rule: %s." % aa.get("rule", ""))
        L.append("")
        L.append("| Shape | metric | effect [95% CI] | hw | limit | pair SD | 80%-power bias | n | Holm p | verdict |")
        L.append("|---|---|---|---|---|---|---|---|---|---|")
        for ch in aa["checks"]:
            if "effect_pct" not in ch:
                L.append("| %s | %s | - | - | %s | - | - | %s | - | %s |" % (
                    ch["shape"], ch["metric"], _f(ch.get("max_half_width_pct"), "%.2f"), ch.get("pairs"),
                    ch.get("why")))
                continue
            L.append("| %s | %s | %+.2f%% [%+.2f, %+.2f] | %.2f | %s | %.2f | %.2f%% | %d | %s | %s |" % (
                ch["shape"], ch["metric"], ch["effect_pct"], ch["lo_pct"], ch["hi_pct"], ch["half_width_pct"],
                _f(ch.get("max_half_width_pct"), "%.2f"), ch["sd_pct"], ch["mde_pct"], ch["pairs"],
                _p(ch.get("holm_p")), ch["why"]))
        L.append("")
    return "\n".join(L) + "\n"
