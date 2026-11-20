"""Scrub of a results tree before it is published.

`epl scrub RUN_DIR` rewrites home directory prefixes in the text files a run writes (by suffix).
A tree that is about to be published holds more than that: console captures, tool output with
other suffixes, compressed members, and the output of other programs (Google Benchmark's JSON
names the host it ran on and the path of the executable). `epl scrub RUN_DIR --publish` covers
those:

1. home directory prefixes (/home/<user>, /Users/<user>, /root/, $HOME) become ~ in every text
   file, whatever its suffix (.console, .out, .err, no suffix at all);
2. the same inside gzip files (a member is rewritten only when its text changes; the gzip
   header carries no time and no name, so a second pass is a no-op);
3. a `"host_name": "..."` field (Google Benchmark's context block) gets the label given with
   --host-label instead of the machine's name;
4. `"executable": "..."` fields are covered by rule 1 like any other path; they are counted
   separately so the report shows them;
5. cloud VM names of the form <vm>.<zone>.c.<project>.internal get the same label, wherever
   they stand;
6. `--name OLD=NEW` (repeatable, or one per line in --names-file) replaces a name the rules
   above cannot know, such as a bare host name in a shell prompt or a user name outside a
   path; it matches whole tokens only (not inside a longer word);
7. `--replace-file FILE` (a JSON list of [old, new] pairs) replaces exact strings.

The names of rule 6 and the strings of rule 7 are private by nature: keep those files outside
the tree that is published.

A tree with the records of several machines needs one label per machine: `--host-label DIR=LABEL`
(repeatable) or `--labels-file FILE` (one DIR=LABEL per line) gives the label for everything under
DIR, relative to RUN_DIR; the longest matching DIR wins and a plain `--host-label LABEL` is the label
elsewhere. With one label for a tree of three machines, `--check` reports every host_name of the
other two.

A file that is not UTF-8 text is not touched and is listed, so nothing binary is published
unseen. `--check` writes nothing and exits 1 when a rule would still change a file: the gate
to run on the tree before it is committed.

No measured value is changed by any rule. Hashes recorded in a run (config_sha256,
bootstrap_sha256) were computed on the text as run and may not match a scrubbed file.
"""

import gzip
import io
import json
import os
import re

from . import sysprobe

HOST_NAME_RE = re.compile(r'("host_name"\s*:\s*")((?:[^"\\]|\\.)*)(")')
EXECUTABLE_RE = re.compile(r'("executable"\s*:\s*")((?:[^"\\]|\\.)*)(")')
CLOUD_VM_RE = re.compile(r"(?<![A-Za-z0-9_.-])[a-z0-9][a-z0-9-]*\.[a-z0-9-]+\.c\.[a-z0-9-]+\.internal(?![A-Za-z0-9_-])")
RULES = ("home", "host_name", "executable", "cloud_vm", "name", "replace")


def name_pattern(name):
    """A name as a whole token: not inside a longer word, file name part or identifier."""
    return re.compile(r"(?<![A-Za-z0-9_-])%s(?![A-Za-z0-9_-])" % re.escape(name))


def parse_names(pairs):
    """["OLD=NEW", ...] -> [(pattern, NEW)]; an empty OLD or a missing = is an error."""
    out = []
    for p in pairs or []:
        old, sep, new = p.partition("=")
        if not sep or not old:
            raise ValueError("a name is OLD=NEW, got %r" % p)
        out.append((name_pattern(old), new))
    return out


def scrub_publish_text(text, host_label="host", names=(), replace=()):
    """(scrubbed text, {rule: replacements}). `names`: parse_names() output; `replace`:
    [(old, new)] exact strings."""
    n = dict.fromkeys(RULES, 0)

    def executable(m):
        new = sysprobe.scrub_text(m.group(2))
        if new != m.group(2):
            n["executable"] += 1
        return m.group(1) + new + m.group(3)

    def host(m):
        if m.group(2) == host_label:
            return m.group(0)
        n["host_name"] += 1
        return m.group(1) + host_label + m.group(3)

    def cloud(m):
        n["cloud_vm"] += 1
        return host_label

    text = EXECUTABLE_RE.sub(executable, text)
    text = HOST_NAME_RE.sub(host, text)
    text = CLOUD_VM_RE.sub(cloud, text)
    new = sysprobe.scrub_text(text)
    if new != text:
        n["home"] += len(sysprobe._HOME_RE.findall(text))
        text = new
    for pat, repl in names:
        text, k = pat.subn(lambda m, r=repl: r, text)
        n["name"] += k
    for old, repl in replace:
        k = text.count(old)
        if k:
            text = text.replace(old, repl)
            n["replace"] += k
    return text, {k: v for k, v in n.items() if v}


def _decode(data):
    """The text of a file, or None when it is not UTF-8 text."""
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def gzip_bytes(data):
    """gzip without a file name or a time in the header: the same input gives the same bytes."""
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0, compresslevel=9) as g:
        g.write(data)
    return buf.getvalue()


def parse_labels(items):
    """["LABEL" | "DIR=LABEL", ...] -> (default label, {dir: label}). A later plain label replaces
    an earlier one; DIR is relative to the tree, without a trailing slash."""
    default, by_dir = "host", {}
    for it in items or []:
        d, sep, label = it.partition("=")
        if not sep:
            default = it
        elif not d.strip("/") or not label:
            raise ValueError("a label is LABEL or DIR=LABEL, got %r" % it)
        else:
            by_dir[d.strip("/")] = label
    return default, by_dir


def label_for(rel, default, by_dir):
    """The label of a file at rel (posix, relative to the tree): the longest DIR that contains it."""
    parts = rel.split("/")
    for n in range(len(parts) - 1, 0, -1):
        hit = by_dir.get("/".join(parts[:n]))
        if hit is not None:
            return hit
    return default


def scrub_publish_tree(root, host_label="host", names=(), replace=(), check=False, labels=None):
    """Apply the rules to every file under root. Returns {"changed": {path: {rule: count}},
    "binary": [paths not text, untouched], "files": files seen}. With check=True nothing is
    written. `labels`: {dir relative to root: label} for the sub trees of other machines."""
    changed, binary, seen = {}, [], 0
    labels = labels or {}
    for d, dirs, files in os.walk(root):
        dirs.sort()
        for fn in sorted(files):
            p = os.path.join(d, fn)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            seen += 1
            rel = os.path.relpath(p, root)
            with open(p, "rb") as f:
                raw = f.read()
            gz = fn.endswith(".gz")
            if gz:
                try:
                    data = gzip.decompress(raw)
                except (OSError, EOFError):
                    binary.append(rel)
                    continue
            else:
                data = raw
            text = _decode(data)
            if text is None:
                binary.append(rel)
                continue
            new, counts = scrub_publish_text(text, label_for(rel.replace(os.sep, "/"), host_label, labels), names, replace)
            if new == text:
                continue
            changed[rel] = counts
            if check:
                continue
            out = new.encode("utf-8")
            with open(p, "wb") as f:
                f.write(gzip_bytes(out) if gz else out)
    return {"changed": changed, "binary": binary, "files": seen}


def load_names_file(path):
    with open(path) as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]


def load_replace_file(path):
    with open(path) as f:
        pairs = json.load(f)
    if not isinstance(pairs, list) or any(not isinstance(p, list) or len(p) != 2
                                          or not all(isinstance(x, str) for x in p) or not p[0] for p in pairs):
        raise ValueError("%s: a JSON list of [old, new] string pairs" % path)
    return [(p[0], p[1]) for p in pairs]
