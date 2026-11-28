#!/usr/bin/env python3
"""The side services of the flip blocks, started once per chain or daemon session.

    side.py start CONFIG STATE_JSON    start the origin (docker) and, when the config's arm traces, the collector,
                                          pinned to cpus.origin, images by digest (no pull: a missing image fails);
                                          their container IDs go to STATE_JSON (the chain's ledger)
    side.py stop STATE_JSON            stop exactly the containers STATE_JSON names, by ID, then remove each one
                                          that is still there and is ours: `docker inspect` shows the recorded full ID,
                                          the recorded name and the recorded image ID (all three recorded at start);
                                          rc 0 when none is left (running or stopped)

Nothing is matched by name or command line; only the IDs `docker run` returned are ever stopped or removed. A container
started with --rm (the nginx origin, the collector) is gone after its stop; its remove step logs "already removed".
A container that is there but does not match its record is never removed: it is reported and stop returns 1. (A
container run without --rm is stopped and then removed, so a stopped one is never left behind.)"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from epl import experiment  # noqa: E402


def log(msg):
    print("%s %s" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg), flush=True)


def inspect(cid):
    """(full ID, name without the leading '/', image ID) of a container, or None when docker has no such container."""
    r = subprocess.run(["docker", "inspect", "--format", "{{.Id}}|{{.Name}}|{{.Image}}", cid], capture_output=True,
                       text=True, timeout=30)
    if r.returncode != 0 or r.stdout.count("|") != 2:
        return None
    i, n, img = r.stdout.strip().split("|")
    return i, n.lstrip("/"), img


def record(role, cid):
    c = {"role": role, "id": cid}
    got = inspect(cid)
    if got and got[0] == cid:
        c.update(name=got[1], image=got[2])
    return c


def start(cfg_path, state_path):
    from epl.origin import Collector, Origin
    exp = experiment.load(cfg_path)
    run_dir = os.path.dirname(os.path.abspath(state_path))
    st = {"config": cfg_path, "containers": []}
    origin = Origin(exp["origin"], exp["cpus"].get("origin", ""), exp["shapes"], run_dir, log)
    try:
        origin.start()
        if origin.container_id:
            st["containers"].append(record("origin", origin.container_id))
        if experiment.needs_collector(exp):
            col = Collector(exp["collector"], exp["cpus"]["origin"], run_dir, log)
            col.start()
            st["containers"].append(record("collector", col.container_id))
    finally:
        # the ledger is written whatever happened, so the chain's stop finds every container that did start
        with open(state_path, "w") as f:
            json.dump(st, f, indent=1)
    log("side services up: %s" % ", ".join("%s %s" % (c["role"], c["id"][:12]) for c in st["containers"]))
    return 0


def stop(state_path):
    try:
        st = json.load(open(state_path))
    except (OSError, ValueError):
        log("no side-service ledger %s: nothing to stop" % state_path)
        return 0
    left = []
    for c in st.get("containers") or []:
        subprocess.run(["docker", "stop", "-t", "5", c["id"]], capture_output=True, text=True, timeout=60)
        r = subprocess.run(["docker", "ps", "-q", "--no-trunc", "--filter", "id=" + c["id"]], capture_output=True,
                           text=True, timeout=30)
        if r.stdout.strip():
            left.append(c["id"][:12])
        log("%s container %s stopped" % (c["role"], c["id"][:12]))
        why = remove_ours(c)
        if why:
            left.append(c["id"][:12])
            log("%s container %s NOT removed: %s" % (c["role"], c["id"][:12], why))
    os.replace(state_path, state_path + ".stopped")
    if left:
        log("still there (running, or stopped and not removed): %s" % left)
        return 1
    return 0


def remove_ours(c):
    """Remove the recorded container if it is still there and is ours; '' when removed or already gone, else why not."""
    got = inspect(c["id"])
    if got is None:
        log("%s container %s already removed" % (c["role"], c["id"][:12]))
        return ""
    want = (c["id"], c.get("name"), c.get("image"))
    if None in want[1:] or got != want:
        return "docker inspect shows %s, not the recorded %s" % (got, want)
    r = subprocess.run(["docker", "rm", c["id"]], capture_output=True, text=True, timeout=60)
    if r.returncode != 0 and "No such container" in r.stderr:
        # an --rm container (the daemon's side services) removes itself on stop; when docker inspect still saw it a
        # moment earlier, docker rm then finds it gone: it was removed, not left behind
        log("%s container %s already removed (docker rm: No such container)" % (c["role"], c["id"][:12]))
        return ""
    if r.returncode != 0:
        return "docker rm rc %d: %s" % (r.returncode, r.stderr.strip()[:200])
    log("%s container %s (%s) removed" % (c["role"], c["id"][:12], c["name"]))
    return ""


def main(argv):
    if len(argv) == 3 and argv[0] == "start":
        return start(argv[1], argv[2])
    if len(argv) == 2 and argv[0] == "stop":
        return stop(argv[1])
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
