#!/usr/bin/env python3
"""Fold `perf script -F comm,pid,tid,cpu,period,event,ip,sym,dso` (stdin) into one line per distinct stack:
    comm;frame_root;...;frame_leaf <TAB> period_sum <TAB> samples
Kernel frames carry the suffix _[k]; a frame without a symbol is [dso basename]. Unparsed headers are
counted on stderr."""
import collections
import re
import sys

HEAD = re.compile(r"^(?P<comm>.*?)\s+(?P<pid>-?\d+)(?:/(?P<tid>-?\d+))?\s+\[(?P<cpu>\d+)\]\s+(?:[\d.]+:\s+)?(?P<period>\d+)\s+(?P<event>[^\s:]+)")
FRAME = re.compile(r"^\s+(?P<ip>[0-9a-f]+)\s+(?P<sym>.*?)\s+\((?P<dso>[^()]*(?:\([^()]*\))?[^()]*)\)\s*$")


def main():
    acc = collections.defaultdict(lambda: [0, 0])
    cur, frames, bad = None, [], 0

    def flush():
        if cur is not None:
            k = ";".join([cur[0]] + frames[::-1])
            acc[k][0] += cur[1]
            acc[k][1] += 1

    for line in sys.stdin:
        if not line.strip():
            flush()
            cur, frames = None, []
            continue
        if line[0] not in " \t":
            flush()
            frames = []
            m = HEAD.match(line)
            if not m:
                bad += 1
                cur = None
                continue
            cur = (m.group("comm").strip().replace(";", ":").replace(" ", "_"), int(m.group("period")))
            continue
        m = FRAME.match(line)
        if not m or cur is None:
            continue
        sym, dso = m.group("sym"), m.group("dso")
        sym = re.sub(r"\+0x[0-9a-f]+$", "", sym)
        kern = dso.startswith("[kernel") or dso.endswith(".ko") or dso == "[unknown]" and int(m.group("ip"), 16) >= 0xffff800000000000
        if sym == "[unknown]" or not sym:
            sym = "[%s]" % dso.rsplit("/", 1)[-1]
        frames.append(sym.replace(";", ":").replace(" ", "_") + ("_[k]" if kern else ""))
    flush()
    for k, (p, n) in sorted(acc.items(), key=lambda kv: -kv[1][0]):
        sys.stdout.write("%s\t%d\t%d\n" % (k, p, n))
    sys.stderr.write("fold: %d stacks, %d samples, %d unparsed headers\n" % (len(acc), sum(v[1] for v in acc.values()), bad))


if __name__ == "__main__":
    main()
