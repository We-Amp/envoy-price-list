# Stats study data: the release assets

Assets of the release of tag `stats-2026-11` (`https://github.com/We-Amp/envoy-price-list/releases/download/stats-2026-11/<asset>`), written by
`tools/build-stats-data.py`. `python3 tools/fetch-stats-data.py` downloads, checks and unpacks them.

| Asset | Size | Files | Unpacked | sha256 |
|---|---|---|---|---|
| `stats-2026-11-data-arm-codegen.tar.gz` | 3.5 MB | 488 | 14.4 MB | `a0bda86aad1ea82b8f97043dc4a9ec57a3688c1b8f6a4003d354550527dc770b` |
| `stats-2026-11-data-arm-lse-llsc.tar.gz` | 1.0 MB | 54 | 9.7 MB | `19b3e29bb5a4a28a18cbd208a7cc32a6c352fd9e830a47366430fde8b5dbf94e` |
| `stats-2026-11-data-contention.tar.gz` | 8.5 MB | 375 | 24.6 MB | `6269e8075a33141b003cd297ddb812d9c110e5f0d9117d00994f500d483fba54` |
| `stats-2026-11-data-flush-latency.tar.gz` | 80.1 MB | 337 | 93.9 MB | `07063f6a0bfdfc958bf380e69f6dbc2a6adbb06a2881bfeb8dd6d5f2c7964a7d` |
| `stats-2026-11-data-microbenchmarks.tar.gz` | 3.1 MB | 237 | 30.1 MB | `3725342d19774b0554d54db04e0e09196fbd04cb65945a74ee0a178342517fa0` |
| `stats-2026-11-data-microbenchmarks-flush-overlap.tar.gz` | 0.7 MB | 57 | 8.5 MB | `d2ffb642d8d0c39e11ff11464cdc4d23c80592ae4f8959c2cb09a542cde49461` |
| `stats-2026-11-data-multi-worker.tar.gz` | 10.5 MB | 627 | 30.9 MB | `412b8d0d046c6e7aeb1c1d9b7a744cbbfb492f77d626ab4b490d7123f7f218ef` |
| `stats-2026-11-data-multi-worker-high-load.tar.gz` | 10.1 MB | 388 | 28.9 MB | `c20fb877019c13f4d807ec579c309021b6fe66f018805af6b47001ebd514a8b2` |
| `stats-2026-11-data-sink-flush-cost.tar.gz` | 23.5 MB | 1040 | 43.8 MB | `dfe3b5561d661303cb58d3a34cc96fdafdd8347edb4db72d03bb3d04808512e1` |
| `stats-2026-11-data-sink-types.tar.gz` | 18.8 MB | 784 | 37.3 MB | `0de7c01127b9f56fd203ce05fd0511437b5ad3650bd0318d758ebc4828b64e0d` |

Together: 160 MB to download, 322 MB unpacked, 4387 files (two of them, `README.md` and
`WHAT-WAS-CHANGED.md`, are in every archive). The same checksums are in `data/stats-data.SHA256SUMS`;
every file of every archive is in `data/stats-data.manifest` with its size and sha256.
