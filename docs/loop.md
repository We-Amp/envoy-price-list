# epl-agentd: the operator's guide to the loop daemon

`epl-agentd` is the loop daemon on the measurement box. An agent drives it over MCP to screen a runtime guard
(or another runtime key) quickly. **Its results are screens, not measurements.** Every number it returns is
labelled "in-process effect, Exploratory" (screens) or "Exploratory, steering only; not a screen" (explore).
No calibration factor is applied. A survivor becomes a candidate record, and only a pre-registered
between-process confirmation session with the harness can turn it into a row.

The code is in `loop/`. Its tests run on any machine against the stand-ins in `loop/standin/` (a fake Envoy admin
process, a fake client and a fake perf), with no box and no Envoy:

```sh
python3 -m unittest tests.test_loop tests.test_loop_e2e tests.test_run_mcp tests.test_flipblock \
    tests.test_split_block tests.test_master_session tests.test_foreign_loginctl
```

The examples below use three shell variables. Set them for your own setup:

```sh
EPL_BOX=bench-box                          # the box's ssh host name (or an alias in ~/.ssh/config)
EPL_CM="$HOME/.ssh/cm/epl-%r@%h:%p"        # the ControlMaster's socket path (ssh expands %r, %h, %p)
EPL_HOME=~/epl                             # on the box: the daemon's home (the default)
```

## What a screen is

- A screen flips one candidate key on one staged arm, at one shape and rate.
- It runs **N ≥ 6 short Envoy process instances**. N is fixed when the screen starts, and the screen is never
  extended.
- Each instance is one flip block (`loop/flipblock.py`): one fresh Envoy and one continuous client.
  - It runs P counterbalanced control pairs (A = off, B = on). The order is mirrored on odd instances. An odd P
    needs an even N.
  - It runs one in-instance A/A pair (B, C: the on value written twice). The pair comes last on odd-numbered
    instances and first on even-numbered ones.
  - flipblock's per-window and per-block validity applies, plus these items:
    - no thread of ours on a SUT CPU or a SUT sibling;
    - perf's counting span within 50 ms of W;
    - the same number of admin reads in every window.
- **The interval is taken across instances**, with the instance as the unit (t, df N − 1).
- **A complete screen shows:**
  - the per-instance effects;
  - the across-instance interval and its MDE;
  - the within-instance pooled SD and the between-instance SD component;
  - the marker (instructions:u per request, off − on; `marker_min` applies to |marker| with one sign in every
    instance);
  - the A/A check (its marker bound defaults to `marker_min / 4`);
  - validity (every planned instance valid, at least 6, no replacement).
- **Blinding:**
  - **No effect figure can be read before the screen is complete.** An open screen's `screen_result` shows only
    progress and validity, and its `screen_telemetry` is refused.
  - **An aborted screen never shows effect figures**, not even afterwards.
- **The screen register (`register.json`)** lists every `screen_start` of the session, refused ones included.
  - A second screen of the same (arm, key, off, on, shape, rate) is refused unless it names `repeat_of: "scrNN"`.
  - Every record in `candidates.jsonl` names the screens of its key and the session's screen count (the family
    size), so the confirmation plan can choose its multiplicity rule.
  - There is no sequential stopping rule, by design.

## Per-second telemetry (one clock: the box's CLOCK_MONOTONIC)

- **CPU:** each window's perf is `perf stat -x , -I 1000 -e <events> -p <envoy>`.
  - It is started through the instance's PID ledger (role `perf`) and stopped in a `finally` if anything
    interrupts it.
  - It never uses `--timeout`: perf 6.8 refuses that together with `-I`.
  - It is ended by a `-- sleep W` workload (`perf_mode: "sleep"`, the default), or by one SIGINT W after the
    counter enable (`"signal"`). The enable is read from perf's first interval line.
  - The window's totals are the sum of its intervals, over perf's own span, scaled to W.
  - Rows are anchored at perf's reap minus its last interval time.
- **Envoy:** admin reads with a tight filter, phase-locked to the windows: exactly W reads inside each window, at
  +0.5 s + j, then gap reads from perf's end. No statsd sink.
- **Nighthawk:** live snapshots from `nighthawk://series`, in explore mode through `nighthawk_mcp` from the
  Nighthawk fork's MCP and series changes. The plain `nighthawk_client`, which screens use, has no live output.

## The stdio route (one TCP login per session)

The daemon is an MCP server on stdio. The agent's MCP client starts it as its command over ssh, so every MCP
frame travels inside one ssh session: nothing polls the box, and no second login appears.

The direct form, when the agent's process can open a TCP connection to the box:

```json
{"mcpServers": {"epl-agentd": {"command": "ssh", "args": [
  "-T", "-o", "BatchMode=yes", "bench-box", "exec ~/epl/loop/run-mcp.sh agentd"]}}}
```

If the agent's process cannot open TCP connections to the box itself (a sandbox, a background job, a jump host),
use one OpenSSH ControlMaster started from a shell that can, and give the agent a mux client. The mux client only
talks to the master's Unix socket; the mux protocol passes its stdin and stdout to the master, which relays the
JSON-RPC stream over its one TCP connection.

1. **Start the master** from your shell, in any long-lived terminal (on macOS, `caffeinate -i` keeps the master
   from sleeping), after the pre-flight login has ended:
   ```sh
   mkdir -m 700 -p ~/.ssh/cm
   caffeinate -i ssh -N -T \
       -o ControlMaster=yes -o ControlPersist=no -o ControlPath="$EPL_CM" \
       -o BatchMode=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=6 \
       -o ClearAllForwardings=yes "$EPL_BOX"
   ```
   (Leave out `caffeinate -i` on Linux.)
2. **Check the route** with `loop/route-check.sh "$EPL_BOX" "$EPL_CM" MODE`:
   - **`local`, from the agent's own context, any time.** It sends nothing to the box. It checks that the master
     runs on the socket, and that with no master the client fails at once (rc 255) and opens no TCP connection.
   - **`box`, inside the pre-flight login, before the session's first pre-flight snapshot.** It sends one command
     (`exec cat`, an sshd session process and a shell on the box) and checks that a JSON line round-trips through
     the master byte for byte. Run there, the foreign-activity check and the start state never see it.
   - **`all`** runs the three, against a localhost master.
3. **The agent's MCP config.** Never `-t`: a pty would rewrite line endings and turn hangup into SIGHUP.
   ```json
   {"mcpServers": {"epl-agentd": {"command": "ssh", "args": [
     "-T", "-o", "ControlMaster=no", "-o", "ControlPath=<your control path>",
     "-o", "ProxyCommand=/usr/bin/false", "-o", "BatchMode=yes",
     "<box>", "exec ~/epl/loop/run-mcp.sh agentd"]}}}
   ```
   `ProxyCommand=/usr/bin/false` makes the client fail closed when the master is gone: it never falls back to a
   direct login. Write the control path out in full, the same as the master's (`$EPL_CM` is a shell variable,
   and the JSON is not run through a shell; ssh's own `%r`, `%h` and `%p` tokens are fine).
   - `run-mcp.sh` takes one argument: a config name under `$EPL_HOME/loop/` (`agentd` for
     `$EPL_HOME/loop/agentd.json`) or a path. It reads `EPL_HOME` once (default `~/epl`) and passes it to the daemon
     as `--home`. It refuses (rc 2, nothing on stdout) a config without `housekeeping_cpus`.
   - **The login-session gate is opt-in.** With `EPL_SESSION_RECORD=<file>` set on the box, the daemon starts only
     when its logind session is already recorded in that file on a `master` or `login-*` line (`loop/state.py
     master --run-dir R` writes the `master` line to `R/state/own-sessions.txt` after the master-session check
     passes), and then appends a `loop-<config>` audit line. Without it, `run-mcp.sh` logs one audit line to
     stderr and starts the daemon. The gate is worth having on a shared box.
   - Set the client's MCP tool timeout above 900 s, or use `wait_s` ≤ 300 with repeated `screen_wait` calls. Those
     calls stay inside the one channel and do not poll the box. With Claude Code as the MCP client, the setting is
     the `MCP_TOOL_TIMEOUT` environment variable (milliseconds). Any MCP client that speaks stdio works the same
     way.
4. **Emergency stop:** `ssh -o ControlPath="$EPL_CM" -O exit "$EPL_BOX"`. It closes every channel, the daemon
   sees EOF, and it tears down. (`-O stop` only refuses new clients.)
5. **The clean-proof login** (the clean proof and the collection) runs as a mux client through the same master,
   after the MCP session ends. Then `-O exit`.

- **Box rc files:** confirm that the box's `~/.bashrc`, `~/.bash_profile` and `/etc/bash.bashrc` print nothing
  for a non-interactive shell. Any output would land in the MCP stream before `exec`.
- **Logins are checked with logind:** `loginctl list-sessions` and `loginctl session-status <id>`. `who` and
  `last` do not list non-pty ssh sessions such as this one. `session_status` and `teardown.json` carry the
  user's logind sessions.
- **Cheap is not free:** every mux command still forks an sshd session process and a shell on the box. Do not
  poll the box.

## Starting a session

1. **Stage** the following, by sha256, before the pre-flight login, with no copy while a session runs:
   - the harness at `$EPL_HOME/loop/harness` (a copy of this repository);
   - `$EPL_HOME/loop/agentd.json`, from `loop/agentd.example.json`;
   - the arms' binaries, the pinned client, and for explore, `nighthawk_service` and `nighthawk_mcp` from the
     Nighthawk fork.
   An arm is a flip-block base config (templates in `examples/flip/`):
   - its `keys` are the only runtime keys a screen may flip. A key may declare its `read_point`: `per_config` is
     refused; `per_connection` needs `flip_extra.cycle_connections`;
   - its `shapes` are the only shapes it runs.
2. **Write the box's state file** from `loop/state.example.json`: the watched directories, the pinned directory
   and its files, the binaries a session may stage, the paths allowed until the final proof, the timers whose runs
   are expected, and any further process names of your own tools.
3. **Take the start state** (`loop/state.py snapshot START.json --state state.json`, and
   `loop/foreign.py snapshot FOREIGN.json --runs R --state state.json`) and run the session's idle and
   foreign-activity pre-flight.
4. **Start the master** (above), if you use one. The MCP client then starts the daemon.
5. **The daemon at start** pins itself (and its threads) to `housekeeping_cpus`. There is no default: the
   daemon refuses to start without it, because a wrong default on another machine would put the daemon on a SUT
   CPU. `run-mcp.sh` reads the same value from the config. The daemon pins its own ssh-session ancestors there too,
   and records `lscpu -e` in `agentd.json`. **It refuses to start (rc 2)** when:
   - the config names no `housekeeping_cpus`;
   - the housekeeping CPUs touch a SUT CPU, `cpus.client`, `cpus.origin` or their siblings;
   - an arm's `cpus.flip_tools` lies outside them;
   - the workdir is inside the harness tree (the default workdir is `$EPL_HOME/runs/loop`);
   - **a previous epl-agentd is still alive** (its `agentd.json` pid and start ticks verify);
   - a previous session left a verified process in a ledger.
   In the last two cases, wait for the previous teardown or run the clean proof. Never reconnect into a half state.

## Stopping and cleaning up

| Ending | rc | `teardown.json` reason |
|---|---|---|
| The agent closes the MCP client, `-O exit`, or the channel is closed | 0 | `eof` |
| A mux client is killed (SIGTERM) | 0 | `eof` |
| The session time limit (`session_ttl_s`, default 4 h, at most 12 h) | 4 | `ttl` |
| **The idle limit:** no inbound message for `idle_ttl_s` (default 900 s, 300-3600), with no step running inside its planned time plus the hang guard. This covers a half-open channel (the workstation asleep, a dead link) | 5 | `idle` |
| An exception anywhere in the daemon's loop | 6 | `error: …` |
| SIGTERM, SIGHUP or SIGINT | 143 | `signal N` |

- `abort` stops the running work and keeps the session open.
- **The teardown steps,** each isolated so that one failure never skips the next (errors are recorded under
  `errors`):
  1. the running instance: one SIGTERM, a 60 s grace, and the step join bounded at 90 s;
  2. the explore traffic, `nighthawk_service` and Envoy;
  3. `ledger.py stop` over every ledger (verified start ticks only);
  4. our registered children;
  5. every remaining `side.json`'s containers, by ID.
  The whole teardown takes **at most about 2.5 minutes**.
- **Then the clean-proof login:** the full clean proof (`loop/state.py proof START.json --state state.json
  --final`, with `--own-sessions` and `--master-session` when the session gate is on) and the collection of
  `$EPL_HOME/runs/loop/session-<utc>-<pid>/`.

## The agent MAY

- Use these tools:
  - `screen_start`, `screen_step`, `screen_wait`, `screen_result`, `screen_telemetry` (finished screens only);
  - `explore_start`, `runtime_set`, `traffic_start`, `traffic_steer`, `traffic_stop`, `traffic_status`,
    `telemetry_read`, `explore_stop`;
  - `abort`, `session_status`, `cleanproof`.
- Choose, within the config:
  - the arm, the candidate key and its off and on values, and the shape (all from the config's lists);
  - the rate (whole, divisible by the client's workers, at most `max_rps`);
  - N (6-40) and P (2-16);
  - the window (`min_window_s`..60 s) and the gap;
  - `repeat_of` for a declared repeat.
- Change rate and shape live **in explore mode only**, through `nighthawk_mcp`. The target is fixed by the
  daemon.

## The agent MAY NOT

- Read a screen's effects before the screen is complete, or ever for an aborted screen.
- Repeat a key in a session without `repeat_of`. Extend or pool a screen.
- Name a binary, a path, a target URI, or a key or shape outside the config. No tool takes a path.
- Steer traffic during a screen: screens use the plain client, unsteered.
- Run tracers or profilers. `perf record`, bpftrace and `pull_profile_window` are not offered.
- **Write or produce a published row.** The daemon writes only under its session directory. Its records say "not
  a published row". No screen or explore number belongs in the price list; it goes to a pre-registered
  between-process plan first.

## Files in a session directory

| Path | What |
|---|---|
| `agentd.json` | the daemon's PID and start ticks, the limits, the CPUs, `lscpu -e` |
| `ledger.jsonl` | every process the daemon started (role, pid, start ticks) |
| `events.log` | `<utc_iso_ms> <monotonic_ns> <event> <detail>` |
| `register.json` | the screen register: every screen_start, its key, status and `repeat_of` |
| `scrNN/spec.json`, `scrNN/iKK.json` | the screen spec and each instance's flip-block config (`scrNN.refused/` when set aside) |
| `scrNN/iKK/` | `block.json` (flipblock's record plus `loop`), `telemetry.json` (per-second rows, perf spans and anchors), `ledger.jsonl` (Envoy, client, perf), logs, perf CSVs, the client JSON |
| `scrNN/result.json` | the screen's result (complete, or aborted without effect figures) |
| `candidates.jsonl` | one record per finished screen: a candidate, or "screen record, not a candidate" |
| `expNN/` | an explore session's config, ledger and logs |
| `teardown.json` | the teardown's record: reason, errors, ours, logind sessions |

## The files in `loop/`

| File | What |
|---|---|
| `agentd.py` | the daemon: the MCP server, the session, the start checks and the teardown |
| `screen.py` | the screen spec, the per-instance flip-block config and the analysis |
| `instance.py` | one screen instance, run as its own process |
| `telemetry.py` | perf intervals, the phase-locked admin sampler and the one-clock timeline |
| `flipblock.py` | one flip block (runtime flips between windows in one Envoy process); also runs on its own |
| `ledger.py`, `side.py`, `evlog.py` | the PID ledger, the side containers by ID, the event log |
| `state.py`, `state.example.json` | the start state, the clean proof against the operator's state file, the master-session check |
| `foreign.py` | the foreign-activity check (processes, units, timers, logins, logind sessions) |
| `run-mcp.sh`, `route-check.sh` | the stdio entry on the box, and the check of the ControlMaster route |
| `agentd.example.json`, `standin/` | an example box config, and the stand-ins for the tests |
