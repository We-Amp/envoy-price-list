#!/usr/bin/env python3
"""Wave 5 track I: turn `perf script --show-mmap-events -F ip` output of frame-pointer call-chain samples
(perf record --call-graph=fp) of the opt binary into an lld call-graph ordering file and a hot-function list.
This replaces wave 2's lbr2order.py on a host without branch records (no LBR, BRBE or SPE in this guest).

Every sample is a chain of frames (leaf first). Each adjacent pair (frame k+1 calls frame k) is one
weighted call edge, the way hfsort's original perf call-stack input worked. Return addresses are looked up at
addr-1. Self samples (frame 0) give the hot set.

Usage:
  fp2order.py edges  BINARY NMFILE OUTDIR SCRIPT [SCRIPT...]
  fp2order.py span   HOTJSON NMFILE [LABEL]
Exit 3 when under half of the samples' leaf frames map into the binary, or the median chain depth is
under 4 frames (frame-pointer chains not usable).
"""
import json
import os
import statistics
import sys
from collections import Counter

# the helpers of wave 2's lbr2order.py, copied (that file lives outside the harness repository)
import bisect  # noqa: E402
import re  # noqa: E402
import struct  # noqa: E402

MMAP_RE = re.compile(r"PERF_RECORD_MMAP2? \d+/\d+: \[(0x[0-9a-f]+)\((0x[0-9a-f]+)\) @ (0x[0-9a-f]+|0)[^\]]*\]: (\S+) (.+)$")


def pt_loads(path):
    with open(path, "rb") as f:
        h = f.read(64)
        assert h[:4] == b"\x7fELF" and h[4] == 2 and h[5] == 1, "ELF64 LE expected"
        phoff, = struct.unpack_from("<Q", h, 32)
        phentsize, phnum = struct.unpack_from("<HH", h, 54)
        f.seek(phoff)
        out = []
        for _ in range(phnum):
            p = f.read(phentsize)
            ptype, flags, off, vaddr, _pa, filesz, _memsz, _al = struct.unpack_from("<IIQQQQQQ", p, 0)
            if ptype == 1:
                out.append((off, vaddr, filesz, flags))
        return out


def load_nm(nmfile):
    addrs, sizes, names, seen = [], [], [], set()
    for line in open(nmfile):
        parts = line.split()
        if len(parts) != 4 or parts[2] not in "tTwW":
            continue
        a, s = int(parts[0], 16), int(parts[1], 16)
        if s == 0 or a in seen:
            continue
        seen.add(a)
        addrs.append(a)
        sizes.append(s)
        names.append(parts[3])
    return addrs, sizes, names


def lookup(addrs, sizes, va):
    i = bisect.bisect_right(addrs, va) - 1
    if i >= 0 and va < addrs[i] + sizes[i]:
        return i
    return -1


def span_stats(entries, label):
    tot_w = sum(w for _, _, w in entries) or 1
    res = {"label": label}
    for cover in (0.90, 0.99, 1.0):
        acc, sel = 0, []
        for e in sorted(entries, key=lambda e: -e[2]):
            if acc / tot_w >= cover and cover < 1.0:
                break
            sel.append(e)
            acc += e[2]
        p4, p2 = set(), set()
        for a, s, _ in sel:
            p4.update(range(a >> 12, ((a + s - 1) >> 12) + 1))
            p2.update(range(a >> 21, ((a + s - 1) >> 21) + 1))
        lo = min(a for a, _, _ in sel)
        hi = max(a + s for a, s, _ in sel)
        res["c%d" % int(cover * 100)] = {"functions": len(sel), "bytes": sum(s for _, s, _ in sel),
                                         "pages_4k": len(p4), "pages_2m": len(p2),
                                         "extent_mb": round((hi - lo) / 2**20, 2)}
    return res


def samples(path, base):
    """Yield (maps, [ip, ...]) per sample; maps is the list of exec mappings of BINARY seen so far."""
    maps, cur = [], []
    for line in open(path, errors="replace"):
        if "PERF_RECORD_MMAP" in line:
            m = MMAP_RE.search(line)
            if m and os.path.basename(m.group(5).strip()) == base and "x" in m.group(4):
                st, ln, pg = int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16)
                maps.append((st, st + ln, pg))
            continue
        t = line.split()
        if not t:
            if cur:
                yield maps, cur
            cur = []
            continue
        try:
            cur.append(int(t[0], 16))
        except ValueError:
            if cur:
                yield maps, cur
            cur = []
    if cur:
        yield maps, cur


def edges(binary, nmfile, outdir, scripts):
    loads = [l for l in pt_loads(binary) if l[3] & 1]
    addrs, sizes, names = load_nm(nmfile)
    base = os.path.basename(binary)
    cg, self_w, depth = Counter(), Counter(), []
    n = n_leaf_in = 0
    per = {}
    for sp in scripts:
        s_n = s_in = 0
        for maps, chain in samples(sp, base):
            def va(x):
                for st, en, pg in maps:
                    if st <= x < en:
                        fo = x - st + pg
                        for off, vaddr, fsz, _f in loads:
                            if off <= fo < off + fsz:
                                return fo - off + vaddr
                return None
            s_n += 1
            fn = []
            for k, ip in enumerate(chain):
                v = va(ip if k == 0 else ip - 1)
                fn.append(lookup(addrs, sizes, v) if v is not None else -1)
            if fn and fn[0] >= 0:
                s_in += 1
                self_w[fn[0]] += 1
            depth.append(len(chain))
            for k in range(len(fn) - 1):
                callee, caller = fn[k], fn[k + 1]
                if callee >= 0 and caller >= 0 and callee != caller:
                    cg[(caller, callee)] += 1
        per[os.path.basename(sp)] = {"samples": s_n, "leaf_in_binary": s_in}
        n += s_n
        n_leaf_in += s_in
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "cg.txt"), "w") as f:
        for (i, j), w in sorted(cg.items(), key=lambda kv: (-kv[1], kv[0])):
            f.write("%s %s %d\n" % (names[i], names[j], w))
    hot = [{"name": names[i], "addr": addrs[i], "size": sizes[i], "w": w} for i, w in self_w.most_common()]
    md = statistics.median(depth) if depth else 0
    stats = {"scripts": per, "samples": n, "leaf_in_binary": n_leaf_in, "median_chain_depth": md,
             "cg_edges": len(cg), "cg_weight": sum(cg.values()), "hot_functions": len(hot),
             "top_self": [h["name"][:120] for h in hot[:25]],
             "layout": span_stats([(h["addr"], h["size"], h["w"]) for h in hot], "profiled") if hot else None}
    with open(os.path.join(outdir, "hot.json"), "w") as f:
        json.dump({"stats": stats, "hot": hot}, f)
    print(json.dumps(stats, indent=1))
    if n_leaf_in < 0.5 * max(n, 1) or md < 4:
        print("FAIL: leaf frames in binary %d of %d, median chain depth %s" % (n_leaf_in, n, md), file=sys.stderr)
        sys.exit(3)


def span(hotjson, nmfile, label):
    hot = json.load(open(hotjson))["hot"]
    addrs, sizes, names = load_nm(nmfile)
    by = {}
    for a, s, nm in zip(addrs, sizes, names):
        by.setdefault(nm, (a, s))
    ent, miss = [], 0
    for h in hot:
        c = by.get(h["name"])
        if not c:
            miss += 1
            continue
        ent.append((c[0], c[1], h["w"]))
    r = span_stats(ent, label)
    r["names_missing"] = miss
    print(json.dumps(r, indent=1))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "edges":
        edges(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:])
    elif len(sys.argv) > 1 and sys.argv[1] == "span":
        span(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "other")
    else:
        sys.exit(__doc__)
