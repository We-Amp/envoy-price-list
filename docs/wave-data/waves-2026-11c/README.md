# Waves 5 and 6 data: the raw records

The raw records of waves 5 and 6 of the Envoy price list, one archive per study, assets of the release of
tag `waves-2026-11c` of https://github.com/We-Amp/envoy-price-list. `python3 tools/fetch-wave-data.py
--tag waves-2026-11c` in that repository downloads them, checks each archive and every file against the
manifest in git, and unpacks them into `data/waves/<study>/`. This file and `WHAT-WAS-CHANGED.md` are in
each study's directory of this release (the first release's files of the same names are at the top of
`data/waves/`).

Run directories have the layout of the first wave release (`docs/wave-data/README.md`). The conditions of
each study are in its example directory; the commands that render every table are in
`docs/wave-studies.md`.

| Archive (`waves-2026-11c-data-<study>.tar.gz`) | Wave | Configs | Machine (label in the records) | Contents |
|---|---|---|---|---|
| `mitigations` | 5 | `examples/wave5h` | the two-socket Xeon E5-2673 v4 bench box (`bench-x86_64`) | blocks `H0` (TCP_DEFER_ACCEPT against idle states: `h-defer-deep`, `h-defer-c1only`), `A` (mitigations on), `B` (`mitigations=off`), `C` (on): `h-pl`, `h-c1`, and `h-spec` in C; `bootstate-*.json` (boot id, mitigation state, command line, microcode per block); `grub-install.txt`, `grub-remove.txt` (what the one-shot boot entries changed); tables `cross.md`/`cross.json`, `H0-defer.md`/`H0-defer.json` |
| `mitigations-cloud` | 6 | `examples/wave6k` | a current Intel server CPU in a cloud VM (`cloud-vm-x86`) | blocks `A`, `B`, `C` and `D` (a second off boot, `h-pl` only); `bootstate-*.json`, `boot-*.txt`, `grub-install.txt`, `boot-final-and-remove.txt`, `host-gate.txt`; tables `cross-plain-ABC.md`/`.json` (A-B-C as planned), `cross-D-for-B-hpl.md` and `cross.json` (D's `h-pl` in place of B's) |
| `arm-vm-layout` | 5 | `examples/wave5i` | a Neoverse V2 class core in a cloud VM, 16 vCPU (`arm-vm`) | `epl/runs/wave5i/w5i` (the A/B run) and its smoke, `epl/runs/wave5i-prof/fp-w5i` (frame-pointer profiling legs); `w5i/` (probes, build and training logs, the order profile's call-graph edges and hot set); `analysis-w5i.md` (its `order` rows are held, not confirmed: no file control ran on this host; on bare metal the control was null and the ordering file gave 4-7%; we do not quote the VM figure as a result); `I-bins.SHA256SUMS` |
| `arm-metal-layout` | 6 | `examples/wave6j` | a Neoverse N3 core, bare metal, 96 cores (`arm-metal`) | `epl/runs/wave6j/w6j` (the 7-arm A/B run) and its smoke, `chain-prof.log` of the SPE profiling session (its legs' records and samples are not in this archive); `w6j/` (probe, build and profile logs); `analysis-w6j.md`; `J-bins.SHA256SUMS` |

## Binaries

The official Envoy v1.40.2 release assets (x86-64 sha256 `1d64506e…f03cc`, arm64 `b9d6d1e0…213baf`) and
own builds of tag v1.40.2 for arm64. No binary and no binary profile (`.afdo`, `.fdata`, `.profdata`) is in these archives; their sha256 are in
`I-bins.SHA256SUMS`, `J-bins.SHA256SUMS`, the example directories' `bins.json` and the records. The build
scripts are `tools/code-layout/arm`.

`metadata.harness` in each run's `results.json` is the measured harness commit;
`docs/wave-data/harness-commit-map.md` says where that code is in the published history.
