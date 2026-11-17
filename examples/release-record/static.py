#!/usr/bin/env python3
"""Static record of official Envoy release binaries (release record/1, step 0).

    python3 -I examples/release-record/static.py OUT.json BINARY:TAG:SHA256 ...

For every binary: size, sha256 (checked against the digest given, which is the GitHub
release asset digest), `--version`, section sizes (`.text`, `.rodata`, `.eh_frame`,
the rest of the allocated sections), the compiler string (`.comment`), the GNU build
id, and whether a symbol table is present. No measurement legs; needs `readelf`.
"""

import hashlib
import json
import os
import re
import subprocess
import sys


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sections(path):
    out = subprocess.run(["readelf", "-S", "-W", path], capture_output=True, text=True, check=True).stdout
    secs = {}
    for line in out.splitlines():
        m = re.match(r"\s*\[\s*\d+\]\s+(\S+)\s+(\S+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\S+\s*(\S*)", line)
        if m and m.group(1) != "NULL":
            secs[m.group(1)] = {"type": m.group(2), "size": int(m.group(5), 16), "flags": m.group(6)}
    return secs


def comment(path):
    out = subprocess.run(["readelf", "-p", ".comment", path], capture_output=True, text=True).stdout
    return sorted({m.group(1).strip() for m in re.finditer(r"\]\s+(.*)", out)})


def build_id(path):
    out = subprocess.run(["readelf", "-n", path], capture_output=True, text=True).stdout
    m = re.search(r"Build ID:\s*([0-9a-f]+)", out)
    return m.group(1) if m else None


def version(path):
    p = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=60)
    out = (p.stdout + p.stderr).strip()
    if not out:
        return None
    # the last line is "<binary path>  version: <commit>/<version>/..."; keep the text after
    # "version: " so the record does not carry the local path
    return out.splitlines()[-1].split("version: ", 1)[-1]


def record(path, tag, want):
    secs = sections(path)
    alloc = {k: v for k, v in secs.items() if "A" in v["flags"]}
    named = (".text", ".rodata", ".eh_frame")
    got = sha256(path)
    return {
        "tag": tag, "file": os.path.basename(path), "size": os.path.getsize(path),
        "sha256": got, "digest": want, "digest_ok": got == want,
        "version": version(path), "build_id": build_id(path), "comment": comment(path),
        "symtab": ".symtab" in secs, "debug_sections": sorted(k for k in secs if k.startswith(".debug")),
        "sections": {k: secs[k]["size"] if k in secs else None for k in named},
        "alloc_rest": sum(v["size"] for k, v in alloc.items() if k not in named),
        "alloc_total": sum(v["size"] for v in alloc.values()),
        "all_sections": {k: v["size"] for k, v in secs.items()},
    }


def main():
    out, items = sys.argv[1], sys.argv[2:]
    recs = []
    for it in items:
        path, tag, want = it.rsplit(":", 2)
        recs.append(record(os.path.expanduser(path), tag, want))
    with open(out, "w") as f:
        json.dump({"record": "release-record/1 static", "binaries": recs}, f, indent=1)
        f.write("\n")
    for r in recs:
        s = r["sections"]
        print("%-9s %10d %s ok=%s text=%s rodata=%s eh=%s rest=%s symtab=%s %s" % (
            r["tag"], r["size"], r["sha256"][:12], r["digest_ok"], s[".text"], s[".rodata"], s[".eh_frame"],
            r["alloc_rest"], r["symtab"], "; ".join(r["comment"])))
    sys.exit(0 if all(r["digest_ok"] for r in recs) else 1)


if __name__ == "__main__":
    main()
