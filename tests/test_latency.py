"""Run L (flush latency): the probe's schedule and log, the window classification, the sham
A/A, the connection map, the one-to-one pins, the cells, every new gate (with a failing case),
the receiver's classing and drain, the configs and the table."""

import atexit
import copy
import gzip
import importlib.util
import io
import json
import os
import random
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from epl import evidence, experiment, latency, latprobe, statsrow, validity
from epl import leg as legmod
from epl.sim import SimBackend

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SF = os.path.join(HERE, "examples", "stats-flush")
X86 = os.path.join(SF, "bench-x86_64")


def _mod(name, path):
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    finally:
        sys.path.pop(0)


MK = _mod("sf_make_lat", os.path.join(SF, "make.py"))
SESS = _mod("sf_session_lat", os.path.join(SF, "session.py"))
TAB = _mod("sf_lat_table", os.path.join(SF, "lat_table.py"))
MS = 1000000


def box():
    with open(os.path.join(SF, "boxes", "bench-x86_64.json")) as f:
        return json.load(f)


# The run-L configs as make.py writes them without a calibration, in a directory of this test
# run: on the box the files beside make.py are rewritten from its calibration (and knobs), and
# these tests must pass there too (smoke rule S-2).
GEN = tempfile.mkdtemp(prefix="epl-lat-test-")
atexit.register(shutil.rmtree, GEN, True)
for _fn, _c in MK.lat_configs(box(), None).items():
    with open(os.path.join(GEN, _fn), "w") as _f:
        json.dump(_c, _f, indent=1)


# ---------------------------------------------------------------- a local server for the probe

class Server:
    """Keep-alive HTTP server on loopback: 4,096-byte bodies; `stall` = (connection index,
    request index, seconds) sleeps once before that response."""

    def __init__(self, stall=None, chunked_ready=False):
        self.stall, self.chunked_ready = stall, chunked_ready
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(256)
        self.port = self.sock.getsockname()[1]
        self.n = 0
        self.stop = False
        self.t = threading.Thread(target=self._accept, daemon=True)
        self.t.start()

    def _accept(self):
        while not self.stop:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            idx, self.n = self.n, self.n + 1
            threading.Thread(target=self._serve, args=(c, idx), daemon=True).start()

    def _serve(self, c, idx):
        buf, k = b"", 0
        body = b"x" * 4096
        try:
            while True:
                while b"\r\n\r\n" not in buf:
                    d = c.recv(65536)
                    if not d:
                        return
                    buf += d
                head, buf = buf.split(b"\r\n\r\n", 1)
                if self.stall and self.stall[0] == idx and self.stall[1] == k:
                    time.sleep(self.stall[2])
                if head.startswith(b"GET /ready"):
                    if self.chunked_ready:
                        c.sendall(b"HTTP/1.1 200 OK\r\ntransfer-encoding: chunked\r\n\r\n5\r\nLIVE\n\r\n0\r\n\r\n")
                    else:
                        c.sendall(b"HTTP/1.1 200 OK\r\ncontent-length: 5\r\n\r\nLIVE\n")
                else:
                    c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 4096\r\n\r\n" + body)
                k += 1
        except OSError:
            return
        finally:
            c.close()

    def close(self):
        self.stop = True
        self.sock.close()


def run_probe(server, conns=4, max_s=1.6, period_ms=20, admin=True, ctl=1):
    data = [socket.create_connection(("127.0.0.1", server.port)) for _ in range(conns)]
    time.sleep(0.05)  # the server has accepted them in order
    ctls = [socket.create_connection(("127.0.0.1", server.port)) for _ in range(ctl)]
    cfg = {"data_req": latprobe.request_bytes("/s", "x"), "ctl_req": latprobe.request_bytes("/s", "x"),
           "admin_req": latprobe.request_bytes("/ready", "x", close=True),
           "data_period_ns": period_ms * MS, "data_stagger_ns": 1250000, "ctl_period_ns": 40 * MS,
           "admin_period_ns": 50 * MS, "gap_ns": 50 * MS, "drain_ns": 3000 * MS, "start_delay_ns": 20 * MS,
           "max_ns": int(max_s * 1e9)}
    rows, gaps, events = [], [], []
    run = latprobe.run_streams(data, ctls, ("127.0.0.1", server.port) if admin else None, cfg, [], rows, gaps,
                               events)
    for s in data + ctls:
        s.close()
    return rows, gaps, events, run, cfg


class ProbeTest(unittest.TestCase):
    def test_open_loop_schedule_and_catch_up_ramp(self):
        # connection 1 stalls 500 ms once, on its 10th request
        srv = Server(stall=(1, 10, 0.5))
        try:
            rows, gaps, events, run, cfg = run_probe(srv)
        finally:
            srv.close()
        self.assertEqual(events, [])
        self.assertTrue(run["drained"])
        per = cfg["data_period_ns"]
        for conn in range(4):
            mine = [r for r in rows if r[0] == "d" and r[1] == conn]
            # intended times fixed in advance: base + phase + k x period, nothing skipped
            self.assertEqual([r[2] for r in mine], list(range(len(mine))))
            first = run["base_ns"] + conn * cfg["data_stagger_ns"]
            self.assertEqual([r[3] for r in mine], [first + k * per for k in range(len(mine))])
            # planned = sent = answered: every intended time up to the stop went out and came back
            planned = (run["stop_ns"] - first) // per + 1
            self.assertEqual(len(mine), planned)
            self.assertTrue(all(r[4] is not None and r[5] is not None and r[6] == 200 and r[7] > 4096 for r in mine))
            # no pipelining: a request goes out only after the previous response is complete
            for a, b in zip(mine, mine[1:]):
                self.assertGreaterEqual(b[4], a[5])
            lat = [(r[5] - r[3]) / 1e6 for r in mine]
            if conn != 1:
                self.assertLess(max(lat), 100.0)
                continue
            # latency from the intended time: the stalled request and a ramp of the ones queued behind
            # it, about 500, 480, 460 ... ms, not one long sample
            self.assertGreater(lat[10], 480.0)
            ramp = lat[10:30]
            self.assertGreaterEqual(sum(1 for x in ramp if x > 100.0), 15)
            for k in range(1, 15):
                self.assertAlmostEqual(ramp[k], ramp[0] - 20.0 * k, delta=30.0)
            self.assertLess(lat[-1], 100.0)   # caught up before the end
            # sent when the connection freed, not at the intended time
            self.assertGreater((mine[11][4] - mine[11][3]) / 1e6, 400.0)
            late = latency.lateness_record(rows, run["base_ns"] / 1e9, run["stop_ns"] / 1e9)
            self.assertLess(late["p99_ms"], 20.0)   # lateness is against the moment the connection freed

    def test_admin_is_concurrent_and_control_runs(self):
        srv = Server(chunked_ready=True)
        try:
            rows, gaps, events, run, cfg = run_probe(srv, conns=2, max_s=0.6)
        finally:
            srv.close()
        adm = [r for r in rows if r[0] == "a"]
        self.assertGreaterEqual(len(adm), 10)
        self.assertEqual([r[3] for r in adm], [adm[0][3] + k * cfg["admin_period_ns"] for k in range(len(adm))])
        self.assertTrue(all(r[5] is not None and r[6] == 200 for r in adm))
        ctl = [r for r in rows if r[0] == "c"]
        self.assertGreaterEqual(len(ctl), 10)
        s = latprobe.summarize(rows, events, gaps, run)
        self.assertEqual(s["data"]["planned"], s["data"]["done"])
        self.assertEqual(s["admin"]["errors"], 0)

    def test_closed_connection_is_recorded_never_reopened(self):
        srv = Server()
        data = [socket.create_connection(("127.0.0.1", srv.port)) for _ in range(2)]
        cfg = {"data_req": b"GET /s HTTP/1.1\r\nHost: x\r\n\r\n", "ctl_req": b"", "admin_req": b"",
               "data_period_ns": 20 * MS, "data_stagger_ns": MS, "ctl_period_ns": 40 * MS, "gap_ns": 50 * MS,
               "drain_ns": 500 * MS, "start_delay_ns": 10 * MS, "max_ns": 400 * MS}
        rows, gaps, events = [], [], []

        def kill():
            time.sleep(0.15)
            data[0].shutdown(socket.SHUT_RDWR)
        threading.Thread(target=kill, daemon=True).start()
        try:
            run = latprobe.run_streams(data, [], None, cfg, [], rows, gaps, events)
        finally:
            srv.close()
        self.assertTrue(any(e["stream"] == "d" and e["conn"] == 0 for e in events))
        n0, n1 = (sum(1 for r in rows if r[1] == c) for c in (0, 1))
        self.assertLess(n0, n1)   # the dead connection planned nothing more: the count gate sees it
        self.assertEqual(srv.n, 2)  # no new connection was opened
        self.assertIn("stop_ns", run)

    def test_main_writes_log_and_summary_and_stops_on_sigterm(self):
        # the whole process, with the map phase stood in for (no /proc/<envoy> here): 16 connections
        d = tempfile.mkdtemp()
        srv = Server()
        helper = os.path.join(d, "run.py")
        with open(helper, "w") as f:
            f.write("""
import socket, sys
sys.path.insert(0, %r)
from epl import latprobe

def fake_map(a, req, events):
    kept = [(socket.create_connection(("127.0.0.1", a.listener_port)), 501 + i // 4, 50.0) for i in range(16)]
    threads = {str(501 + i): {"comm": "wrk:worker_%%d" %% i, "cpus": str(i)} for i in range(4)}
    rec = {"ok": True, "workers_found": 4, "opens": 16, "min_margin": 50.0, "threads": threads,
           "per_worker": {str(501 + i): 4 for i in range(4)},
           "connections": [{"conn": i, "tid": t, "comm": "wrk:worker_%%d" %% (i // 4), "cpus": str(i // 4),
                            "margin": m, "local_port": s.getsockname()[1]} for i, (s, t, m) in enumerate(kept)]}
    return kept, rec

latprobe.map_phase = fake_map
latprobe.wrk_threads = lambda pid, proc="/proc": {501 + i: {"comm": "wrk:worker_%%d" %% i, "cpus": str(i)}
                                                  for i in range(4)}
sys.exit(latprobe.main(sys.argv[1:]))
""" % HERE)
        summ, log = os.path.join(d, "p.json"), os.path.join(d, "p.jsonl.gz")
        p = subprocess.Popen([sys.executable, helper, "--listener-port", str(srv.port), "--admin-port", str(srv.port),
                              "--origin-port", str(srv.port), "--envoy-pid", "1", "--out-log", log,
                              "--out-summary", summ, "--drain-s", "3"])
        try:
            end = time.time() + 20
            while not os.path.exists(summ + ".ready") and time.time() < end and p.poll() is None:
                time.sleep(0.02)
            self.assertTrue(os.path.exists(summ + ".ready"))
            self.assertFalse(os.path.exists(summ))
            time.sleep(1.2)
            t_stop = time.monotonic_ns()
            p.send_signal(signal.SIGTERM)
            self.assertEqual(p.wait(timeout=20), 0)
            with open(summ) as f:
                sm = json.load(f)
            probe = latency.load_probe(log)
        finally:
            if p.poll() is None:
                p.kill()
            srv.close()
            shutil.rmtree(d)
        self.assertEqual(probe["meta"]["columns"][3:6], ["intended_ns", "sent_ns", "done_ns"])
        self.assertIsNotNone(probe["end"])
        self.assertTrue(sm["run"]["drained"] and sm["map_end"]["unchanged"])
        # one CLOCK_MONOTONIC for every process of the box: what the whole run rests on (on other
        # systems Python's monotonic clock may start with the process, so only checked on Linux)
        linux = sys.platform.startswith("linux")
        if linux:
            self.assertLess(abs(sm["run"]["stop_ns"] - t_stop), 200 * MS)
        self.assertEqual(sm["data"]["planned"], sm["data"]["done"])
        self.assertEqual(sm["data"]["errors"] + sm["control"]["errors"] + sm["admin"]["errors"], 0)
        # 16 connections x 50 per second, phases 1.25 ms apart; nothing intended after the stop
        d_rows = [r for r in probe["rows"] if r[0] == "d"]
        self.assertEqual({r[1] for r in d_rows}, set(range(16)))
        base = sm["run"]["base_ns"]
        self.assertEqual(sorted({r[3] for r in d_rows if r[2] == 0}), [base + i * 1250000 for i in range(16)])
        self.assertLessEqual(max(r[3] for r in probe["rows"]), sm["run"]["stop_ns"])
        secs = (sm["run"]["stop_ns"] - base) / 1e9
        self.assertAlmostEqual(len(d_rows), 800 * secs, delta=17)
        self.assertAlmostEqual(sum(1 for r in probe["rows"] if r[0] == "a"), 20 * secs, delta=2)
        self.assertAlmostEqual(sum(1 for r in probe["rows"] if r[0] == "c"), 50 * secs, delta=3)
        # the record the leg builds from these files: counts against rate x window, the map, the clock
        t0, t1 = base / 1e9 + 0.1, base / 1e9 + 1.0
        rec = latency.probe_record(probe, sm, t0, t1, CFG)
        self.assertLessEqual(rec["data_count_error"], 16)
        self.assertEqual((rec["data_unanswered"], rec["data_errors"], rec["data_non200"], rec["finished"]),
                         (0, 0, 0, True))
        mrec, groups = latency.map_record(sm, 4, 4, 0)
        self.assertTrue(mrec["ok"] and mrec["unchanged_at_end"] and mrec["one_cpu_each"])
        self.assertEqual(len(groups["cpu0"]), 4)
        pair = {"monotonic_ns": time.monotonic_ns(), "time_ns": time.time_ns()}
        ck = latency.clock_record(probe["rows"], [], t0, t1, [pair], [sm["clock_start"], sm["clock_end"]],
                                  sm["run"]["stop_ns"], latency.params())
        self.assertIsNotNone(ck["pair_error_ms"])
        if linux:
            self.assertLess(ck["pair_error_ms"], 1.0)

    def test_main_without_a_map_exits_with_the_reason(self):
        d = tempfile.mkdtemp()
        try:
            summ = os.path.join(d, "p.json")
            r = subprocess.run([sys.executable, os.path.join(HERE, "epl", "latprobe.py"), "--listener-port", "1",
                                "--admin-port", "1", "--origin-port", "1", "--envoy-pid", "999999999",
                                "--out-log", os.path.join(d, "p.jsonl.gz"), "--out-summary", summ], timeout=30)
            self.assertEqual(r.returncode, 3)
            with open(summ) as f:
                self.assertIn("0 wrk: threads", json.load(f)["error"])
            self.assertFalse(os.path.exists(summ + ".ready"))
        finally:
            shutil.rmtree(d)

    def test_response_reader(self):
        r = latprobe.Resp()
        self.assertFalse(r.feed(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nab"))
        self.assertTrue(r.feed(b"cde"))
        self.assertEqual((r.status, r.got), (200, 43))
        r = latprobe.Resp()
        self.assertFalse(r.feed(b"HTTP/1.1 503 x\r\ntransfer-encoding: chunked\r\n\r\n3\r\nabc\r\n"))
        self.assertTrue(r.feed(b"0\r\n\r\n"))
        self.assertEqual(r.status, 503)
        r = latprobe.Resp()
        r.feed(b"HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\n")
        self.assertRaises(ValueError, r.feed, b"ab")
        r = latprobe.Resp()
        self.assertFalse(r.feed(b"HTTP/1.1 200 OK\r\nx: y\r\n\r\nLIVE"))
        self.assertTrue(r.to_eof)


class MapTest(unittest.TestCase):
    """The per-worker connection map: owner by scheduler run time, exactly 4 per worker."""

    class C:
        def __init__(self, owner):
            self.owner, self.closed = owner, False

        def close(self):
            self.closed = True

    def run_map(self, owners, noise=0, quiet=1000, busy=6000000, **kw):
        tids = [11, 12, 13, 14]
        it = iter(owners)
        opened = []

        def open_conn():
            c = self.C(next(it))
            opened.append(c)
            return c

        def measure(c):
            before = {t: 0 for t in tids}
            after = {t: (busy if t == c.owner else quiet) + noise for t in tids}
            return before, after
        return latprobe.map_connections(open_conn, measure, tids, **kw) + (opened,)

    def test_decide(self):
        self.assertEqual(latprobe.map_decide({1: 10, 2: 10}, {1: 6000010, 2: 1010})[:2], (1, 6000.0))
        self.assertEqual(latprobe.map_decide({1: 10, 2: 10}, {1: 10, 2: 10})[0], None)
        self.assertEqual(latprobe.map_decide({1: 0}, {1: 5})[:2], (1, 5.0))

    def test_exact_balance_gives_four_each(self):
        kept, attempts, ok, opened = self.run_map([11, 12, 13, 14] * 4)
        self.assertTrue(ok)
        self.assertEqual(len(kept), 16)
        self.assertEqual(sorted(t for _, t, _ in kept), sorted([11, 12, 13, 14] * 4))
        self.assertFalse(any(c.closed for c in opened))

    def test_full_worker_is_closed_and_others_filled(self):
        owners = [11] * 6 + [12, 13, 14] * 4
        kept, attempts, ok, opened = self.run_map(owners)
        self.assertTrue(ok)
        self.assertEqual(sum(1 for _, t, _ in kept if t == 11), 4)
        self.assertEqual(sum(1 for c in opened if c.closed), 2)
        self.assertEqual([a["why"] for a in attempts if not a["kept"]], ["worker full"] * 2)

    def test_unclear_owner_is_not_kept(self):
        # the next thread ran a quarter as much (a flush on every worker during the 100 requests): under 5x
        kept, attempts, ok, opened = self.run_map([11] * 64, quiet=2000000)
        self.assertFalse(ok)
        self.assertEqual(kept, [])
        self.assertTrue(all(a["why"] == "no clear owner" for a in attempts))

    def test_gives_up_after_the_limit(self):
        kept, attempts, ok, opened = self.run_map([11] * 64, max_opens=64)
        self.assertFalse(ok)
        self.assertEqual(len(attempts), 64)
        self.assertEqual(len(kept), 4)

    def test_groups_from_the_map(self):
        s = synth_summary()
        rec, groups = latency.map_record(s, 4, 4, 0)
        self.assertEqual(groups["cpu0"], {0, 1, 2, 3})
        self.assertEqual(groups["others"], set(range(4, 16)))
        self.assertTrue(rec["ok"] and rec["one_cpu_each"] and rec["unchanged_at_end"])
        self.assertEqual((rec["per_worker_min"], rec["per_worker_max"], rec["cpu0_connections"]), (4, 4, 4))


# ---------------------------------------------------------------- one CPU per worker, on a made-up /proc

def fake_proc(root, pid, threads):
    """threads: {tid: (comm, allowed list text, last cpu)}; the main thread is tid = pid."""
    for tid, (comm, allowed, last) in threads.items():
        d = os.path.join(root, str(pid), "task", str(tid))
        os.makedirs(d)
        with open(os.path.join(d, "comm"), "w") as f:
            f.write(comm + "\n")
        with open(os.path.join(d, "status"), "w") as f:
            f.write("Name:\t%s\nCpus_allowed_list:\t%s\n" % (comm, allowed))
        with open(os.path.join(d, "stat"), "w") as f:
            f.write("%d (%s) S %s %d %s\n" % (tid, comm, " ".join(["0"] * 35), last, " ".join(["0"] * 5)))
        with open(os.path.join(d, "schedstat"), "w") as f:
            f.write("%d %d 7\n" % (1000 * tid, 10 * tid))


class PinTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.old = legmod.PROC
        legmod.PROC = self.root

    def tearDown(self):
        legmod.PROC = self.old
        shutil.rmtree(self.root)

    def threads(self, main=("envoy", "4", 4), workers=None):
        t = {500: main}
        for i in range(4):
            t[501 + i] = ("wrk:worker_%d" % i, str(i), i)
        t.update(workers or {})
        t[520] = ("GrpcGoogClient", "4", 4)
        return t

    def test_plan(self):
        self.assertEqual(legmod.one_to_one_plan({7: "wrk:worker_1", 5: "wrk:worker_0"}, {2, 3}), {5: 2, 7: 3})
        self.assertIsNone(legmod.one_to_one_plan({7: "wrk:worker_1", 5: "wrk:worker_1"}, {2, 3}))
        self.assertIsNone(legmod.one_to_one_plan({7: "wrk:worker_2", 5: "wrk:worker_0"}, {2, 3}))
        self.assertIsNone(legmod.one_to_one_plan({5: "wrk:other"}, {2}))

    def test_own_core(self):
        fake_proc(self.root, 500, self.threads())
        r = legmod.pin_check(500, 4, {0, 1, 2, 3}, 4, one_to_one=True)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["one_to_one"], {"501": 0, "502": 1, "503": 2, "504": 3})

    def test_shared_core(self):
        fake_proc(self.root, 500, self.threads(main=("envoy", "0", 0)))
        self.assertTrue(legmod.pin_check(500, 0, {0, 1, 2, 3}, 4, one_to_one=True)["ok"])
        # the main thread somewhere else: not the shared-core shape
        shutil.rmtree(os.path.join(self.root, "500"))
        fake_proc(self.root, 500, self.threads(main=("envoy", "0-3", 2)))
        self.assertFalse(legmod.pin_check(500, 0, {0, 1, 2, 3}, 4, one_to_one=True)["ok"])

    def test_failing_cases(self):
        cases = {
            "worker allowed on the whole set": {502: ("wrk:worker_1", "0-3", 1)},
            "worker last ran on another CPU": {503: ("wrk:worker_2", "2", 1)},
            "worker on a wrong single CPU": {504: ("wrk:worker_3", "2", 2)},
        }
        for name, over in cases.items():
            root = tempfile.mkdtemp()
            legmod.PROC = root
            try:
                fake_proc(root, 500, self.threads(workers=over))
                r = legmod.pin_check(500, 4, {0, 1, 2, 3}, 4, one_to_one=True)
                self.assertFalse(r["ok"], name)
                self.assertEqual(r["bad_workers"], list(over), name)
            finally:
                shutil.rmtree(root)
        legmod.PROC = self.root

    def test_five_threads_or_wrong_names(self):
        fake_proc(self.root, 500, self.threads(workers={505: ("wrk:worker_4", "3", 3)}))
        self.assertFalse(legmod.pin_check(500, 4, {0, 1, 2, 3}, 4, one_to_one=True)["ok"])

    def test_pin_rung_sets_one_cpu_each(self):
        fake_proc(self.root, 500, self.threads())
        calls = {}
        old = legmod._set_affinity
        legmod._set_affinity = lambda tid, cpus: calls.__setitem__(tid, set(cpus))
        try:
            r = legmod.pin_rung(500, 4, {0, 1, 2, 3}, 4, wait_s=0.1, one_to_one=True)
        finally:
            legmod._set_affinity = old
        self.assertTrue(r["ok"], r)
        self.assertEqual(calls, {501: {0}, 502: {1}, 503: {2}, 504: {3}})

    def test_rung_of_and_validation(self):
        exp = experiment.load(os.path.join(GEN, "lat.json"))
        own, shared = exp["shapes"]
        self.assertEqual((own["main_cpu"], shared["main_cpu"]), (4, 0))
        ro, rs = legmod.rung_of(exp, own), legmod.rung_of(exp, shared)
        self.assertTrue(ro["one_to_one"] and rs["one_to_one"])
        self.assertEqual((ro["sut_set"], rs["sut_set"]), ({0, 1, 2, 3, 4}, {0, 1, 2, 3}))
        self.assertEqual((ro["start_cpus"], rs["start_cpus"]), ("4", "0"))
        # without main_shares_worker the old rule stands for that shape
        bad = copy.deepcopy(exp)
        bad["shapes"][1].pop("main_shares_worker")
        self.assertTrue(any("main_cpu outside" in e for e in experiment.validate(bad, allow_short=True)))
        bad = copy.deepcopy(exp)
        bad["shapes"][0]["main_shares_worker"] = True
        self.assertTrue(any("main_cpu inside" in e for e in experiment.validate(bad, allow_short=True)))


class SamplerTest(unittest.TestCase):
    def test_thread_series_run_and_wait(self):
        root = tempfile.mkdtemp()
        try:
            fake_proc(root, 500, {500: ("envoy", "4", 4), 501: ("wrk:worker_0", "0", 0)})
            s = statsrow.ThreadSampler(500, [500, 501, 999], 0.005, None, proc=root)
            s.start()
            time.sleep(0.2)
            s.stop_evt.set()
            s.join(timeout=5)
            self.assertGreaterEqual(len(s.series[500]), 10)
            self.assertEqual(s.series[501][0][1:], (501000, 5010))
            self.assertEqual(s.main_samples(500)[0][1], 500000)
            # a thread that cannot be read is counted on every round, never skipped silently
            self.assertEqual(s.series[999], [])
            self.assertGreaterEqual(s.missing, 10)
            self.assertEqual(statsrow.find_bursts(s.main_samples(500)), [])
        finally:
            shutil.rmtree(root)


# ---------------------------------------------------------------- synthetic legs

CFG = dict(MK.LAT_PROBE, cpu0=0, workers=4, interval_s=10.0)


def synth_summary(per_worker=4, margin=40.0, unchanged=True, pair_ns=0):
    conns = [{"conn": i, "tid": 501 + i // 4, "comm": "wrk:worker_%d" % (i // 4), "cpus": str(i // 4),
              "margin": margin, "local_port": 40000 + i} for i in range(16)]
    threads = {str(501 + i): {"comm": "wrk:worker_%d" % i, "cpus": str(i)} for i in range(4)}
    return {"map": {"ok": True, "workers_found": 4, "opens": 16, "requests": 1600, "min_margin": margin,
                    "connections": conns,
                    "per_worker": {str(501 + i): per_worker for i in range(4)}, "threads": threads},
            "map_end": {"unchanged": unchanged},
            "clock_start": {"monotonic_ns": 5 * 10 ** 9, "time_ns": 10 ** 18 + 5 * 10 ** 9 + pair_ns},
            "clock_end": {"monotonic_ns": 90 * 10 ** 9, "time_ns": 10 ** 18 + 90 * 10 ** 9 + pair_ns},
            "run": {"stop_ns": None, "drained": True}, "exit": 0, "cpus_allowed": [31]}


def synth(t0=1000.0, window=60.0, interval=10.0, flush_s=0.3, first=4.0, base_us=400.0, in_us=0.0,
          cpu0_in_us=0.0, onset_us=0.0, seed=1, hz=50, period_s=0.005, wait_cpu0_in=0.0, admin_wait=True,
          extra_burst=None, noise_us=30.0):
    """One synthetic leg: flushes every `interval` from t0 + first, `flush_s` long; the main
    thread busy in them; data probes at 16 x hz with latency base + noise, plus in_us inside a
    flush (plus cpu0_in_us on the connections of the worker on CPU 0, plus onset_us in the first
    50 ms); admin probes wait for the flush end. Returns the inputs of latency.leg_record."""
    rnd = random.Random(seed)
    t1 = t0 + window
    flushes = []
    s = t0 + first
    while s < t1 + 5:
        flushes.append((s, s + flush_s))
        s += interval
    if extra_burst:
        flushes.append(extra_burst)
        flushes.sort()

    def flush_at(t):
        for a, b in flushes:
            if a <= t < b:
                return a, b
        return None
    series = {500: [], 501: [], 502: [], 503: [], 504: []}
    run = {t: 0 for t in series}
    wait = {t: 0 for t in series}
    n = int(round(window / period_s)) + 1
    for i in range(n):
        t = t0 + i * period_s
        for tid in series:
            series[tid].append((t, run[tid], wait[tid]))
        busy = flush_at(t + period_s / 2) is not None
        run[500] += int(period_s * 1e9) if busy else 0
        for tid in (501, 502, 503, 504):
            run[tid] += int(0.3 * period_s * 1e9)
            wait[tid] += int((max(wait_cpu0_in, 0.0001) if (tid == 501 and busy) else 0.0001) * period_s * 1e9)
    rows = []
    per = int(1e9 / hz)
    start = int((t0 - 3.0) * 1e9)
    end = int((t1 + 1.0) * 1e9)
    for c in range(16):
        k, ts = 0, start + c * 1250000
        while ts <= end:
            f = flush_at(ts / 1e9)
            lat = base_us + rnd.random() * noise_us
            if f:
                lat += in_us + (cpu0_in_us if c < 4 else 0.0)
                if ts / 1e9 - f[0] <= 0.05:
                    lat += onset_us
            sent = ts + 5000
            rows.append(["d", c, k, ts, sent, ts + int(lat * 1000), 200, 4300])
            k += 1
            ts += per
    k, ts = 0, start + 300000
    while ts <= end:
        f = flush_at(ts / 1e9)
        lat = (f[1] - ts / 1e9) * 1e6 + 300 if (f and admin_wait) else 300.0
        rows.append(["a", 0, k, ts, ts + 4000, ts + int(lat * 1000), 200, 120])
        k += 1
        ts += 50 * MS
    for c in range(2):
        k, ts = 0, start + 600000 + c * 20 * MS
        while ts <= end:
            rows.append(["c", c, k, ts, ts + 4000, ts + 150000, 200, 4300])
            k += 1
            ts += 40 * MS
    rows.sort(key=lambda r: r[4])
    probe = {"meta": {"meta": {"map": synth_summary()["map"]}}, "rows": rows, "end": {"gaps": [], "events": []}}
    main = [(x[0], x[1]) for x in series[500]]
    bursts = statsrow.find_bursts(main, 0.2, 0.1)
    threads = {501 + i: {"comm": "wrk:worker_%d" % i, "cpus": str(i)} for i in range(4)}
    threads[500] = {"comm": "main", "cpus": "4"}
    pairs = [{"monotonic_ns": int(t0 * 1e9), "time_ns": 10 ** 18 + int(t0 * 1e9)},
             {"monotonic_ns": int(t1 * 1e9), "time_ns": 10 ** 18 + int(t1 * 1e9)}]
    return {"probe": probe, "summary": synth_summary(), "series": series, "threads": threads, "bursts": bursts,
            "t0": t0, "t1": t1, "pairs": pairs, "missing": 0}


def record(x, cfg=None):
    return latency.leg_record(x["probe"], x["summary"], x["series"], x["threads"], 500, x["bursts"], x["t0"], x["t1"],
                              x["pairs"], x["missing"], cfg or CFG)


def leg_of(x, cfg=None, **over):
    """A leg record as the harness builds it around m["lat"], every other gated field in order."""
    m = {"shape": "own", "arm": "nosink", "lat": record(x, cfg), "lat_senders_running": True,
         "client_rate_2xx": 4400.4, "lat_nh": {"open_loop": True, "sent_ratio": 1.0001},
         "quiesce": {"before_ok": True, "after_ok": True}, "uptime": {"error_s": 0.4},
         "lat_count": {"error": 0},
         "dropped_stat_flushes_delta": 0}
    m.update(over)
    return m


EV = MK.ev_lat(60, 4400)


def failed(m, items=None):
    return {r["label"] for r in evidence.evaluate(m, items or EV)["items"] if not r["ok"]}


class ClassificationTest(unittest.TestCase):
    """In flush and out of flush, by the intended time (guard 20 ms)."""

    P = latency.params()
    SPAN = (0.5, 59.5)
    W = [(5.0 + 10 * i, 5.3 + 10 * i) for i in range(6)]

    def cls(self, t, whole=None, allw=None):
        return latency.classify(t, self.W if whole is None else whole, self.W if allw is None else allw, self.SPAN,
                                self.P)

    def test_slices(self):
        for t, want in ((4.97, {"out"}), (4.98, {"onset"}), (5.0, {"onset"}), (5.019, {"onset"}),
                        (5.02, {"in", "onset"}), (5.05, {"in", "onset"}), (5.06, {"in"}), (5.28, {"in"}),
                        (5.281, {"post"}), (5.3, {"post"}), (5.55, {"post"}), (5.551, {"out"}), (30.0, {"out"}),
                        (0.49, set()), (59.51, set()), (0.5, {"out"}), (59.5, {"out"})):
            self.assertEqual(self.cls(t), want, t)

    def test_a_partial_burst_is_no_slice(self):
        # a flush that crosses the edge of the used span: not IN (not whole), and not OUT either
        allw = self.W + [(59.3, 59.9)]
        self.assertEqual(self.cls(59.4, allw=allw), set())
        self.assertEqual(self.cls(59.27, allw=allw), {"out"})
        self.assertEqual(self.cls(59.29, allw=allw), set())   # inside the guard before its start

    def test_a_flush_shorter_than_two_guards_has_no_in(self):
        w = [(5.0, 5.03)]
        self.assertEqual(self.cls(5.005, w, w), {"onset"})
        self.assertEqual(self.cls(5.02, w, w), {"onset", "post"})
        self.assertFalse(any("in" in self.cls(5.0 + k / 1000.0, w, w) for k in range(-30, 300)))

    def test_ranges_agree_with_the_point_rule(self):
        rnd = random.Random(3)
        ts = sorted(rnd.uniform(0, 60) for _ in range(4000))
        r = latency.slice_ranges(ts, self.W, self.W, self.SPAN, self.P)
        for name in ("in", "onset", "post", "out"):
            got = {i for i0, i1 in r[name] for i in range(i0, i1)}
            want = {i for i, t in enumerate(ts) if name in self.cls(t)}
            self.assertEqual(got, want, name)

    def test_whole_bursts_and_the_synthetic_series(self):
        x = synth()
        span = latency.used_span(x["t0"], x["t1"], self.P)
        whole = latency.whole_bursts(x["bursts"], span)
        self.assertEqual(len(whole), 6)
        for (s, e), k in zip(whole, range(6)):
            self.assertAlmostEqual(s, 1004.0 + 10 * k, delta=0.011)
            self.assertAlmostEqual(e - s, 0.3, delta=0.011)
        # a flush in progress at the end of the window is not whole
        x = synth(first=9.9)
        self.assertEqual(len(latency.whole_bursts(x["bursts"], latency.used_span(x["t0"], x["t1"], self.P))), 5)

    def test_probes_in_a_loop_gap_are_dropped_and_counted(self):
        x = synth()
        gap = [int(1010.0 * 1e9), int(1010.004 * 1e9)]
        pts, cnt = latency.data_points(x["probe"]["rows"], 1000.5, 1059.5, [gap])
        self.assertGreater(cnt["dropped_for_gap"], 0)
        self.assertFalse(any(1010.0 < p[0] <= 1010.004 for p in pts))
        self.assertEqual(len(pts) + cnt["dropped_for_gap"], cnt["total"])

    def test_statistics(self):
        s = latency.stats_of([100.0] * 98 + [3000.0, 150000.0])
        self.assertEqual((s["n"], s["p50"], s["p99"], s["max"]), (100, 100.0, 3000.0, 150000.0))
        self.assertEqual((s["share_over_2ms"], s["over_20ms"], s["over_100ms"]), (0.02, 1, 1))
        self.assertEqual(latency.stats_of([]), {"n": 0})


class ShamTest(unittest.TestCase):
    """The A/A reference: the leg's windows shifted; never on a real flush."""

    P = latency.params()

    def zones(self, w):
        return [(s - self.P["guard_s"], e + self.P["post_s"]) for s, e in w]

    def test_shifts_never_touch_a_real_flush_or_its_post_zone(self):
        for flush_s in (0.27, 2.4, 4.0):
            x = synth(flush_s=flush_s)
            span = latency.used_span(x["t0"], x["t1"], self.P)
            whole, allw = latency.whole_bursts(x["bursts"], span), latency.all_windows(x["bursts"])
            shifts = latency.sham_shifts(whole, allw, span, self.P)
            self.assertGreaterEqual(len(shifts), 2, flush_s)
            for s, sh in shifts:
                self.assertAlmostEqual(s / 0.5, round(s / 0.5))
                self.assertGreaterEqual(len(sh), len(whole) - 1)
                for (a, b) in self.zones(sh):
                    self.assertTrue(a >= span[0] and b <= span[1])
                    for (ra, rb) in self.zones(allw):
                        self.assertTrue(b < ra or a > rb, (flush_s, s))

    def test_no_admissible_shift_when_the_flush_fills_the_interval(self):
        x = synth(flush_s=7.0)
        span = latency.used_span(x["t0"], x["t1"], self.P)
        whole, allw = latency.whole_bursts(x["bursts"], span), latency.all_windows(x["bursts"])
        self.assertEqual(latency.sham_shifts(whole, allw, span, self.P), [])

    def analyse(self, x):
        _, groups = latency.map_record(x["summary"], 4, 4, 0)
        span = latency.used_span(x["t0"], x["t1"], self.P)
        pts, _ = latency.data_points(x["probe"]["rows"], span[0], span[1], [])
        return latency.analyse_leg(pts, groups, x["bursts"], x["t0"], x["t1"], CFG)

    def test_a_real_effect_shows_in_the_contrast_and_not_in_the_sham(self):
        a = self.analyse(synth(in_us=300.0, cpu0_in_us=600.0, onset_us=500.0))
        c = a["contrasts"]
        # L1: IN - OUT on all connections (a quarter of them carry the extra 600 us: p99 has it)
        self.assertGreater(c["L1_p50"], 250.0)
        self.assertGreater(c["L1_p99"], 800.0)
        self.assertGreater(c["L2_p99"], c["L1_p99"])          # the onset adds its own
        self.assertAlmostEqual(c["L3_p50"], 600.0, delta=30.0)   # the shared-CPU worker against the others
        self.assertGreaterEqual(len(a["sham"]), 2)
        for s, sc in a["sham"].items():
            for k in ("L1_p99", "L2_p99", "L3_p99", "L1_p50", "L3_p50"):
                self.assertLess(abs(sc[k]), 30.0, (s, k))

    def test_no_effect_gives_contrasts_inside_the_noise(self):
        a = self.analyse(synth())
        for k in ("L1_p99", "L2_p99", "L3_p99", "L1_p50"):
            self.assertLess(abs(a["contrasts"][k]), 30.0, k)
        self.assertEqual(a["contrasts"]["L1_share_over_2ms"], 0.0)

    def test_reach_needs_two_shifts_common_to_every_round(self):
        self.assertEqual(TAB.reach_of([{"1.0": 5.0, "2.0": -40.0}, {"1.0": -9.0, "2.0": -20.0, "3.0": 99.0}]), (30.0, 2))
        self.assertEqual(TAB.reach_of([{"1.0": 5.0}, {"1.0": 9.0}]), (None, 1))
        self.assertEqual(TAB.reach_of([{"1.0": 5.0, "2.0": None}, {"1.0": 9.0, "2.0": 1.0}]), (None, 1))


class GateTest(unittest.TestCase):
    """Every gate of plan section 5 on a clean synthetic leg, then with its own failing case."""

    @classmethod
    def setUpClass(cls):
        cls.x = synth()
        cls.m = leg_of(cls.x)

    def bad(self, label_part, m=None, items=None, **synth_kw):
        m = m if m is not None else leg_of(synth(**synth_kw))
        f = failed(m, items)
        self.assertTrue(any(label_part in x for x in f), (label_part, sorted(f)))
        return f

    def test_clean_leg_passes_every_gate(self):
        self.assertEqual(failed(self.m), set())
        self.assertEqual(self.m["lat"]["probe"]["data_in_window"], 48000)
        self.assertEqual(self.m["lat"]["flush"]["whole"], 6)

    def test_missing_record_fails_every_lat_gate(self):
        m = dict(self.m)
        m.pop("lat")
        f = failed(m)
        self.assertGreaterEqual(len(f), 20)

    def mutate(self, fn):
        x = copy.deepcopy(self.x)
        fn(x)
        return leg_of(x)

    def test_probe_count_against_rate_times_window(self):
        def drop(x):
            # one connection silent for half a second: 25 requests short of 800 x window
            x["probe"]["rows"] = [r for r in x["probe"]["rows"]
                                  if not (r[0] == "d" and r[1] == 3 and 1020.0 <= r[3] / 1e9 < 1020.5)]
        self.assertEqual(self.bad("rate x window", self.mutate(drop)),
                         {"probe data requests with an intended time in the window = rate x window, +/-16"})

    def test_unanswered_error_status(self):
        def unanswered(x):
            r = [r for r in x["probe"]["rows"] if r[0] == "d"][500]
            r[5] = r[6] = None
        self.bad("every probe data request answered", self.mutate(unanswered))

        def err(x):
            x["probe"]["end"]["events"].append({"stream": "d", "conn": 2, "what": "closed by peer", "t_ns": 1})
        self.bad("no error or close", self.mutate(err))

        def status(x):
            [r for r in x["probe"]["rows"] if r[0] == "d"][7][6] = 503
        self.bad("field:lat.probe.data_non200", self.mutate(status))

        def undrained(x):
            x["summary"]["run"]["drained"] = False
        self.bad("everything due before it stopped", self.mutate(undrained))

        def unfinished(x):
            x["probe"]["end"] = None
        f = self.bad("the probe wrote its whole log", self.mutate(unfinished))
        self.assertTrue(any("loop gaps" in s for s in f))   # no gap list: those gates fail too, closed

    def test_probe_headroom(self):
        def late(x):
            for r in x["probe"]["rows"]:
                if r[0] == "d" and r[1] == 0:
                    r[4] = r[3] + 1500000    # every request of one connection goes out 1.5 ms late
        f = self.bad("lateness p99", self.mutate(late))
        self.assertTrue(any("over 1 ms" in s for s in f))

        def gaps(x):
            x["probe"]["end"]["gaps"] = [[int((1010 + i) * 1e9), int((1010 + i) * 1e9) + 2 * MS] for i in range(6)]
        self.bad("loop gaps over 1 ms at most 5", self.mutate(gaps))

        def long_gap(x):
            x["probe"]["end"]["gaps"] = [[int(1010 * 1e9), int(1010.2 * 1e9)]]   # 160 of 48,000 probes
        self.assertEqual(self.bad("dropped for a loop gap", self.mutate(long_gap)),
                         {"probes dropped for a loop gap at most 0.1%"})

    def test_lateness_is_against_the_free_connection(self):
        def backlog(x):
            # a stalled request, then the next ones sent the moment the connection frees: not late
            mine = [r for r in x["probe"]["rows"] if r[0] == "d" and r[1] == 5 and r[3] / 1e9 >= 1030.0][:10]
            done = mine[0][3] + 150 * MS
            mine[0][5] = done
            for r in mine[1:]:
                r[4], r[5] = done + 10000, done + 400000
                done = r[5]
        m = self.mutate(backlog)
        self.assertEqual(failed(m), set())

    def test_connection_map(self):
        def uneven(x):
            x["summary"]["map"]["per_worker"]["501"] = 5
            x["summary"]["map"]["per_worker"]["502"] = 3
        f = self.bad("exactly 4 probe connections per worker", self.mutate(uneven))
        self.assertIn("field:lat.map.per_worker_max", f)

        def margin(x):
            x["summary"]["map"]["min_margin"] = 3.2
        self.bad("clear by a factor of 5", self.mutate(margin))

        def changed(x):
            x["summary"]["map_end"]["unchanged"] = False
        self.bad("same connections on the same workers", self.mutate(changed))

        def failed_map(x):
            x["summary"]["map"] = {"error": "no 4 connections per worker after 64 opens", "workers_found": 4}
        f = self.bad("the probe mapped its connections", self.mutate(failed_map))
        self.assertIn("field:lat.map.connections", f)

        def not_pinned(x):
            for c in x["summary"]["map"]["connections"]:
                c["cpus"] = "0-3"
        self.bad("allowed on one CPU", self.mutate(not_pinned))

    def test_flush_count(self):
        # a 20 s interval: 3 whole flushes where 5 or 6 are due
        self.bad("whole flushes in the used span", interval=20.0)
        # 15 s apart: four whole flushes
        self.bad("whole flushes in the used span", interval=15.0)
        m = leg_of(synth(first=9.9))     # five whole, one in progress at the end: still valid
        self.assertEqual(m["lat"]["flush"]["whole"], 5)
        self.assertEqual(failed(m), set())

    def test_flush_grid(self):
        self.bad("flush starts one interval apart", interval=10.3)
        # a burst off the grid inside the window (an admin read mistaken for a flush)
        f = self.bad("flush starts one interval apart", extra_burst=(1027.0, 1027.4))
        self.assertTrue(any("whole flushes" in s for s in f))
        # one flush 150 ms late
        x = synth()
        b = x["bursts"][2]
        b["start_t"] += 0.15
        self.bad("flush starts one interval apart", leg_of(x))

    def test_clock_alignment(self):
        def skew(x):
            x["summary"]["clock_start"]["time_ns"] += 3 * MS
        self.assertEqual(self.bad("clock pairs agree", self.mutate(skew)),
                         {"harness and probe clock pairs agree within 1 ms"})

        def one_pair(x):
            x["summary"]["clock_end"] = None
        self.bad("clock pairs agree", self.mutate(one_pair))

        def stray(x):
            n = 0
            for r in x["probe"]["rows"]:
                if r[0] == "a" and 1030.0 <= r[3] / 1e9 < 1032.0 and n < 2:
                    r[5] = r[3] + 80 * MS    # two slow admin answers far from any flush
                    n += 1
        self.bad("at most 1 exception", self.mutate(stray))
        # the admin stream never slow: the two flush signals disagree (or the edges are off)
        self.bad("every whole flush burst holds a slow admin probe", admin_wait=False)

        def shifted(x):
            for b in x["bursts"]:
                b["start_t"] += 3.0
                b["end_t"] += 3.0
        f = self.bad("at most 1 exception", self.mutate(shifted))
        self.assertTrue(any("holds a slow admin probe" in s for s in f))

    def test_one_slow_admin_probe_outside_is_allowed(self):
        def stray(x):
            for r in x["probe"]["rows"]:
                if r[0] == "a" and r[3] / 1e9 >= 1030.0:
                    r[5] = r[3] + 80 * MS
                    break
        self.assertEqual(failed(self.mutate(stray)), set())

    def test_sampler(self):
        def missing(x):
            x["missing"] = 2
        self.bad("field:lat.sampler.missing", self.mutate(missing))

        def thin(x):
            for t in x["series"]:
                x["series"][t] = x["series"][t][::2]
        f = self.bad("95% of the expected samples", self.mutate(thin))

        def gap(x):
            s = x["series"][503]
            x["series"][503] = s[:3000] + s[3008:]    # one thread not read for 40 ms
        self.assertEqual(self.bad("largest sample gap", self.mutate(gap)), {"largest sample gap at most 25 ms"})

        def lost(x):
            x["series"].pop(504)
        self.bad("field:lat.sampler.threads", self.mutate(lost))

    def test_senders_rate_and_open_loop(self):
        self.bad("still sending", leg_of(self.x, lat_senders_running=False))
        self.bad("Nighthawk 2xx rate", leg_of(self.x, client_rate_2xx=4370.0))
        self.bad("--open-loop", leg_of(self.x, lat_nh={"open_loop": False, "sent_ratio": 1.0}))
        self.bad("rate x duration", leg_of(self.x, lat_nh={"open_loop": True, "sent_ratio": 0.99}))
        self.bad("quiescent point after", leg_of(self.x, quiesce={"before_ok": True, "after_ok": False}))

    def test_listener_target_is_client_plus_probe_and_stall_outcomes_are_not_gates(self):
        cfg = MK.lat_configs(box(), None)["lat.json"]
        base = {"idle_ok": True, "preflight_ok": True, "pinning_ok": True, "target_rps": 5200, "perf_ok": True,
                "responses": 300000, "client_headroom": 0.6, "sut_foreign_cpus": 0.0, "sut_sibling_cpus": 0.0,
                "client_overflow": {"benchmark.pool_overflow": 12}, "client_pending_total": 900, "client_workers": 16,
                "envoy_exit": 0}
        self.assertTrue(validity.verdict(dict(base, sut_rate_2xx=5199.0), cfg["validity"])["valid"])
        # the same leg under the default gates: the client's queue and overflow would have made it invalid
        self.assertFalse(validity.verdict(dict(base, sut_rate_2xx=5199.0))["valid"])
        # pins before and after the window stay gated
        v = validity.verdict(dict(base, sut_rate_2xx=5199.0, rung_pin_after={"ok": False}), cfg["validity"])
        self.assertTrue(any("left their cores" in r for r in v["reasons"]))
        # the listener's requests are gated by count (CountGateTest), on every leg of every arm
        for a in cfg["arms"]:
            self.assertIn("lat_count.error", [i["stat"] for i in a["evidence"]])

    # ---- the sinks

    def statsd_leg(self, marks=None, **over):
        used = 310098
        if marks is None:
            marks = [[int((990 + 10 * i) * 1e9), 100.0 + 10 * i, 200000 * i, 110110 * i, 0, 310110 * i] for i in range(9)]
        sd = latency.statsd_flushes(marks, used, int(985 * 1e9), int(1075 * 1e9))
        sd.update(marks_window_error=0, ms_per_request=3.06, ms_error_share=0.003)
        m = leg_of(self.x, arm="statsd", udp_leg={"rcvbuf_errors": 0, "socket_drops": 0},
                   udpsink={"drain_quiet": True, "classes": {"other": 0}})
        m["lat"] = dict(m["lat"], statsd=sd)
        for k, v in over.items():
            cur = m
            parts = k.split("__")
            for p in parts[:-1]:
                cur = cur[p]
            cur[parts[-1]] = v
        return m

    def test_statsd_delivery(self):
        ev = MK.EV_LAT_STATSD
        self.assertEqual(failed(self.statsd_leg(), ev), set())
        self.assertEqual(self.statsd_leg()["lat"]["statsd"]["flushes"], 8)
        self.bad("RcvbufErrors", self.statsd_leg(udp_leg__rcvbuf_errors=3), ev)
        self.bad("socket dropped nothing", self.statsd_leg(udp_leg__socket_drops=None), ev)
        self.bad("read its queue empty", self.statsd_leg(udpsink__drain_quiet=False), ev)
        self.bad("counter, gauge or timer", self.statsd_leg(udpsink__classes={"other": 4}), ev)
        self.bad("the leg's own counters say", self.statsd_leg(lat__statsd__ms_error_share=0.03), ev)
        self.bad("uptime lines in the window", self.statsd_leg(lat__statsd__marks_window_error=2), ev)
        # one flush 1% short at the receiver: against the admin count, and against the other flushes
        marks = [[int((990 + 10 * i) * 1e9), 0.0, 200000 * i, 110110 * i, 0, 0] for i in range(9)]
        for mk in marks[5:]:
            mk[2] -= 3101
        f = self.bad("within 0.5% of the admin count", self.statsd_leg(marks=marks), ev)
        self.assertTrue(any("equal within 0.1%" in s for s in f))
        # every flush 0.3% short alike: inside 0.5% of the admin count, and equal
        marks = [[int((990 + 10 * i) * 1e9), 0.0, 200000 * i, 109180 * i, 0, 0] for i in range(9)]
        self.assertEqual(failed(self.statsd_leg(marks=marks), ev), set())
        # every flush 0.6% short alike: equal, but not the admin count
        marks = [[int((990 + 10 * i) * 1e9), 0.0, 200000 * i, 108250 * i, 0, 0] for i in range(9)]
        self.assertEqual(self.bad("within 0.5% of the admin count", self.statsd_leg(marks=marks), ev),
                         {"counter and gauge lines of every flush within 0.5% of the admin count of used ones"})
        # the receiver recorded too few flushes (it fell behind or stopped)
        self.bad("at least 5 whole flushes", self.statsd_leg(marks=marks[:4]), ev)
        # only the marks between the two quiescent points count
        sd = latency.statsd_flushes(marks, 310098, int(1005 * 1e9), int(1045 * 1e9))
        self.assertEqual((sd["marks"], sd["flushes"]), (4, 3))

    def otlp_leg(self, points=4 * 360147, rq=4 * 37, reset=0, settled=True, limit=64, refused=0):
        used = 360147
        n0 = {"cluster.otel_collector.upstream_rq_total": 100, "cluster.otel_collector.http2.rx_reset": 0}
        n1 = {"cluster.otel_collector.upstream_rq_total": 100 + rq, "cluster.otel_collector.http2.rx_reset": reset}
        oc = statsrow.otlp_cluster(n0, n1, used, 10000, 85.0, 10.0)
        fit = statsrow.flush_fit(points, used, int(round(oc["flushes"])))
        cd = {"accepted_metric_points": points, "refused_metric_points": refused, "fit": fit, "settled": settled}
        if fit.get("n"):
            cd["accepted_metric_points_per_flush"] = points / fit["n"]
        return leg_of(self.x, arm="otlp", used_total=used, otlp_cluster=oc, collector_delta=cd,
                      collector_cfg={"max_recv_msg_size_mib": limit})

    def test_otlp_delivery(self):
        ev = MK.EV_LAT_OTLP
        self.assertEqual(failed(self.otlp_leg(rq=8 * 37, points=8 * 360147), ev), set())
        # one flush in flight at a collector read: allowed (n within one)
        self.assertEqual(failed(self.otlp_leg(rq=8 * 37, points=9 * 360147), ev), set())
        # the recorded loss of run S: 5 of 37 requests of every flush refused below the receiver
        f = self.bad("metric points per whole flush", self.otlp_leg(rq=8 * 37, points=8 * 310146, reset=40), ev)
        self.assertIn("field:otlp_cluster.rx_reset", f)
        self.bad("exactly whole flushes", self.otlp_leg(rq=8 * 37 - 1, points=8 * 360147), ev)
        self.bad("as the span and the interval say", self.otlp_leg(rq=4 * 37, points=4 * 360147), ev)
        self.bad("within one of Envoy's request count", self.otlp_leg(rq=8 * 37, points=6 * 360147), ev)
        self.bad("residual under 1%", self.otlp_leg(rq=8 * 37, points=8 * 360147 - 10000), ev)
        self.bad("settled at both", self.otlp_leg(rq=8 * 37, points=8 * 360147, settled=False), ev)
        self.bad("64 MiB receive limit", self.otlp_leg(rq=8 * 37, points=8 * 360147, limit=None), ev)
        self.bad("field:collector_delta.refused_metric_points",
                 self.otlp_leg(rq=8 * 37, points=8 * 360147, refused=7), ev)

    def test_nosink(self):
        ev = MK.EV_LAT_NOSINK
        m = leg_of(self.x, udp_leg={"delivered": 12, "no_ports": 0}, sut_stats_leg_end={"a": 1},
                   sut_stats_leg_end_ok=True)
        dump = {"configs": [{"bootstrap": {"stats_flush_interval": "10s"}}]}

        def f(m, dump):
            return {r["label"] for r in evidence.evaluate(m, ev, dump)["items"] if not r["ok"]}
        self.assertEqual(f(m, dump), set())
        self.assertIn("no stats sink configured", f(m, {"bootstrap": {"stats_sinks": [{"name": "envoy.stat_sinks.statsd"}]}}))
        self.assertIn("no collector cluster",
                      f(dict(m, sut_stats_leg_end={"cluster.otel_collector.upstream_rq_total": 0}), dump))
        self.assertTrue(any("UDP counters flat" in s for s in f(dict(m, udp_leg={"delivered": 310000, "no_ports": 0}),
                                                               dump)))
        self.assertTrue(any("closed port" in s for s in f(dict(m, udp_leg={"delivered": 0, "no_ports": 310000}),
                                                         dump)))

    def test_manipulation_check(self):
        m = leg_of(synth(wait_cpu0_in=0.5))
        mp = m["lat"]["manipulation"]
        self.assertGreater(mp["in_over_out"], 1000)
        self.assertGreater(mp["in_over_others"], 1000)
        self.assertAlmostEqual(mp["cpu0_wait_in"], 500.0, delta=20.0)
        # own core: the worker on CPU 0 waits no more in a flush than out of it
        self.assertAlmostEqual(self.m["lat"]["manipulation"]["in_over_out"], 1.0, delta=0.2)
        self.assertAlmostEqual(self.m["lat"]["worker_busy_mean"], 0.3, delta=0.01)


class CellsTest(unittest.TestCase):
    def exp(self, fn="lat.json", **over):
        e = experiment.load(os.path.join(GEN, fn), over or None)
        self.assertEqual(experiment.validate(e, allow_short=True), [])
        return e

    def test_five_cells(self):
        e = self.exp()
        self.assertEqual([(s["name"], a["name"]) for s, a in experiment.cells(e)],
                         [("own", "nosink"), ("own", "statsd"), ("own", "otlp"), ("shared", "nosink"),
                          ("shared", "statsd")])
        self.assertEqual(len(experiment.schedule(e)), 25)
        self.assertEqual((e["rounds"], e["order_seed"], experiment.order_period(e)), (5, 31, 5))

    def test_latin_square_over_the_cells(self):
        e = self.exp()
        plan = experiment.schedule(e)
        pos = {}
        for r in range(1, 6):
            legs = [(s["name"], a["name"]) for rr, s, a in plan if rr == r]
            self.assertEqual(len(set(legs)), 5)
            for i, c in enumerate(legs):
                pos.setdefault(c, []).append(i)
        for c, p in pos.items():
            self.assertEqual(sorted(p), [0, 1, 2, 3, 4], c)

    def test_other_configs_are_not_cells(self):
        e = experiment.load(os.path.join(X86, "sw.json"))
        self.assertFalse(experiment.cell_mode(e))
        self.assertEqual(len(experiment.cells(e)), len(e["shapes"]) * len(e["arms"]))

    def test_cells_need_latin_and_known_shapes(self):
        e = self.exp()
        e["order"] = "rotate"
        self.assertTrue(any("need order latin" in x for x in experiment.validate(e, allow_short=True)))
        e = self.exp()
        e["arms"][2]["shapes"] = ["nowhere"]
        self.assertTrue(any("non-empty list of shape names" in x for x in experiment.validate(e, allow_short=True)))
        e = self.exp()
        e["rounds"] = e["rounds_block"] = e["rounds_max"] = 4
        self.assertTrue(any("multiple of 5" in x for x in experiment.validate(e, allow_short=True)))

    def run_sim(self, faults, rounds=5):
        d = tempfile.mkdtemp()
        e = self.exp(sim_faults=faults, rounds=rounds, rounds_block=rounds, rounds_max=rounds)
        r = experiment.Runner(e, d, SimBackend, allow_short=True, log_stream=io.StringIO())
        try:
            return r.run(simulate=True), d
        except RuntimeError as ex:
            return ex, d

    def test_an_invalid_leg_reruns_its_whole_round(self):
        res, d = self.run_sim({"r02-own-otlp": "headroom"})
        try:
            legs = res["legs"]
            self.assertEqual(len(legs), 30)
            sup = [m for m in legs if m.get("superseded")]
            self.assertEqual(sorted(m["leg_id"] for m in sup), sorted(
                "r02-%s-%s" % c for c in (("own", "nosink"), ("own", "statsd"), ("own", "otlp"), ("shared", "nosink"),
                                         ("shared", "statsd"))))
            rr = [m["leg_id"] for m in legs if m.get("attempt") == 1]
            # the round's own order again
            self.assertEqual(rr, [experiment.leg_id(2, s, a, 1) for s, a in experiment.cell_order(res["experiment"], 2)])
            self.assertEqual(res["metadata"]["rounds_complete"], 5)
            self.assertEqual(len(evidence.load_legs(d)), 25)
        finally:
            shutil.rmtree(d)

    def test_three_invalid_rounds_in_a_row_abort(self):
        res, d = self.run_sim({"r01-own-otlp": "headroom", "r02-own-nosink": "headroom", "r03-shared-statsd": "non2xx"})
        shutil.rmtree(d)
        self.assertIsInstance(res, RuntimeError)
        self.assertIn("3 rounds in a row", str(res))
        # two in a row, then a clean one: no abort
        res, d = self.run_sim({"r01-own-otlp": "headroom", "r02-own-nosink": "headroom"})
        shutil.rmtree(d)
        self.assertNotIsInstance(res, RuntimeError)
        self.assertEqual(len(res["legs"]), 35)

    def test_complete_rounds_counts_cells(self):
        e = self.exp()
        legs = [{"round": r, "shape": s["name"], "arm": a["name"], "verdict": {"valid": True}}
                for r, s, a in experiment.schedule(e)]
        self.assertEqual(experiment.complete_rounds(e, legs), 5)
        self.assertEqual(experiment.complete_rounds(e, legs[:-1]), 0)


class ConfigTest(unittest.TestCase):
    def raw(self, fn):
        with open(os.path.join(GEN, fn)) as f:
            return json.load(f)

    def test_written_files_are_the_generator_output_or_a_calibrated_rewrite(self):
        # in the repository the committed files are the uncalibrated output (test_statsflush checks
        # every config byte for byte); here only that both files exist beside make.py
        for fn in ("lat.json", "smoke-lat.json"):
            self.assertTrue(os.path.exists(os.path.join(X86, fn)), fn)

    def test_smoke_differs_only_in_name_rounds_and_the_smoke_flag(self):
        q, s = self.raw("lat.json"), self.raw("smoke-lat.json")
        diff = {k for k in set(q) | set(s) if q.get(k) != s.get(k)}
        self.assertEqual(diff, {"name", "rounds", "rounds_block", "rounds_max", "smoke"})
        self.assertEqual((s["rounds"], q["rounds"], s["smoke"]), (1, 5, True))
        # the smoke runs in gate mode, with the queue's own window
        self.assertNotIn("evidence_mode", s)
        self.assertEqual(s["measure"]["window_s"], 60)

    def test_every_queue_cell_has_a_smoke_leg(self):
        q = experiment.load(os.path.join(GEN, "lat.json"))
        s = experiment.load(os.path.join(GEN, "smoke-lat.json"))
        qc = {(sh["name"], a["name"]) for sh, a in experiment.cells(q)}
        sc = {(sh["name"], a["name"]) for _, sh, a in experiment.schedule(s)}
        self.assertEqual(qc - sc, set())
        self.assertEqual({a["name"] for a in q["arms"]} - {a["name"] for a in s["arms"]}, set())
        # and with a cut applied (own/otlp dropped, shared/statsd replaced): still the same cells in both
        for knobs in ({"cells": {"nosink": ["own", "shared"], "statsd": ["own", "shared"], "otlp": []}},
                      {"cells": {"nosink": ["own", "shared"], "statsd": ["own"], "otlp": ["own", "shared"]}},
                      {"window_s": 50, "nh_rps": 4800}):
            c = MK.lat_configs(box(), None, knobs)
            cells = [[(sh, a["name"]) for a in c[fn]["arms"] for sh in a["shapes"]] for fn in ("lat.json", "smoke-lat.json")]
            self.assertEqual(cells[0], cells[1])

    def test_no_evidence_item_takes_its_expectation_from_a_smoke(self):
        for fn in ("lat.json", "smoke-lat.json"):
            for a in self.raw(fn)["arms"]:
                self.assertGreater(len(a["evidence"]), 30)
                for it in a["evidence"]:
                    self.assertNotIn("ref", it, (fn, a["name"], it["stat"]))
        # with a calibration the counts come from it, still no ref
        cal = {"1m": {"stats_total": 1180396, "used_total": 360107, "settle_s": 5.0, "ready_timeout_s": 60,
                      "admin_timeout_s": 42}}
        c = MK.lat_configs(box(), cal)["lat.json"]
        self.assertNotIn("uncalibrated", c)
        for a in c["arms"]:
            self.assertFalse(any("ref" in it for it in a["evidence"]))
            self.assertIn("stats_total", [it["stat"] for it in a["evidence"]])
        self.assertEqual(c["client"]["duration_s"], 2 + 5 + 60 + 5)
        self.assertEqual(c["shapes"][0]["pre_window_settle_s"], 5.0)

    def test_design(self):
        q = experiment.load(os.path.join(GEN, "lat.json"))
        self.assertTrue(q.get("uncalibrated"))
        self.assertEqual(q["cpus"], {"sut": "0-4", "client": "20-29,60-69", "origin": "32-39,72-79", "sampler": "30",
                                     "probe": "31", "reserved": "70-71"})
        for a in q["arms"]:
            st = a["settings"]
            self.assertEqual(st["stats_flush"], {"interval_s": 10})
            self.assertEqual(st["stats_clusters"]["count"], 10000)
        self.assertEqual({a["name"]: (a["settings"].get("stats_sink") or {}).get("kind") for a in q["arms"]},
                         {"nosink": None, "statsd": "statsd", "otlp": "otlp"})
        for sh in q["shapes"]:
            self.assertEqual((sh["rps"], sh["workers"], sh["worker_cpus"], sh["worker_pin"], sh["path"]),
                             (4400, 4, "0-3", "one_to_one", "/s"))
        lt = q["measure"]["latency"]
        self.assertEqual(lt["data_conns"] * lt["data_hz"], 800)
        self.assertEqual((lt["sample_s"], lt["admin_period_ms"], lt["control_conns"], lt["control_hz"]),
                         (0.005, 50, 2, 25))
        self.assertIsNone(q["validity"]["rate_tolerance"])   # recorded; the count gate replaces it
        self.assertIsNone(q["validity"]["max_pending_total"])
        self.assertNotIn("stat_ops_probe", q["measure"])
        # the same binary and pins as run S
        s = experiment.load(os.path.join(X86, "sw.json"))
        self.assertEqual([a["binaries"] for a in q["arms"]], [s["arms"][0]["binaries"]] * 3)
        self.assertEqual(q["collector"], s["collector"])
        self.assertEqual(q["client"]["extra_args"], s["client"]["extra_args"])
        # the window cut changes the flush-count gate with it
        c = MK.lat_configs(box(), None, {"window_s": 50})["lat.json"]
        it = [i for i in c["arms"][0]["evidence"] if i["stat"] == "lat.flush.whole"][0]
        self.assertEqual((it["min"], it["max"]), (4, 5))

    def test_validation_of_the_latency_section(self):
        e = experiment.load(os.path.join(GEN, "lat.json"))
        e["cpus"].pop("probe")
        self.assertTrue(any("cpus.probe" in x for x in experiment.validate(e, allow_short=True)))
        e = experiment.load(os.path.join(GEN, "lat.json"))
        e["measure"]["latency"].pop("map_margin")
        self.assertTrue(any("map_margin" in x for x in experiment.validate(e, allow_short=True)))
        e = experiment.load(os.path.join(GEN, "lat.json"))
        e["shapes"][0].pop("worker_pin")
        self.assertTrue(any("one_to_one" in x for x in experiment.validate(e, allow_short=True)))

    def test_dry_run_of_the_smoke(self):
        d = tempfile.mkdtemp()
        try:
            r = subprocess.run([sys.executable, os.path.join(HERE, "bin", "epl"), "run",
                                os.path.join(GEN, "smoke-lat.json"), "--dry-run", "--allow-short",
                                "--allow-uncalibrated", "--out", d], capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
            self.assertEqual(len(evidence.load_legs(d)), 5)
            self.assertEqual(SESS.smoke_problems(os.path.join(GEN, "smoke-lat.json"), d), [])
        finally:
            shutil.rmtree(d)


class SinkTest(unittest.TestCase):
    def test_classes_marks_and_drain(self):
        d = tempfile.mkdtemp()
        out = os.path.join(d, "sink.json")
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        p = subprocess.Popen([sys.executable, os.path.join(HERE, "epl", "udpsink.py"), "--port", str(port),
                              "--rcvbuf", "1048576", "--out", out, "--drain-s", "5", "--classes"])
        try:
            end = time.time() + 10
            while not os.path.exists(out + ".ready") and time.time() < end:
                time.sleep(0.02)
            u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            def flush(up):
                for i in range(30):
                    u.sendto(b"envoy.cluster.c%d.upstream_rq_total:1|c" % i, ("127.0.0.1", port))
                u.sendto(b"envoy.server.uptime:%d|g" % up, ("127.0.0.1", port))
                for i in range(20):
                    u.sendto(b"envoy.cluster.c%d.membership_total:1|g" % i, ("127.0.0.1", port))
            flush(10)
            for i in range(7):
                u.sendto(b"envoy.http.ingress_http.downstream_rq_time:3|ms", ("127.0.0.1", port))
            flush(20)
            flush(30)
            u.sendto(b"envoy.x:1|c\n", ("127.0.0.1", port))   # a trailing newline is skipped
            time.sleep(0.2)
            p.send_signal(signal.SIGTERM)
            # sent after the stop signal: still read (the drain), where the old sink exited
            for i in range(5):
                u.sendto(b"envoy.late%d:1|c" % i, ("127.0.0.1", port))
            self.assertEqual(p.wait(timeout=15), 0)
            with open(out) as f:
                st = json.load(f)
        finally:
            if p.poll() is None:
                p.kill()
            shutil.rmtree(d)
        self.assertEqual(st["classes"], {"c": 96, "g": 63, "ms": 7, "h": 0, "other": 0})
        self.assertEqual(st["datagrams"], 166)
        self.assertTrue(st["drain_quiet"])
        self.assertTrue(1 <= st["drained_datagrams"] <= 5, st["drained_datagrams"])
        self.assertEqual([m[1] for m in st["marks"]], [10.0, 20.0, 30.0])
        self.assertEqual(len(st["uptime_samples"]), 3)
        sd = latency.statsd_flushes(st["marks"], 51, 0, 2 ** 62)
        # the lines between two uptime lines are one flush: 30 counters and 21 gauges
        self.assertEqual((sd["flushes"], sd["cg_per_flush_min"], sd["cg_per_flush_max"]), (2, 51, 51))
        self.assertEqual((sd["max_rel_error"], sd["spread"]), (0.0, 0.0))
        self.assertLess(st["marks"][0][0], st["marks"][2][0])
        self.assertLess(abs(st["marks"][2][0] - st["clock_end"]["monotonic_ns"]), 20 * 10 ** 9)


class SinkFlagTest(unittest.TestCase):
    """D1: without --classes (every run but L) the sink is the one of the earlier runs."""

    def test_without_the_flag_no_classing_and_no_drain(self):
        d = tempfile.mkdtemp()
        out = os.path.join(d, "sink.json")
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        p = subprocess.Popen([sys.executable, os.path.join(HERE, "epl", "udpsink.py"), "--port", str(port),
                              "--rcvbuf", "1048576", "--out", out])
        try:
            end = time.time() + 10
            while not os.path.exists(out + ".ready") and time.time() < end:
                time.sleep(0.02)
            u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            for i in range(10):
                u.sendto(b"envoy.a%d:1|c" % i, ("127.0.0.1", port))
            u.sendto(b"envoy.server.uptime:7|g", ("127.0.0.1", port))
            u.close()
            time.sleep(0.2)
            t = time.time()
            p.send_signal(signal.SIGTERM)
            self.assertEqual(p.wait(timeout=15), 0)
            took = time.time() - t
            with open(out) as f:
                st = json.load(f)
        finally:
            if p.poll() is None:
                p.kill()
            shutil.rmtree(d)
        # exactly the keys the sink wrote before run L, the uptime sample still taken
        self.assertEqual(sorted(st), ["bytes", "datagrams", "newlines", "port", "rcvbuf_granted", "rcvbuf_requested",
                                      "started", "stopped", "uptime_samples"])
        self.assertEqual((st["datagrams"], len(st["uptime_samples"])), (11, 1))
        self.assertLess(took, 5.0)

    def test_only_run_l_sets_the_flag(self):
        calls = []

        class Own:
            def start(self, args, **kw):
                calls.append(args)
                raise RuntimeError("stop here")
        for classes in (False, True):
            try:
                statsrow.start_udpsink(Own(), "32", 8125, 1024, os.path.join(tempfile.gettempdir(), "x.json"),
                                       classes=classes)
            except RuntimeError:
                pass
        self.assertNotIn("--classes", calls[0])
        self.assertIn("--classes", calls[1])
        with open(os.path.join(HERE, "epl", "leg.py")) as f:
            src = f.read()
        self.assertIn('classes=bool(self.exp["measure"].get("latency"))', src)
        self.assertEqual(src.count("start_udpsink("), 1)


class CountGateTest(unittest.TestCase):
    """B1: the listener's request count between the leg's two quiescent reads, with no time base."""

    K = "http.ingress_http.downstream_rq_2xx"

    def rows(self, n=60000, unanswered=0, non200=0):
        r = [["d", i % 16, i // 16, i, i, i + 1, 200, 4300] for i in range(n)]
        for x in r[:unanswered]:
            x[5] = x[6] = None
        for x in r[unanswered:unanswered + non200]:
            x[6] = 503
        return r + [["a", 0, 0, 1, 1, 2, 200, 9], ["c", 0, 0, 1, 1, 2, 200, 9]]

    def count(self, listener=330000 + 60000 + 1600, nh=330000, mapped=1600, **kw):
        # 36,000 requests (priming, warm-up) before the first read are in neither count
        return legmod.lat_count({self.K: 36000}, {self.K: 36000 + listener} if listener is not None else {},
                                nh, self.rows(**kw), mapped)

    def item(self):
        return [i for i in MK.ev_lat(60, 4400) if i["stat"] == "lat_count.error"]

    def ok(self, c):
        return evidence.evaluate({"shape": "own", "lat_count": c}, self.item())["ok"]

    def test_exact_sum_passes(self):
        c = self.count()
        self.assertEqual((c["listener_2xx"], c["expected"], c["error"]), (391600, 391600, 0))
        self.assertTrue(self.ok(c))

    def test_one_request_off_fails_either_way(self):
        for listener in (391599, 391601):
            c = self.count(listener=listener)
            self.assertEqual(abs(c["error"]), 1)
            self.assertFalse(self.ok(c))

    def test_the_probe_stream_missing_fails(self):
        # a listener that saw only the client's requests (what a rate gate with a loose base could pass)
        self.assertFalse(self.ok(self.count(listener=330000 + 1600)))
        # requests Envoy answered that the probe never saw answered, and non-200 answers
        self.assertFalse(self.ok(self.count(unanswered=3)))
        self.assertFalse(self.ok(self.count(non200=2)))

    def test_a_missing_part_fails_closed(self):
        for kw in (dict(nh=None), dict(mapped=None), dict(listener=None)):
            c = self.count(**kw)
            self.assertNotIn("error", c)
            self.assertFalse(self.ok(c))
        self.assertFalse(evidence.evaluate({"shape": "own"}, self.item())["ok"])

    def test_the_windowed_rate_is_recorded_not_gated(self):
        cfg = MK.lat_configs(box(), None)["lat.json"]
        self.assertIsNone(cfg["validity"]["rate_tolerance"])
        base = {"idle_ok": True, "preflight_ok": True, "pinning_ok": True, "target_rps": 5200, "perf_ok": True,
                "responses": 300000, "client_headroom": 0.6, "sut_foreign_cpus": 0.0, "sut_sibling_cpus": 0.0,
                "client_overflow": {}, "envoy_exit": 0}
        # a count read that waited 2.4 s behind a flush reads the rate 1.8% low: not a reason any more
        self.assertTrue(validity.verdict(dict(base, sut_rate_2xx=5200 * 0.982), cfg["validity"])["valid"])
        # with no rate at all the leg still fails, and other runs keep their tolerance
        self.assertFalse(validity.verdict(dict(base, sut_rate_2xx=None), cfg["validity"])["valid"])
        self.assertFalse(validity.verdict(dict(base, sut_rate_2xx=5200 * 0.982))["valid"])

    def test_client_duration_holds_two_reads_that_each_wait_for_a_flush(self):
        lat = MK.LAT_PROBE
        base = 72
        d_idle = 0.83
        for arm, flush in (("statsd", 7.0), ("otlp", 7.0), ("nosink", 2.0)):
            dur = legmod.lat_client_duration(base, lat, arm, d_idle)
            # lead-in, first read (wait + twice its idle time), settle, window, second read the same
            need = 2 + (flush + 2 * d_idle) + 5 + 0.3 + 60.1 + (flush + 2 * d_idle)
            self.assertGreaterEqual(dur, need, arm)
            self.assertLessEqual(dur, need + 6, arm)
        self.assertEqual(legmod.lat_client_duration(72, lat, "statsd", 0.83), 72 + 18)
        self.assertEqual(legmod.lat_client_duration(72, lat, "nosink", 0.83), 72 + 8)
        with open(os.path.join(HERE, "epl", "leg.py")) as f:
            src = f.read()
        # lat_senders_running stays a gate, computed after the second count read
        self.assertLess(src.index("t_q1_end = time.monotonic()"), src.index('m["lat_senders_running"] ='))
        self.assertIn("lat_senders_running", [i["stat"] for i in MK.ev_lat(60, 4400)])

    def test_map_requests_are_counted_by_the_probe(self):
        with open(os.path.join(HERE, "epl", "latprobe.py")) as f:
            src = f.read()
        self.assertIn("requests=sent[0]", src)


class TimerLinesTest(unittest.TestCase):
    """Q2: the timer-line expectation from the leg's own counters."""

    def numeric(self):
        n = {"http.ingress_http.downstream_rq_completed": 424000, "http.admin.downstream_rq_completed": 1700,
             "http.ingress_http.downstream_cx_destroy": 1300, "http.admin.downstream_cx_destroy": 1690,
             "cluster.origin.upstream_cx_total": 600, "cluster.origin.upstream_cx_destroy": 90,
             "cluster.origin.upstream_cx_destroy_local": 90}
        for i in range(100):
            n["cluster.gen%d.upstream_cx_total" % i] = 100
            n["cluster.gen%d.upstream_cx_destroy" % i] = 100
        return n

    def test_expectation(self):
        e = legmod.timer_lines_expected(self.numeric())
        self.assertEqual(e, {"requests": 1272000, "admin_requests": 1700, "downstream_closes": 5980,
                             "upstream_connects": 10600, "upstream_closes": 10090, "total": 1300370})
        # about 3.07 per request, as counted by hand for 10,000 clusters: inside no fixed bound by luck
        self.assertAlmostEqual(e["total"] / 424000.0, 3.067, delta=0.001)

    def test_missing_counter_gives_no_expectation(self):
        n = self.numeric()
        n.pop("http.admin.downstream_rq_completed")
        self.assertIsNone(legmod.timer_lines_expected(n))
        self.assertIsNone(legmod.timer_lines_expected({}))

    def test_gate(self):
        it = [i for i in MK.EV_LAT_STATSD if i["stat"] == "lat.statsd.ms_error_share"]
        self.assertEqual(len(it), 1)
        self.assertFalse(any(i["stat"] == "lat.statsd.ms_per_request" for i in MK.EV_LAT_STATSD))

        def ok(share):
            sd = {} if share is None else {"ms_error_share": share}
            return evidence.evaluate({"shape": "own", "lat": {"statsd": sd}}, it)["ok"]
        self.assertTrue(ok(0.004))
        self.assertFalse(ok(0.02))     # the receiver lost (or gained) 2% of the timer lines
        self.assertFalse(ok(None))     # no expectation: fails closed


# ---------------------------------------------------------------- the table and the session rules

def write_run(root, rounds=4, cpu0_in_us=0.0, in_us=0.0, interval=5.0, window=30.0, hz=20, flush_s=0.3, valid=True):
    """A run directory as a loaded run L leaves it, from synthetic legs (a short window and a
    low probe rate keep it small): legs.jsonl, probe/, main/, experiment.json."""
    cfg = MK.lat_configs(box(), None)["lat.json"]
    cfg["measure"]["latency"].update(data_hz=hz)
    cfg["lat"]["interval_s"] = interval
    os.makedirs(os.path.join(root, "probe"))
    os.makedirs(os.path.join(root, "main"))
    with open(os.path.join(root, "experiment.json"), "w") as f:
        json.dump(cfg, f)
    exp = dict(cfg, order="latin", order_seed=31)
    lines = []
    seed = 0
    for r in range(1, rounds + 1):
        for sh, a in experiment.cell_order(exp, r):
            seed += 1
            shared = sh["name"] == "shared"
            x = synth(window=window, interval=interval, first=2.0, hz=hz, seed=seed, flush_s=flush_s,
                      in_us=in_us, cpu0_in_us=cpu0_in_us if shared else 0.0, wait_cpu0_in=0.5 if shared else 0.0)
            lid = experiment.leg_id(r, sh, a)
            with gzip.open(os.path.join(root, "probe", lid + ".jsonl.gz"), "wt") as f:
                f.write(json.dumps(x["probe"]["meta"]) + "\n")
                for row in x["probe"]["rows"]:
                    f.write(json.dumps(row) + "\n")
                f.write(json.dumps({"end": x["probe"]["end"]}) + "\n")
            with gzip.open(os.path.join(root, "main", lid + ".json.gz"), "wt") as f:
                json.dump({"bursts": x["bursts"], "window_mono": [x["t0"], x["t1"]], "main_tid": 500,
                           "series": {str(t): v for t, v in x["series"].items()},
                           "threads": {str(t): v for t, v in x["threads"].items()}}, f)
            c = dict(cfg["measure"]["latency"], workers=4, interval_s=interval)
            m = {"leg_id": lid, "round": r, "shape": sh["name"], "arm": a["name"], "attempt": 0,
                 "verdict": {"valid": valid, "reasons": [] if valid else ["made invalid"]},
                 "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(1.8e9 + 130 * seed)),
                 "latency_us": {"p50": 400.0, "p99": 610.0}, "client_pending_total": 16, "client_overflow": {},
                 "watchdog_delta": {"server.worker_0.watchdog_miss": 1 if shared else 0},
                 "udp_leg": {"rcvbuf_errors": 0, "socket_drops": 0},
                 "otlp_cluster": {"rx_reset": 0}, "used_total": 360147,
                 "collector_delta": {"accepted_metric_points_per_flush": 360147.0},
                 "lat": dict(record(x, c), rx_queue={"max_share": 0.01})}
            lines.append(json.dumps(m))
    with open(os.path.join(root, "legs.jsonl"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return cfg


class TableTest(unittest.TestCase):
    def test_finding_on_the_shared_core_and_none_on_the_own_core(self):
        d = tempfile.mkdtemp()
        try:
            write_run(d, rounds=5, cpu0_in_us=900.0)
            res = TAB.build(d)
            rows = {(x["label"], x["metric"]): x for x in res["rows"]}
            self.assertTrue(res["complete"])
            self.assertEqual(res["rounds"], [1, 2, 3, 4, 5])
            self.assertEqual(res["holm_family"], 6)
            for arm in ("nosink", "statsd"):
                r = rows[("L3 shared/" + arm, "p99")]
                self.assertEqual(r["status"], "finding", r)
                self.assertAlmostEqual(r["mean"], 900.0, delta=60.0)
                self.assertEqual(r["n"], 5)
                self.assertGreaterEqual(r["sham_shifts"], 2)
                self.assertLess(r["reach"], 60.0)
                self.assertLessEqual(r["holm_p"], 0.05)
            for label in ("L1 own/nosink", "L1 own/statsd", "L1 own/otlp", "L2 own, arms pooled"):
                r = rows[(label, "p99")]
                self.assertTrue(r["status"].startswith("not shown (bound 120 us)"), r["status"])
                self.assertLess(abs(r["mean"]), 30.0)
            # the placebo beside L3: the same contrast on the own-core legs, never a verdict
            self.assertEqual(rows[("placebo: L3 own/nosink", "p99")]["status"], "descriptive")
            self.assertEqual(rows[("L3 shared/statsd", "p50")]["status"], "secondary: differs")
            md = TAB.markdown(res)
            self.assertIn("| L3 shared/statsd | 5 |", md)
            self.assertIn("longest admin wait / flush wall", md)
            cd = res["cells_detail"]["shared/statsd"]
            self.assertEqual(cd["flushes"], 5 * 6)
            self.assertAlmostEqual(cd["admin_longest_wait_over_flush_mean"], 1.0, delta=0.25)
            self.assertEqual(cd["watchdog_delta"], {"server.worker_0.watchdog_miss": 5})
            self.assertIn("0", cd["profile"])
        finally:
            shutil.rmtree(d)

    def test_under_four_complete_rounds_is_incomplete(self):
        d = tempfile.mkdtemp()
        try:
            write_run(d, rounds=3, cpu0_in_us=900.0)
            res = TAB.build(d)
            self.assertFalse(res["complete"])
            self.assertEqual({x["status"] for x in res["rows"]}, {"incomplete, no verdict"})
            self.assertIn("no verdict", TAB.markdown(res))
            # a round with one invalid leg does not count
            p = os.path.join(d, "legs.jsonl")
            legs = [json.loads(x) for x in open(p).read().splitlines()]
            legs[2]["verdict"] = {"valid": False, "reasons": ["x"]}
            with open(p, "w") as f:
                f.write("\n".join(json.dumps(m) for m in legs) + "\n")
            self.assertEqual(TAB.build(d)["rounds"], [2, 3])
        finally:
            shutil.rmtree(d)

    def test_a_flush_that_fills_the_interval_has_no_reach_and_no_verdict(self):
        d = tempfile.mkdtemp()
        try:
            write_run(d, rounds=4, cpu0_in_us=900.0, flush_s=3.6)
            rows = {(x["label"], x["metric"]): x for x in TAB.build(d)["rows"]}
            self.assertEqual(rows[("L3 shared/statsd", "p99")]["status"], "no reach, no verdict")
        finally:
            shutil.rmtree(d)

    def test_invalid_legs_stay_visible_with_their_reasons(self):
        d = tempfile.mkdtemp()
        try:
            write_run(d, rounds=4)
            p = os.path.join(d, "legs.jsonl")
            with open(p) as f:
                lines = f.read().splitlines()
            # round 2 ran twice: its first shared/statsd leg failed on a gate a stalled worker trips
            first = json.loads([x for x in lines if '"r02-shared-statsd"' in x][0])
            old = dict(first, verdict={"valid": False, "reasons": [
                "evidence: Nighthawk 2xx rate within 0.5% of its target: 4361.2, expected 4400 +/- 22"]})
            ok_old = dict(json.loads([x for x in lines if '"r02-own-nosink"' in x][0]))
            for m, lid in ((old, "r02-shared-statsd"), (ok_old, "r02-own-nosink")):
                m["leg_id"] = lid
            new = [json.loads(x) for x in lines]
            for m in new:
                if m["round"] == 2:
                    m["leg_id"] += ".rr1"
                    m["attempt"] = 1
            # and one invalid leg that was never re-run
            [m for m in new if m["leg_id"] == "r04-own-otlp"][0]["verdict"] = {"valid": False, "reasons": ["perf counters missing"]}
            for m in new:
                for sub in ("probe", "main"):
                    ext = ".jsonl.gz" if sub == "probe" else ".json.gz"
                    src = os.path.join(d, sub, m["leg_id"].replace(".rr1", "") + ext)
                    dst = os.path.join(d, sub, m["leg_id"] + ext)
                    if src != dst:
                        os.rename(src, dst)
            with open(p, "w") as f:
                f.write("\n".join([json.dumps(old), json.dumps(ok_old),
                                   json.dumps({"supersede": ["r02-shared-statsd", "r02-own-nosink"]})]
                                  + [json.dumps(m) for m in new]) + "\n")
            res = TAB.build(d)
            inv = {x["leg_id"]: x for x in res["invalid_legs"]}
            self.assertEqual(sorted(inv), ["r02-shared-statsd", "r04-own-otlp"])
            self.assertTrue(inv["r02-shared-statsd"]["superseded"])
            self.assertFalse(inv["r04-own-otlp"]["superseded"])
            self.assertEqual(inv["r02-shared-statsd"]["cell"], "shared/statsd")
            self.assertIn("Nighthawk 2xx rate", inv["r02-shared-statsd"]["reasons"][0])
            self.assertEqual(res["legs_run"], 22)
            self.assertEqual(res["rounds"], [1, 2, 3])     # round 4 has an invalid leg; round 2 counts by its re-run
            md = TAB.markdown(res)
            self.assertIn("| shared/statsd | 1 | r02-shared-statsd | yes | evidence: Nighthawk 2xx rate", md)
            self.assertIn("| own/otlp | 1 | r04-own-otlp | no | perf counters missing |", md)
            self.assertIn("| own/nosink | 0 | - | - | - |", md)
        finally:
            shutil.rmtree(d)

    def test_t_row_and_status(self):
        r = TAB.t_row([100.0, 110.0, 90.0, 105.0, 95.0])
        self.assertAlmostEqual(r["mean"], 100.0)
        self.assertTrue(r["lo"] < 100.0 < r["hi"] and r["lo"] > 85.0)
        self.assertLess(r["t_p"], 0.001)
        self.assertNotIn("lo", TAB.t_row([1.0, None, 2.0]))
        d = dict(r, primary=True, reach=150.0, floor=120.0, metric="p99", holm_p=0.001)
        self.assertEqual(TAB.status(d, True), "not shown (bound 150 us)")     # inside the reach
        self.assertEqual(TAB.status(dict(d, reach=40.0), True), "not shown (bound 120 us)")   # under the floor
        self.assertEqual(TAB.status(dict(d, reach=40.0, mean=400.0, lo=380.0, hi=420.0), True), "finding")
        self.assertEqual(TAB.status(dict(d, reach=40.0, mean=400.0, lo=380.0, hi=420.0, holm_p=0.2), True),
                         "not shown (bound 120 us)")
        self.assertEqual(TAB.status(dict(d, reach=None), True), "no reach, no verdict")
        self.assertEqual(TAB.status(d, False), "incomplete, no verdict")


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.cfg = os.path.join(GEN, "smoke-lat.json")
        self.queue_cfg = os.path.join(GEN, "lat.json")   # the rules and the budget are of the queue

    def tearDown(self):
        shutil.rmtree(self.d)

    def smoke(self, edit=None, **kw):
        d = os.path.join(self.d, "s%d" % len(os.listdir(self.d)))
        os.makedirs(d)
        write_run(d, rounds=1, **kw)
        if edit:
            p = os.path.join(d, "legs.jsonl")
            legs = [json.loads(x) for x in open(p).read().splitlines()]
            edit({(m["shape"], m["arm"]): m for m in legs})
            with open(p, "w") as f:
                f.write("\n".join(json.dumps(m) for m in legs) + "\n")
        return d

    def rules(self, d):
        return SESS.lat_rules(self.queue_cfg, d, out=io.StringIO())

    def test_clean_smoke_passes_the_rules(self):
        d = self.smoke()
        self.assertEqual(SESS.smoke_problems(self.cfg, d), [])
        self.assertEqual(self.rules(d), [])

    def test_each_rule_fails(self):
        cases = {
            "S-3": lambda c: c[("own", "nosink")]["lat"].update(worker_busy_mean=0.52),
            "S-4": lambda c: c[("shared", "statsd")]["lat"]["flush"].update(wall_s_max=7.4),
            "S-5": lambda c: c[("shared", "statsd")]["lat"]["manipulation"].update(in_over_others=2.0),
            "S-6": lambda c: c[("own", "statsd")]["lat"]["rx_queue"].update(max_share=0.7),
            "S-7": lambda c: c[("own", "otlp")]["lat"]["probe"]["control"].update(p99_us=2400.0),
            "S-9": lambda c: c[("own", "otlp")]["collector_delta"].update(accepted_metric_points_per_flush=310146.0),
        }
        for rule, edit in cases.items():
            probs = self.rules(self.smoke(edit))
            self.assertEqual(len(probs), 1, (rule, probs))
            self.assertTrue(probs[0].startswith(rule), probs)

    def test_missing_values_and_legs_fail_closed(self):
        probs = self.rules(self.smoke(lambda c: c[("shared", "statsd")]["lat"].pop("manipulation")))
        self.assertEqual(len([p for p in probs if p.startswith("S-5")]), 2)
        probs = self.rules(self.smoke(lambda c: c[("own", "statsd")].pop("udp_leg")))
        self.assertTrue(any(p.startswith("S-6") for p in probs))

        def drop(c):
            c[("own", "otlp")]["arm"] = "gone"
        d = self.smoke(drop)
        self.assertTrue(any("no smoke leg of own/otlp" in p for p in self.rules(d)))
        self.assertTrue(any("missing: own otlp" in p for p in SESS.smoke_problems(self.cfg, d)))

    def test_an_invalid_smoke_leg_is_a_problem(self):
        d = self.smoke(valid=False)
        self.assertEqual(len(SESS.smoke_problems(self.cfg, d)), 5)

    def test_budget(self):
        # limit 62 min: legs 130 s apart pass, 148 s apart (61.7 min) pass, 150 s (62.5 min) do not
        d = self.smoke()
        self.assertEqual(self.rules(d), [])

        def slower(c):
            for i, m in enumerate(c.values()):
                m["started_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(1.8e9 + self.gap * i))
        self.gap = 148
        self.assertEqual(self.rules(self.smoke(slower)), [])
        self.gap = 150
        probs = self.rules(self.smoke(slower))
        self.assertEqual(len(probs), 1)
        self.assertTrue(probs[0].startswith("S-8"))

    def test_stamp_binds_the_harness_and_the_config(self):
        cfg = os.path.join(self.d, "lat.json")
        shutil.copy(os.path.join(GEN, "lat.json"), cfg)
        st = os.path.join(self.d, "lat-check.json")
        self.assertEqual(SESS.main(["lat-stamp-ok", cfg, st]), 1)       # no check recorded
        self.assertEqual(SESS.main(["lat-stamp", cfg, st]), 0)
        self.assertEqual(SESS.main(["lat-stamp-ok", cfg, st]), 0)
        with open(cfg, "a") as f:
            f.write("\n")                                              # the config changed after the check
        self.assertEqual(SESS.main(["lat-stamp-ok", cfg, st]), 1)
        shutil.copy(os.path.join(GEN, "lat.json"), cfg)
        rec = json.load(open(st))
        rec["source_sha256"] = "0" * 64                                # another harness
        json.dump(rec, open(st, "w"))
        self.assertEqual(SESS.main(["lat-stamp-ok", cfg, st]), 1)

    def test_a_stale_or_hand_check_cannot_pass_an_older_smoke(self):
        cdir = os.path.join(self.d, "cfg")
        os.makedirs(cdir)
        q, sm = os.path.join(cdir, "lat.json"), os.path.join(cdir, "smoke-lat.json")
        for fn, c in MK.lat_configs(box(), None).items():
            with open(os.path.join(cdir, fn), "w") as f:
                json.dump(c, f, indent=1)
        smoke = os.path.join(self.d, "smoke-lat")
        # a smoke directory nobody stamped (not run by lat-smoke)
        os.makedirs(smoke)
        self.assertEqual(SESS.main(["lat-smoke-stamp-ok", q, sm, smoke]), 1)
        self.assertEqual(SESS.main(["lat-smoke-stamp", sm, smoke]), 0)
        self.assertEqual(SESS.smoke_stamp_problems(q, sm, smoke), [])
        self.assertEqual(SESS.main(["lat-smoke-stamp-ok", q, sm, smoke]), 0)
        # the knobs changed after the smoke (a 50 s window regenerated over a 60 s smoke, or the reverse)
        for fn, c in MK.lat_configs(box(), None, {"window_s": 50}).items():
            with open(os.path.join(cdir, fn), "w") as f:
                json.dump(c, f, indent=1)
        probs = SESS.smoke_stamp_problems(q, sm, smoke)
        self.assertEqual(len(probs), 1)
        self.assertIn("another smoke-lat.json", probs[0])
        # only lat.json regenerated (another session's rewrite without the knobs): not this smoke's queue config
        with open(sm, "w") as f:
            json.dump(MK.lat_configs(box(), None)["smoke-lat.json"], f, indent=1)
        probs = SESS.smoke_stamp_problems(q, sm, smoke)
        self.assertEqual(len(probs), 1)
        self.assertIn("not the queue config", probs[0])
        with open(q, "w") as f:
            json.dump(MK.lat_configs(box(), None)["lat.json"], f, indent=1)
        self.assertEqual(SESS.smoke_stamp_problems(q, sm, smoke), [])
        # the harness sources changed after the smoke
        sp = os.path.join(smoke, SESS.SMOKE_STAMP)
        with open(sp) as f:
            st = json.load(f)
        st["source_sha256"] = "0" * 64
        with open(sp, "w") as f:
            json.dump(st, f)
        probs = SESS.smoke_stamp_problems(q, sm, smoke)
        self.assertEqual(len(probs), 1)
        self.assertIn("another harness source", probs[0])
        self.assertEqual(SESS.main(["lat-smoke-stamp-ok", q, sm, smoke]), 1)

    def test_entry_points(self):
        sh = open(os.path.join(SF, "run-session.sh")).read()
        for mode in ("lat-smoke)", "lat-check)", "lat-queue)"):
            self.assertIn("\n  " + mode, sh)
        q = sh[sh.index("\n  lat-queue)"):sh.index("\n  restore)")]
        # the queue never rewrites the configs, checks the stamp first, runs inside the guard, has its stop
        self.assertNotIn("rewrite", q)
        self.assertLess(q.index("lat-stamp-ok"), q.index("guard_begin"))
        self.assertLess(q.index("guard_begin"), q.index("$EPL run"))
        self.assertIn("LAT_STOP_S:-4500", q)
        # Q1: the check first requires the smoke to be of these sources and configs; lat-smoke stamps
        # the directory before its run
        chk0 = sh[sh.index("lat_check() {"):sh.index("rewrite_lat() {")]
        self.assertLess(chk0.index("lat-smoke-stamp-ok"), chk0.index("smoke-valid"))
        sm = sh[sh.index("\n  lat-smoke)"):sh.index("\n  lat-check)")]
        self.assertLess(sm.index("rewrite_lat"), sm.index("lat-smoke-stamp "))
        self.assertLess(sm.index("lat-smoke-stamp "), sm.index("$EPL run"))
        chk = sh[sh.index("lat_check() {"):sh.index("rewrite_lat() {")]
        self.assertIn("evidence-check \"$C/lat.json\"", chk)
        self.assertNotIn("--freeze", chk)
        self.assertIn("smoke-valid", chk)
        for word in ("pkill", "killall"):
            for fn in ("run-session.sh", "lat_table.py", "session.py", "make.py"):
                self.assertNotIn(word, open(os.path.join(SF, fn)).read())
            for fn in ("latprobe.py", "latency.py", "udpsink.py"):
                self.assertNotIn(word, open(os.path.join(HERE, "epl", fn)).read())


class LegSourceTest(unittest.TestCase):
    """What can only run on the box, held by the order of the source."""

    def test_order_of_the_loaded_leg(self):
        src = open(os.path.join(HERE, "epl", "leg.py")).read()
        body = src[src.index("    def run_leg("):src.index("    def _lat_before(")]
        i_before = body.index("lx = self._lat_before(")
        i_client = body.index('cl = self.own.start(["taskset", "-c", e["cpus"]["client"], nh] + ma')
        i_t0 = body.index('lx["t0"] = t0 = time.monotonic()')
        i_perf = body.index("pr = subprocess.run(pcmd(envoy.pid)")
        i_t1 = body.index("                    t1 = time.monotonic()")
        i_stop = body.index('statsrow.stop_latprobe(self.own, lx.pop("probe")')
        i_wait = body.index("cl.wait(timeout=dur + 120)")
        i_after = body.index("self._lat_after(")
        # reads and the probe's map before the client; the probe stopped after the window and the
        # count read; the post reads after the client ended
        self.assertLess(i_before, i_client)
        self.assertLess(i_client, i_t0)
        self.assertLess(i_t0, i_perf)
        self.assertLess(i_perf, i_t1)
        self.assertLess(i_t1, body.index("t_q1 = time.monotonic()"))
        self.assertLess(body.index("t2 = time.monotonic()"), i_stop)
        self.assertLess(i_stop, i_wait)
        self.assertLess(i_wait, i_after)
        # no admin read between t0 and t1
        for call in ("admin_stats(", "admin_get(", "admin_prometheus(", "stats_read(", "admin_text("):
            self.assertNotIn(call, body[i_t0:i_t1])
        # the probe is only ever stopped through the registry of this run's own children
        lat = src[src.index("    def _lat_before("):src.index("    # ---------------------------------------------------------------- idle legs")]
        self.assertNotIn("os.kill", lat)
        self.assertNotIn("os.kill", open(os.path.join(HERE, "epl", "latprobe.py")).read())

    def test_probe_start_refuses_without_a_map(self):
        class Own:
            def __init__(self):
                self.stopped = []

            def start(self, args, **kw):
                self.args = args
                return subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(3)"])

            def stop(self, p, grace_s=10.0):
                self.stopped.append(p.pid)
                p.wait()
                return p.returncode
        d = tempfile.mkdtemp()
        try:
            own = Own()
            sp = os.path.join(d, "p.json")
            with self.assertRaises(RuntimeError) as cm:
                with open(sp, "w") as f:
                    pass
                statsrow.start_latprobe(own, "31", ["--x", 1], sp, wait_s=5.0)
            self.assertIn("latency probe not ready", str(cm.exception))
            self.assertEqual(own.args[:3], ["taskset", "-c", "31"])
            self.assertEqual(len(own.stopped), 1)
        finally:
            shutil.rmtree(d)


class LegMethodsTest(unittest.TestCase):
    """The three run-L steps of the leg on stand-ins for the box (admin reads, /proc, the probe
    process): the field names they write are the ones the config's evidence reads."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.saved = {}

    def tearDown(self):
        for (mod, name), v in self.saved.items():
            setattr(mod, name, v)
        shutil.rmtree(self.d)

    def patch(self, mod, name, fn):
        self.saved.setdefault((mod, name), getattr(mod, name))
        setattr(mod, name, fn)

    def run_arm(self, arm_name, shape_name="own", breakage=None):
        from types import SimpleNamespace as NS
        from epl import origin
        exp = experiment.load(os.path.join(GEN, "lat.json"))
        arm = [a for a in exp["arms"] if a["name"] == arm_name][0]
        shape = [s for s in exp["shapes"] if s["name"] == shape_name][0]
        aenv = experiment.arm_envoy(exp, arm, self.d)
        lat = exp["measure"]["latency"]
        kind = (aenv.get("stats_sink") or {}).get("kind")
        k = 10000
        x = synth()
        answered = sum(1 for r in x["probe"]["rows"] if r[0] == "d")
        used, hist = 360107, 50009
        if kind == "otlp":
            used, hist = 360147, 50012
        c = "cluster.otel_collector."
        reads = [
            {"status": 200, "total": 1180396, "histograms": 50013, "text_readouts": 0, "seconds": 2.2, "bytes": 9,
             "numeric": {"cluster_manager.active_clusters": k + (2 if kind == "otlp" else 1), "server.uptime": 30,
                         "server.dropped_stat_flushes": 0, "server.worker_0.watchdog_miss": 1,
                         "http.ingress_http.downstream_rq_2xx": 36000,
                         "server.main_thread.watchdog_miss": 2, c + "upstream_rq_total": 37 * 3,
                         c + "http2.rx_reset": 0}},
            {"status": 200, "total": used, "histograms": hist, "text_readouts": 0, "seconds": 0.8, "bytes": 9,
             "numeric": {"server.uptime": 115, "server.worker_0.watchdog_miss": 4,
                         "http.ingress_http.downstream_rq_2xx": 36000 + 330000 + 1600 + answered - (
                             1 if breakage == "count" else 0),
                         "http.ingress_http.downstream_rq_completed": 420000, "http.admin.downstream_rq_completed": 1700,
                         "http.ingress_http.downstream_cx_destroy": 1300, "http.admin.downstream_cx_destroy": 1690,
                         "cluster.origin.upstream_cx_total": 10600, "cluster.origin.upstream_cx_destroy": 10090,
                         "server.main_thread.watchdog_miss": 2, c + "upstream_rq_total": 37 * 11}}]
        self.patch(statsrow, "stats_read", lambda port, timeout, usedonly=False: reads.pop(0))
        self.patch(statsrow, "quiesce", lambda pid, port=None, timeout_s=30.0: (True, 0.03))
        udp = [{"snmp": {"InDatagrams": 100, "RcvbufErrors": 0, "NoPorts": 5}, "sock": {"rx_queue": 0, "drops": 0}},
               {"snmp": {"InDatagrams": 100 + (3000000 if kind == "statsd" else 40), "RcvbufErrors": 0, "NoPorts": 5},
                "sock": {"rx_queue": 0, "drops": 0}}]
        if kind != "statsd":
            for u in udp:
                u["sock"] = None
        self.patch(statsrow, "udp_counters", lambda port: udp.pop(0))
        self.patch(legmod, "admin_stats", lambda port, timeout=5.0: {})

        class Clock:
            """The leg's clock: the pre-client read at 0 s, the post-client read 86 s later."""
            seq = [0.0, 1.0, 2.0, 86.0]

            def monotonic(self):
                return self.seq.pop(0)

            def __getattr__(self, name):
                return getattr(time, name)
        self.patch(legmod, "time", Clock())
        self.patch(legmod.sysprobe, "cpus_allowed", lambda pid: "31")
        started = {}

        def start(own, cpu, args, summary_path, wait_s=60.0):
            started.update(cpu=cpu, args=[str(a) for a in args], summary=summary_path)
            return NS(pid=777, poll=lambda: None)
        self.patch(statsrow, "start_latprobe", start)
        scr = [{"accepted_metric_points": 5 * used, "refused_metric_points": 0},
               {"accepted_metric_points": 13 * used, "refused_metric_points": 0}]
        coll = NS(scrape=lambda: dict(scr[0])) if kind == "otlp" else None
        self.patch(statsrow, "settled_scrape", lambda collector, tries=20, step_s=0.25: dict(scr.pop(0), _settled=True))
        os.makedirs(os.path.join(self.d, "collector"))
        with open(os.path.join(self.d, "collector", "config.yaml"), "w") as f:
            f.write(origin.collector_conf(4317, 8888, True, None if breakage == "no-limit" else 64))
        stub = NS(exp=exp, run_dir=self.d, own=None, collector=coll)
        stub._collector_cfg = lambda: legmod.RealBackend._collector_cfg(stub)
        m = {"shape": shape_name, "arm": arm_name, "envoy_pid": 500, "nofile_soft": 60000, "envoy_log_emfile": 0,
             "prime": {"ok": k, "non200": 0, "errors": 0}, "gen_cx_connect_fail": 0, "gen_cx_overflow": 0,
             "lat_senders_running": True, "client_rate_2xx": 4399.0,
             "lat_nh": {"open_loop": True, "sent_ratio": 1.0, "responses_2xx": 330000},
             "sut_stats_leg_end": {"http.ingress_http.downstream_rq_completed": 420000}, "sut_stats_leg_end_ok": True}
        sink = NS(pid=600) if kind == "statsd" else None
        lx = legmod.RealBackend._lat_before(stub, m, aenv, NS(pid=500), sink, "r01-x", lat, 42.0, shape, 4)
        # the probe is started on its own CPU with the config's numbers and this Envoy's pid
        self.assertEqual(started["cpu"], "31")
        a = started["args"]
        for flag, val in (("--envoy-pid", "500"), ("--listener-port", "10110"), ("--admin-port", "9921"),
                          ("--origin-port", "8092"), ("--per-worker", "4"), ("--data-hz", "50"), ("--path", "/s"),
                          ("--map-margin", "5.0"), ("--map-max-opens", "64"), ("--control-hz", "25")):
            self.assertEqual(a[a.index(flag) + 1], val, flag)
        with open(os.path.join(HERE, "epl", "latprobe.py")) as f:
            src = f.read()
        self.assertTrue(all('ap.add_argument("%s"' % flag in src for flag in a[0::2]))   # flags the probe knows
        self.assertEqual(lx["port"], 8125 if kind == "statsd" else None)
        self.assertGreaterEqual(lx["count_read_s"], 0.0)
        # the window, as run_leg fills it in
        sampler = NS(samples=[(t, r) for t, r, _ in x["series"][500]], series=x["series"], period_s=0.005,
                     missing=0, affinity=[30], rx_queue=[(1001.0, 4096), (1002.0, 1 << 20)])
        lx.update(t0=x["t0"], t1=x["t1"], sampler=sampler, clock=x["pairs"], summary=dict(x["summary"], exit=0))
        lx.pop("probe")
        self.assertTrue(lx["pins_ok"](lx["summary"], sampler))
        self.assertFalse(lx["pins_ok"](dict(lx["summary"], cpus_allowed=[20, 31]), sampler))
        self.assertFalse(lx["pins_ok"](lx["summary"], NS(affinity=[20, 21])))
        with gzip.open(lx["log"], "wt") as f:
            f.write(json.dumps(x["probe"]["meta"]) + "\n")
            for row in x["probe"]["rows"]:
                f.write(json.dumps(row) + "\n")
            if breakage != "probe-killed":
                f.write(json.dumps({"end": x["probe"]["end"]}) + "\n")
        lx["tu0_ns"] = int(985 * 1e9)
        legmod.RealBackend._lat_after(stub, m, aenv, NS(pid=500), sink, lat, 42.0, lx)
        lx["tu1_ns"] = int(1075 * 1e9)
        if kind == "statsd":
            cg = used - hist
            m["udpsink"] = {"rcvbuf_granted": 536870912, "drain_quiet": True,
                            "classes": {"c": 1, "g": 1, "h": 0, "other": 0, "ms": legmod.timer_lines_expected(
                                lx["post"]["numeric"])["total"] + (40000 if breakage == "timer-lines" else 300)},
                            "marks": [[int((988 + 10 * i) * 1e9), 30.0 + 10 * i, (cg - 100000) * i, 100000 * i, 0, 0]
                                      for i in range(9)]}
        legmod.RealBackend._lat_finish(stub, m, aenv, shape, "r01-x", lat, lx, legmod.rung_of(exp, shape))
        dump = {"bootstrap": {"stats_sinks": [1]}} if kind else {"bootstrap": {}}
        ev = evidence.evaluate(m, arm["evidence"], dump)
        return m, ev, exp

    def test_every_arm_passes_its_own_evidence_from_the_leg_methods(self):
        for arm, shape in (("nosink", "own"), ("statsd", "shared"), ("otlp", "own")):
            self.tearDown()
            self.setUp()
            m, ev, exp = self.run_arm(arm, shape)
            # the calibrated counts are not in an uncalibrated config: every other item is there
            self.assertNotIn("lat_error", m, m.get("lat_error"))
            self.assertEqual(ev["failed"], [], arm)
            self.assertGreater(len(ev["items"]), 40)
            self.assertEqual(m["stats_total"], 1180396)
            self.assertEqual((m["uptime"]["delta_s"], m["uptime"]["elapsed_s"]), (85, 86.0))
            self.assertEqual(m["watchdog_delta"]["server.worker_0.watchdog_miss"], 3)
            self.assertEqual(m["main_thread_delta"], {"server.main_thread.watchdog_miss": 0})
            self.assertEqual(m["lat"]["probe"]["data_in_window"], 48000)
            self.assertEqual((m["lat_count"]["error"], m["lat_count"]["map_requests"]), (0, 1600))
            # the series of the leg is saved, and the table reads it back
            ser = latency.load_series(os.path.join(self.d, "main", "r01-x.json.gz"))
            self.assertEqual(sorted(ser["series"]), [500, 501, 502, 503, 504])
            self.assertEqual(ser["window_mono"], [1000.0, 1060.0])
            self.assertEqual(len(ser["bursts"]), 6)
            self.assertEqual(ser["threads"][500], {"comm": "main", "cpus": "4" if shape == "own" else "0"})
            json.dumps(m)   # the leg record is plain JSON
            if arm == "statsd":
                sd = m["lat"]["statsd"]
                self.assertEqual((sd["flushes"], sd["marks_window"]), (8, 6))
                self.assertEqual(sd["ms_expected"]["total"], 3 * 420000 + 1700 + 2 * 2990 + 10600 + 10090)
                self.assertLess(sd["ms_error_share"], 0.001)
                self.assertAlmostEqual(m["lat"]["rx_queue"]["max_share"], (1 << 20) / 536870912.0)
            if arm == "otlp":
                self.assertEqual(m["otlp_cluster"]["flushes"], 8.0)
                self.assertEqual(m["collector_delta"]["fit"]["n"], 8)
                self.assertEqual(m["collector_cfg"], {"max_recv_msg_size_mib": 64})

    def test_failures_of_the_steps_fail_closed(self):
        m, ev, _ = self.run_arm("otlp", breakage="no-limit")
        self.assertTrue(any("64 MiB receive limit" in f for f in ev["failed"]), ev["failed"])
        self.tearDown()
        self.setUp()
        m, ev, _ = self.run_arm("nosink", breakage="count")
        self.assertEqual(m["lat_count"]["error"], -1)
        self.assertEqual(len(ev["failed"]), 1)
        self.assertIn("exactly", ev["failed"][0])
        self.tearDown()
        self.setUp()
        m, ev, _ = self.run_arm("statsd", "shared", breakage="timer-lines")
        self.assertEqual(len(ev["failed"]), 1)
        self.assertIn("the leg's own counters say", ev["failed"][0])
        self.tearDown()
        self.setUp()
        m, ev, _ = self.run_arm("nosink", breakage="probe-killed")
        self.assertTrue(any("the probe wrote its whole log" in f for f in ev["failed"]))
        # the record step itself failing marks the leg, and no lat field is left to pass a gate
        stub = __import__("types").SimpleNamespace(run_dir=self.d)
        m2 = {"envoy_pid": 500}
        legmod.RealBackend._lat_finish(stub, m2, {}, {}, "r01-y", {}, None, {})
        self.assertIn("run L record", m2["error"])
        self.assertNotIn("lat", m2)
        self.assertFalse(validity.verdict(m2)["valid"])


if __name__ == "__main__":
    unittest.main()
