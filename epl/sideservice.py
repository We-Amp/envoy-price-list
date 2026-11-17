"""Side services in their own containers (origin with the authorization service, tracing
collector): where they run and how much CPU they use, read from the container's cgroup
files and /proc only. Nothing here calls the Docker CLI, so nothing wakes the daemon's
unpinned threads during a perf window; the container's main PID is taken once, at start.

cgroup v2 (one unified hierarchy) is read directly: cpu.stat usage_usec,
cpuset.cpus.effective (else cpuset.cpus), cgroup.procs. On cgroup v1 the cpuacct and
cpuset controllers' own directories are used (cpuacct.usage in ns, cpuset.cpus).
"""

import os

from . import sysprobe

CGROUP_ROOT = "/sys/fs/cgroup"


def parse_proc_cgroup(text):
    """{controller: path} from /proc/<pid>/cgroup; the v2 entry is under ""."""
    out = {}
    for line in text.splitlines():
        parts = line.strip().split(":", 2)
        if len(parts) != 3:
            continue
        _, ctrls, path = parts
        if not ctrls:
            out[""] = path
        for c in ctrls.split(","):
            if c:
                out[c] = path
    return out


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


class Cgroup:
    """The cgroup of one container, found from its main PID."""

    def __init__(self, pid, root=CGROUP_ROOT, proc="/proc"):
        self.pid = int(pid)
        self.root = root
        txt = _read(os.path.join(proc, str(self.pid), "cgroup"))
        if txt is None:
            raise RuntimeError("no /proc/%d/cgroup" % self.pid)
        m = parse_proc_cgroup(txt)
        self.v2 = "" in m and not any(k for k in m if k)
        if self.v2:
            self.cpu_dir = self.set_dir = os.path.join(root, m[""].lstrip("/"))
        else:
            acct = m.get("cpuacct") or m.get("cpu")
            cs = m.get("cpuset")
            if acct is None or cs is None:
                raise RuntimeError("cgroup v1 without cpuacct or cpuset for pid %d" % self.pid)
            self.cpu_dir = os.path.join(root, "cpu,cpuacct" if os.path.isdir(os.path.join(root, "cpu,cpuacct"))
                                        else "cpuacct", acct.lstrip("/"))
            self.set_dir = os.path.join(root, "cpuset", cs.lstrip("/"))
        if not os.path.isdir(self.cpu_dir):
            raise RuntimeError("cgroup directory %s missing" % self.cpu_dir)

    def usage_us(self):
        """CPU time of every task in the cgroup, microseconds; None when unreadable."""
        if self.v2:
            txt = _read(os.path.join(self.cpu_dir, "cpu.stat"))
            for line in (txt or "").splitlines():
                k, _, v = line.partition(" ")
                if k == "usage_usec":
                    return int(v)
            return None
        txt = _read(os.path.join(self.cpu_dir, "cpuacct.usage"))
        return int(txt) / 1000.0 if txt and txt.strip() else None

    def cpuset(self):
        for n in ("cpuset.cpus.effective", "cpuset.cpus"):
            txt = _read(os.path.join(self.set_dir, n))
            if txt is not None and txt.strip():
                return txt.strip()
        return None

    def pids(self):
        txt = _read(os.path.join(self.cpu_dir, "cgroup.procs")) or ""
        return sorted(int(x) for x in txt.split() if x.strip().isdigit())


class SideService:
    """One container started by the harness: name, main PID, the CPU set it must use."""

    def __init__(self, name, pid, want_cpus, root=CGROUP_ROOT, proc="/proc"):
        self.name = name
        self.want = sysprobe.parse_cpuset(want_cpus)
        self.want_text = want_cpus
        self.proc = proc
        self.cg = Cgroup(pid, root, proc)

    def placement(self):
        """{cpuset, cpuset_ok, pids, pids_ok, bad_pids}: the container's cpuset and every
        process's Cpus_allowed_list against the configured set (read outside the window)."""
        cs = self.cg.cpuset()
        out = {"want": self.want_text, "cpuset": cs,
               "cpuset_ok": cs is not None and sysprobe.parse_cpuset(cs) == self.want}
        pids = self.cg.pids()
        bad = []
        for p in pids:
            allowed = _read(os.path.join(self.proc, str(p), "status"))
            if allowed is None:
                continue  # exited between the two reads
            al = None
            for line in allowed.splitlines():
                if line.startswith("Cpus_allowed_list:"):
                    al = line.split(":", 1)[1].strip()
            if al is None or sysprobe.parse_cpuset(al) != self.want:
                bad.append({"pid": p, "cpus_allowed": al})
        out.update(pids=len(pids), pids_ok=bool(pids) and not bad, bad_pids=bad[:8])
        return out

    def usage_us(self):
        return self.cg.usage_us()


def window_record(svc, u0, u1, seconds, responses):
    """Per-leg record of one side service from usage before and after the window."""
    r = {}
    if u0 is None or u1 is None or seconds <= 0:
        r["error"] = "cgroup CPU time unreadable"
        return r
    cpu_s = (u1 - u0) / 1e6
    n = len(svc.want) or 1
    r.update(cpu_s=round(cpu_s, 4), busy_of_set=round(cpu_s / seconds / n, 5),
             cpus_used=round(cpu_s / seconds, 4))
    if responses:
        # exploratory: the service's own CPU per request, never added to Envoy's
        r["cpu_us_per_request"] = round(cpu_s * 1e6 / responses, 3)
    return r
