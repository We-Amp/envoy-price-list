"""Decompose A/A per-round log ratios by label, slot and position.

usage: python3 aa_decompose.py results.json [more results.json ...] [--json out.json]
For each shape: d = 100 ln(label A2 / label A) per round on cycles_total.
  label effect   = mean d
  slot effect    = mean of 100 ln(arms[1] / arms[0])
  position       = mean of 100 ln(second leg in round / first leg in round)
  middle-of-pair = mean of 100 ln(arm in the temporal middle of the round pair / outer arm)
"""
import json
import math
import sys

T975 = {5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160,
        14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074,
        23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042, 35: 2.030,
        40: 2.021, 50: 2.009, 60: 2.000, 80: 1.990, 100: 1.984, 200: 1.972}


def tq(df):
    ks = sorted(T975)
    for k in ks:
        if df <= k:
            return T975[k]
    return 1.96


def summ(xs):
    n = len(xs)
    if n < 2:
        return {"n": n}
    mu = sum(xs) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / (n - 1))
    se = sd / math.sqrt(n)
    hw = tq(n - 1) * se
    return {"n": n, "mean": round(mu, 3), "sd": round(sd, 3), "se": round(se, 3), "lo": round(mu - hw, 3),
            "hi": round(mu + hw, 3), "t": round(mu / se, 3) if se > 0 else None}


def decompose(path, metric="cycles_total"):
    r = json.load(open(path))
    exp = r["experiment"]
    names = [a["name"] for a in exp["arms"]]
    lab_ref, lab_arm = "A", "A2"
    slot0, slot1 = names[0], names[1]
    legs = [m for m in r["legs"] if "arm" in m]
    cur = [m for m in legs if not m.get("superseded") and m.get("verdict", {}).get("valid")]
    out = {"run": path, "arms_order": names, "order_seed": exp.get("order_seed"), "shapes": {}}
    for sh in [s["name"] for s in exp["shapes"]]:
        by = {}
        idx = {}
        for i, m in enumerate(legs):
            if m["shape"] == sh and not m.get("superseded"):
                idx[(m["round"], m["arm"])] = i
        for m in cur:
            if m["shape"] == sh:
                by[(m["round"], m["arm"])] = m["per_req"][metric]
        rounds = sorted(rr for (rr, a) in by if a == lab_arm and (rr, lab_ref) in by)
        lab, slot, pos, rows = [], [], [], []
        for rr in rounds:
            d = 100 * math.log(by[(rr, lab_arm)] / by[(rr, lab_ref)])
            first = lab_ref if idx[(rr, lab_ref)] < idx[(rr, lab_arm)] else lab_arm
            second = lab_arm if first == lab_ref else lab_ref
            lab.append(d)
            slot.append(100 * math.log(by[(rr, slot1)] / by[(rr, slot0)]))
            pos.append(100 * math.log(by[(rr, second)] / by[(rr, first)]))
            rows.append({"round": rr, "d_label": round(d, 3), "first": first})
        # middle of pair: pairs (1,2), (3,4), ... ; the middle arm is the second arm of the pair's first round
        mid = []
        for rr in rounds:
            if rr % 2 == 1 and (rr + 1) in rounds:
                firstrow = [x for x in rows if x["round"] == rr][0]
                middle = lab_arm if firstrow["first"] == lab_ref else lab_ref
                for q in (rr, rr + 1):
                    d = [x for x in rows if x["round"] == q][0]["d_label"]
                    mid.append(d if middle == lab_arm else -d)
        a2_first = sum(1 for x in rows if x["first"] == lab_arm)
        out["shapes"][sh] = {"label_A2_over_A": summ(lab), "slot1_over_slot0": summ(slot),
                             "second_over_first": summ(pos), "middle_over_outer": summ(mid),
                             "A2_first_rounds": a2_first, "rounds": len(rows), "per_round": rows}
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    jout = None
    if "--json" in args:
        i = args.index("--json")
        jout = args[i + 1]
        args = args[:i] + args[i + 2:]
    allr = [decompose(p) for p in args]
    for o in allr:
        print("==", o["run"], "arms", o["arms_order"], "seed", o["order_seed"])
        for sh, s in o["shapes"].items():
            def f(k):
                x = s[k]
                return "%+.2f [%+.2f,%+.2f] t=%s" % (x["mean"], x["lo"], x["hi"], x["t"]) if "mean" in x else "-"
            print("  %-10s n=%d A2first=%d | label %s | slot %s | 2nd/1st %s | mid/outer %s" % (
                sh, s["rounds"], s["A2_first_rounds"], f("label_A2_over_A"), f("slot1_over_slot0"),
                f("second_over_first"), f("middle_over_outer")))
    if jout:
        json.dump(allr, open(jout, "w"), indent=1)
