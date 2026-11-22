#!/usr/bin/env python3
"""Turn `perf script --show-mmap-events -F ip,brstack` output of a profiled Envoy binary into
(1) an lld call-graph ordering file (caller callee weight) and (2) a hot-function list with layout
stats.

Usage:
  lbr2order.py edges  BINARY NMFILE OUTDIR SCRIPT [SCRIPT...]
      BINARY: unstripped ELF whose file layout equals the profiled binary (same build-id). Its file
              name must equal the file name of the profiled executable in the mmap events.
      NMFILE: `llvm-nm --defined-only --numeric-sort --print-size --no-demangle BINARY`
      Writes OUTDIR/cg.txt and OUTDIR/hot.json, prints stats as JSON. Exits 3 when under half of
      the branch records map into the binary.
  lbr2order.py span   HOTJSON NMFILE [LABEL]
      Layout stats of the hot set (from hot.json) in another binary (matched by symbol name), e.g.
      a relinked one. Prints JSON.

Method:
  - Only the binary's own executable text is counted (shared libraries, vdso and [unknown] are
    skipped): a branch address is mapped through the executable mmap of BINARY's file name to a
    file offset, then through BINARY's executable PT_LOAD segments to a virtual address.
  - Symbols: text symbols (nm types t, T, w, W) of non-zero size; at an address with aliases the
    first name in nm order is kept.
  - Every branch record (from/to) with both ends inside a function counts one hit to the source
    function and, if the target is another function, one to the target. When the target is that
    function's entry address (a call or tail call), the edge caller -> callee gets weight 1.
  - cg.txt lists edges by weight descending, then by (caller, callee) symbol index.
  - Layout stats: over the hottest functions holding 90%, 99% and 100% of the hit weight, the
    number of functions, their bytes, the 4 KB and 2 MB pages their extents touch, and the span
    from the lowest start to the highest end in MB.
"""
import bisect
import json
import os
import re
import struct
import sys
from collections import Counter, defaultdict

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
    addrs, sizes, names = [], [], []
    seen = set()
    with open(nmfile) as f:
        for line in f:
            parts = line.split()
            if len(parts) != 4 or parts[2] not in "tTwW":
                continue
            a, s = int(parts[0], 16), int(parts[1], 16)
            if s == 0 or a in seen:  # keep the first name at an address (aliases)
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
    """entries: list of (addr, size, weight) of the hot set. Pages touched by the hot set's extents."""
    tot_w = sum(w for _, _, w in entries) or 1
    res = {"label": label}
    for cover in (0.90, 0.99, 1.0):
        acc, sel = 0, []
        for e in sorted(entries, key=lambda e: -e[2]):
            if acc / tot_w >= cover and cover < 1.0:
                break
            sel.append(e)
            acc += e[2]
        pages4k, pages2m = set(), set()
        for a, s, _ in sel:
            for p in range(a >> 12, ((a + s - 1) >> 12) + 1):
                pages4k.add(p)
            for p in range(a >> 21, ((a + s - 1) >> 21) + 1):
                pages2m.add(p)
        lo = min(a for a, _, _ in sel)
        hi = max(a + s for a, s, _ in sel)
        res[f"c{int(cover * 100)}"] = {"functions": len(sel), "bytes": sum(s for _, s, _ in sel),
                                       "pages_4k": len(pages4k), "pages_2m": len(pages2m),
                                       "extent_mb": round((hi - lo) / 2**20, 2)}
    return res


def edges(binary, nmfile, outdir, scripts):
    loads = [ld for ld in pt_loads(binary) if ld[3] & 1]  # executable PT_LOAD(s)
    addrs, sizes, names = load_nm(nmfile)
    base = os.path.basename(binary)
    cg = Counter()
    hits = Counter()
    n_rec = n_in = n_samples = 0
    per_script = {}
    for sp in scripts:
        maps = []  # (start, end, pgoff)
        s_rec = s_in = 0

        def va(x):
            for st, en, pg in maps:
                if st <= x < en:
                    fo = x - st + pg
                    for off, vaddr, fsz, _f in loads:
                        if off <= fo < off + fsz:
                            return fo - off + vaddr
            return None

        with open(sp, errors="replace") as fh:
            for line in fh:
                if "PERF_RECORD_MMAP" in line:
                    m = MMAP_RE.search(line)
                    if m and os.path.basename(m.group(5).strip()) == base and "x" in m.group(4):
                        st, ln, pg = int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16)
                        maps.append((st, st + ln, pg))
                    continue
                toks = line.split()
                if not toks or "/" not in line:
                    continue
                n_samples += 1
                for t in toks:
                    if "/" not in t:
                        continue
                    p = t.split("/")
                    try:
                        fr, to = int(p[0], 16), int(p[1], 16)
                    except ValueError:
                        continue
                    s_rec += 1
                    vf, vt = va(fr), va(to)
                    if vf is None or vt is None:
                        continue
                    i, j = lookup(addrs, sizes, vf), lookup(addrs, sizes, vt)
                    if i < 0 or j < 0:
                        continue
                    s_in += 1
                    hits[i] += 1
                    if j != i:
                        hits[j] += 1
                        if vt == addrs[j]:  # a call or tail call: lands on the callee's entry
                            cg[(i, j)] += 1
        per_script[os.path.basename(sp)] = {"exec_maps": len(maps), "branch_records": s_rec, "in_binary": s_in}
        n_rec += s_rec
        n_in += s_in
        if not maps:
            print(f"WARN {sp}: no executable mmap of {base}", file=sys.stderr)
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "cg.txt"), "w") as f:
        for (i, j), w in sorted(cg.items(), key=lambda kv: (-kv[1], kv[0])):
            f.write(f"{names[i]} {names[j]} {w}\n")
    hot = [{"name": names[i], "addr": addrs[i], "size": sizes[i], "w": w} for i, w in hits.most_common()]
    stats = {"scripts": per_script, "samples": n_samples, "branch_records": n_rec, "in_binary": n_in,
             "cg_edges": len(cg), "cg_weight": sum(cg.values()), "hot_functions": len(hot),
             "layout": span_stats([(h["addr"], h["size"], h["w"]) for h in hot], "profiled")}
    with open(os.path.join(outdir, "hot.json"), "w") as f:
        json.dump({"stats": stats, "hot": hot}, f)
    print(json.dumps(stats, indent=1))
    if n_in < 0.5 * max(n_rec, 1):
        print("FAIL: under half of the branch records map into the binary", file=sys.stderr)
        sys.exit(3)


def span(hotjson, nmfile, label):
    with open(hotjson) as f:
        hot = json.load(f)["hot"]
    addrs, sizes, names = load_nm(nmfile)
    by = defaultdict(list)
    for a, s, n in zip(addrs, sizes, names):
        by[n].append((a, s))
    ent, miss = [], 0
    for h in hot:
        c = by.get(h["name"])
        if not c:
            miss += 1
            continue
        a, s = c[0]
        ent.append((a, s, h["w"]))
    r = span_stats(ent, label)
    r["names_missing"] = miss
    print(json.dumps(r, indent=1))
    return r


def main(argv):
    if len(argv) >= 5 and argv[1] == "edges":
        edges(argv[2], argv[3], argv[4], argv[5:])
    elif len(argv) >= 4 and argv[1] == "span":
        span(argv[2], argv[3], argv[4] if len(argv) > 4 else "other")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
