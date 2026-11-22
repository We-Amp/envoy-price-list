# Wave 4 (HTTP/3) data: the raw records

The raw records of track G of the Envoy price list: HTTP/3 (QUIC) against HTTP/2 over TLS on Envoy
v1.40.2. One archive, `waves-2026-11b-data-http3.tar.gz`, an asset of the release of tag
`waves-2026-11b` of https://github.com/We-Amp/envoy-price-list. `python3 tools/fetch-wave-data.py http3`
in that repository downloads it, checks it and every file against the manifest in git, and unpacks it into
`data/waves/http3/`. This file and `WHAT-WAS-CHANGED.md` sit in that directory (the first wave release's
files of the same names are at the top of `data/waves/`).

The bench box, run directory layout and method are those of the first wave release
(`docs/wave-data/README.md`, `docs/wave-studies.md`); the conditions of this track are in
`examples/wave4g/README.md`. The records call the box `bench-x86_64`.

## Sessions

| Directory | Session | Runs |
|---|---|---|
| `wave4g/` | smokes of `g1-proto` and `g2-resume`, then `g1-proto` | `g1-proto` (8 rounds, all 32 scored legs valid; round 2 replaced once by the harness after one invalid leg, `.rr1` legs); the `g2-resume` smoke failed its check, so `g2-resume` did not run |
| `wave4g-s/` | smoke only of `g2s-resume` (Envoy closes each connection after 10 requests) | `smoke/smoke-g2s-resume` |
| `wave4g-s2/` | smoke of `g2s-resume` and its evidence freeze, which failed on the warm-pool item | no run |
| `wave4g-s3/` | the same with the reconnect arms' warm-pool limit at 0.005 | `g2s-resume` (8 rounds) |

Also: `tables.md` in `wave4g/` and `wave4g-s3/` (rendered with `examples/wave4g/table.py`), and
`g1-worker-shares.csv`, `g2s-worker-shares.csv` (per leg: busiest and least busy worker share, the four
shares, cycles and UDP datagrams per request; extracted from `legs.jsonl` when the runs were analysed).

`metadata.harness` names the measured harness commit (`772807bfa1f5`, `3dcbe9602e1d`, `577f19528e39`);
`docs/wave-data/harness-commit-map.md` says where that code is in the published history.
