# Wave 6, track K: the mitigation price on a current x86 CPU in a cloud VM

Track H's three-boot design ([`examples/wave5h`](../wave5h): the price of the kernel's CPU-vulnerability
mitigations, `mitigations=off` against the default, and the per-task prctl arms) on a 5th-generation Xeon in a
cloud VM, plus a fourth block. Data: the `mitigations-cloud` archive of the third wave release
(`python3 tools/fetch-wave-data.py mitigations-cloud`, see [`docs/wave-studies.md`](../../docs/wave-studies.md)).

## Conditions

- Box (`box-c4-32.json`): a current Intel server CPU in a cloud VM (KVM guest), 16 cores x 2 SMT, default idle
  states. Envoy on CPUs 0-3 with their SMT siblings idle; client on 4-11,20-27; origin on 12-15,28-30; the
  harness on CPU 31.
- Binary: the official `envoy-1.40.2-linux-x86_64` release asset (sha256 `1d64506e…`); Nighthawk 0.3.0.
- The runs, arms, rates, gates, rounds and warm-ups are H's (`h-pl`, `h-c1`, `h-spec`); what differs is the box,
  the Williams seeds (611, 612, 613) and a per-leg steal gate (at most 2% of the window's CPU time).
- Boot-state rule `general` (`examples/wave5h/bootstate.py --rule general`): on this CPU most vulnerability
  lines read "Not affected", so "off" means `mitigations=off` on the command line and every "Mitigation" line of
  the reference boot reading "Vulnerable".
- Blocks: A (mitigations on), B (off), C (on), and D, a second off boot that repeats only `h-pl` (added before it
  ran, after B's `h-pl` A/A failed); `table.py cross --pl-off D` uses D's `h-pl` in place of B's.
- **The cloud VM's clock is not fixed**: the host's turbo and power budget set it, and it moved by block. Read the
  cross-boot levels with the effective clock (cycles over task-clock, from each leg's record) beside them.
- The one-shot boot entries are those of `examples/wave5h/oneshot-boot.sh` (read its warning), for a cloud image
  whose entry has two kernel lines.

## Files

- `make.py [--box] [--rates]` writes `c4-32/` (`h-pl`, `h-c1`, `h-spec` and their smokes; the same files in every
  boot).
- `box-start.sh`: `K_BLOCK=A|B|C|D` starts H's block chain with K's configs, runs directory and the general rule.
- Tables: `examples/wave5h/table.py block|cross` (commands in `docs/wave-studies.md`).
