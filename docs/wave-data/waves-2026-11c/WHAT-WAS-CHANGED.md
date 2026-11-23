# Waves 5 and 6 data: what was changed in the raw records before publication

The archives hold the records as the harness and the build and profile chains wrote them, with the changes
listed here. No measured value was changed: every change is inside a text string. The changes were made with
`epl scrub --publish` (`epl/pubscrub.py`) and checked with its `--check` mode, which
`tools/build-wave-data.py` runs again before it writes an archive.

## Left out

- **Binaries and binary profiles**: no Envoy or Nighthawk binary is published. The arm64 own builds, the
  split-DWARF file, the instrumented-PGO profile, the AutoFDO profiles (`envoy.afdo`, `envoy2.afdo`) and the
  BOLT profile (`merged.fdata`) are left out (3 files that were in the data directories; the binaries were kept
  apart from them). Their sha256 are in `arm-vm-layout/I-bins.SHA256SUMS` and
  `arm-metal-layout/J-bins.SHA256SUMS` (added for the publication from the build records) and in the
  example directories' `bins.json`.
- **Raw perf and SPE samples**: none were in the data directories (they stayed on the machines that recorded
  them and were deleted with them).
- **Eight packed copies** (`A.tgz`, `B.tgz`, `C.tgz`, `D.tgz` of both mitigation studies) of block directories
  that are published unpacked.
- **The host's package-install log** of the bare-metal Arm machine (`w6j/logs/apt.log`): no table reads it.
- **The setup and chain scripts** of the bare-metal Arm machine: they are in the repository, cleaned and with
  parameters, as `tools/code-layout/arm/`.

## What was changed

135 of the published files differ from the files the runs wrote.

- **Home directory prefixes** are written `~` (569 places in 58 files).
- **The kernel release of the two cloud VMs** is written `7.0.0-1017-cloud`; the image's flavour suffix is
  replaced (139 places in 84 files: kernel and platform strings, the perf path, the boot image name), as in the
  stats study's data.
- **The cloud VM's instance id** in `mitigations-cloud/host-gate.txt` (the check, before every block, that the
  VM was the same instance and had not been restarted or moved) is written `<instance id>` (5 places in 1 file);
  the start times beside it are unchanged.

## Rendered again or written for the publication

- The cross-boot tables were rendered again with `examples/wave5h/table.py cross` from the records:
  `mitigations/cross.json` and `cross.md`, `mitigations-cloud/cross-plain-ABC.json` and `.md`,
  `mitigations-cloud/cross.json` and `cross-D-for-B-hpl.md`. Against the tables rendered when the runs were
  analysed, only labels differ: the price-list verdict line carried an internal item number (now "the
  mitigations as a price-list row"), block D's directory is named `D` instead of a full path, and the table code
  of the first run did not yet write the `pl_off` field. Every number and verdict is the same.
- `mitigations/H0-defer.json` is as rendered when the run was analysed; `mitigations/H0-defer.md` (the printed
  table) was written for the publication.
- `arm-vm-layout/analysis-w5i.md` and `arm-metal-layout/analysis-w6j.md` are as rendered when the runs were
  analysed; the scripts of the repository render them again byte for byte.

## Commit ids

The records name the harness commits that were measured, left as recorded; see
`docs/wave-data/harness-commit-map.md`.
