# Wave 5, track H: the CPU price of the kernel's CPU-vulnerability mitigations

What Linux's default CPU-vulnerability mitigations (page-table isolation, CPU buffer clearing on kernel
exit, retpolines and the rest of what `mitigations=off` turns off) cost Envoy v1.40.2 per request, on
the price list's shapes and on a syscall-heavy shape; what the two per-task mitigations a process can
opt into (prctl `PR_SET_SPECULATION_CTRL`: Speculative Store Bypass and indirect branch speculation)
cost; and a check of whether the median-latency shift seen with `TCP_DEFER_ACCEPT` (wave 3) comes from
CPU idle-state exits. Config only: the official binary in every arm.

## Design

Boot-time mitigations are fixed when the kernel boots, so on and off cannot alternate inside one run
and paired rounds across them are impossible. The same configs therefore run unchanged in three boots:

| Block | Boot | Runs |
|---|---|---|
| H0 | the current boot (before the series) | `h-defer-deep`, `h-defer-c1only` |
| A | fresh boot, mitigations on (one-shot entry with the default command line) | `h-pl`, `h-c1` |
| B | fresh boot, `mitigations=off` (one-shot entry) | `h-pl`, `h-c1` |
| C | fresh boot, mitigations on | `h-pl`, `h-c1`, `h-spec` |

- Inside every block each run has a same-boot A/A arm and its own validity gates.
- Across blocks the level of each shape (mean per-round log of cycles per request over the A/A pair)
  is compared: P = (A + C)/2 - B is the price of the mitigations ("on minus off"); A - C, two boots in
  the same state, is the boot-to-boot noise floor, and a shape whose A - C is at the kill line is
  inconclusive. User instructions per request must agree across the three boots (the workload is the
  same).
- `bootstate.py` records each boot (boot id, mitigation state, command line, microcode, frequency and
  idle-state setup, a few sysctls) and the chain refuses to run when the mitigation state is not the
  expected one, when anything else differs from block A, or when no reboot happened.
- **Warning:** `oneshot-boot.sh` changes the boot loader and can boot the machine with the CPU-vulnerability
  mitigations off. Use it only on a dedicated, isolated bench machine with console access, read its
  `entries` output before `install`, and `remove` the entries afterwards.
- `oneshot-boot.sh` (run by the operator, as root) adds two GRUB entries that copy the default entry,
  one with `mitigations=off`, and selects one for the next boot only (`grub-reboot`). GRUB clears the
  choice before the kernel starts, so any later boot, a power cycle included, is the default one.

## Runs

| Config | Arms | Shapes |
|---|---|---|
| `h-pl.json` | `base`, `base-A2` | `s` (4 KB proxied, 5,200 req/s), `fh` (direct response, 57 + 52 headers, 8,000 req/s) |
| `h-c1.json` | `ka` (keep-alive), `ka-A2`, `c1` (one request per connection, 16 loopback addresses) | `s` at 1,600 req/s (wave 3's churn rig, its `e-plain` arms) |
| `h-spec.json` | `base`, `ssbd` (`spec_ctrl: {store_bypass: disable}`), `ibp` (`spec_ctrl: {indirect_branch: disable}`) | `s` at 5,200 req/s |
| `h-defer-deep.json` | `c1`, `c1-A2`, `c1-defer` (`TCP_DEFER_ACCEPT` 1 s), default idle states | `s` at 1,600 req/s |
| `h-defer-c1only.json` | the same, with C1E and C6 disabled on Envoy's CPUs and their SMT siblings for the run | `s` at 1,600 req/s |

Every run: Williams order, 6 rounds, one unscored warm-up leg of the base arm before each shape block,
and a one-round smoke from which the evidence is frozen. The idle check matches no process by its
command line.

## Harness additions (generic, off unless a config uses them)

- `arms[].spec_ctrl`: per-task speculation control, applied with prctl in the child before exec (Envoy
  and its threads inherit it); a refused prctl stops the leg. Every leg records the state of every Envoy
  thread from `/proc/<pid>/task/*/status` (`envoy_speculation`), which the `h-spec` evidence checks.
- Run metadata: the boot id, `/sys/devices/system/cpu/vulnerabilities`, the mitigation arguments of the
  kernel command line and the microcode revision (`sysprobe.boot_state`).

## Files

- `make.py` writes the configs; `run-h.sh smoke|check|queue RUN`, `chain-h.sh` (`H_BLOCK=H0|A|B|C`;
  `H_DRY=1` simulates every leg off the bench box), `box-start.sh`: the sessions.
- `bootstate.py record|check`: the boot state, read only.
- `cstate.sh show|pin|restore`: the idle states of the `h-defer-c1only` run (needs `sudo -n`).
- `oneshot-boot.sh entries|install|next|status|remove`: the one-shot boot entries (operator, as root).
- `table.py block|cross|defer`: the tables and the decision rules fixed before the runs.
