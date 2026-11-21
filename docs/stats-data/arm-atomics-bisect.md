# Arm atomics in Envoy's arm64 builds: where the code generation changed

What is here: the counts and the method. No raw files were kept (the images were removed after each
count), so this table is the record. Every binary in it is an upstream artefact (a dev image is
identified by its tag only), so the counts can be taken again.

## Method

Per aarch64 `envoy` binary: the number of exclusive-pair instructions in its disassembly, counted
per mnemonic with `llvm-objdump -d` (`ldaxr`, `ldxr`, `stlxr`, `stxr`). Release binaries are the
release assets. Builds of `main` are the official dev images of that commit (linux/arm64), pulled by
commit, the binary extracted, the image deleted. The image labels carry no revision, so the tag is
trusted as the build of that commit.

The command, per binary (any `llvm-objdump` that disassembles aarch64; the byte and half-word forms
are folded into their base mnemonic):

```
llvm-objdump -d --no-show-raw-insn BINARY | awk '{print $2}' \
  | grep -E '^(ldadd|ldaddal|ldaddl|ldadda|ldclr|ldset|swp|cas|casal|ldxr|ldaxr|stxr|stlxr)' \
  | sed -E 's/(b|h)$//' | sort | uniq -c
```

Range covered: the merge base of v1.40.0 and `main` (`9e5580933739`, 2026-10-13) to `5e1439980a`
(2026-11-17), 654 commits; commits without a dev image were skipped.

## Counts

| Binary | ldaxr | ldxr | stlxr | stxr | Form |
|---|---|---|---|---|---|
| release v1.39.0, v1.40.0 | 84 | 28 | 86 | 26 | out-of-line helpers (about 110 pairs; v1.40.2 the same order) |
| `main` at `2a39ecbfa9` (parent of step 1) | 84 | 28 | 86 | 26 | out-of-line |
| `main` at `7ffbe9cc49` (2026-10-24), step 1 | 1122 | 1335 | 1147 | 1310 | about 2.5k inline pairs |
| `main` at `28491e9130` (parent of step 2) | as step 1 | | | | |
| `main` at `06e236175a` (2026-10-26), step 2 | 28904 | 15507 | 28773 | 15638 | about 45k inline pairs |
| `main` at `5e1439980a` (2026-11-17) | 29324 | 15693 | 29193 | 15824 | about 45k inline pairs |

## What is measured and what is inferred

- Measured: the counts above, and that neither step is an ancestor of v1.40.2 (`git merge-base
  --is-ancestor`). From that ancestry, not from a count of every release: no 1.40.x release carries
  the inline form, and it is in no release up to v1.40.2.
- Inferred from reading the build files and the compiler source, not confirmed by a compiler
  invocation log: both steps come from compiling aarch64 code against a sysroot without a GCC
  installation, where clang's default for outline atomics is off and it emits inline exclusive pairs
  for the ARMv8.0 baseline. No `-march`, `-mcpu` or `-mno-outline-atomics` flag is involved.
- Inferred, not verified on the archive itself: step 1's pairs are in a prebuilt dependency that was
  rebuilt in that step.
- The controlled pair of builds that isolates the instruction form (one source, two flag sets) is in
  the data archive `arm-lse-llsc`; the end-to-end comparison of the release against a `main` image is
  in the archive `arm-codegen` (`python3 tools/fetch-stats-data.py arm-lse-llsc arm-codegen`).
