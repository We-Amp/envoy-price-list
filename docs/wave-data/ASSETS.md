# Wave studies data: the release assets

Assets of the release of tag `waves-2026-11` (`https://github.com/We-Amp/envoy-price-list/releases/download/waves-2026-11/<asset>`), written by
`tools/build-wave-data.py`. `python3 tools/fetch-wave-data.py` downloads, checks and unpacks them.

| Asset | Wave | Size | Files | Unpacked | sha256 |
|---|---|---|---|---|---|
| `waves-2026-11-data-code-layout.tar.gz` | 2 | 11.0 MB | 1160 | 124.8 MB | `a5e56f6209a59e7bfa106b525bb7c4a9d9c3d04406c264f36a6d98ebcfa893f7` |
| `waves-2026-11-data-connection-churn.tar.gz` | 3 | 5.7 MB | 982 | 84.0 MB | `9f6d79dbe6e03fe8563901e53374142c57f7196aa03a744cdfb7c3016758ff79` |
| `waves-2026-11-data-ext-proc-xds.tar.gz` | 1 | 8.3 MB | 858 | 80.0 MB | `257b7b4bcf86815324e85c0110e15a0527f81e6d0d0c7887c2b8015be99f0ee5` |
| `waves-2026-11-data-statsd-batching.tar.gz` | 1 | 15.5 MB | 1010 | 107.5 MB | `16732dc00e06811e1a8aba41d443fdcf0d67e3393a4a65d89c5f1d5331f3822a` |
| `waves-2026-11-data-topdown.tar.gz` | 1 | 8.4 MB | 848 | 100.1 MB | `6a29af2f107f0c513912200cbe2ce60fbfa4efcd446cacc8017454e30d759199` |
| `waves-2026-11-data-upstream-protocols.tar.gz` | 3 | 9.0 MB | 931 | 78.8 MB | `4a585966ddd92d8bae559ab9e32e67d4c13ffee9892a79a72c45e36cb7675e7c` |

Together: 58 MB to download, 575 MB unpacked, 5789 files (two of them, `README.md` and
`WHAT-WAS-CHANGED.md`, are in every archive). The same checksums are in `data/wave-data.SHA256SUMS`;
every file of every archive is in `data/wave-data.manifest` with its size and sha256.
