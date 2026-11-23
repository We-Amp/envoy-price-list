# Wave studies data: the release assets

Assets of the releases of tags `waves-2026-11`, `waves-2026-11b`, `waves-2026-11c` (`https://github.com/We-Amp/envoy-price-list/releases/download/<tag>/<asset>`), written by
`tools/build-wave-data.py`. `python3 tools/fetch-wave-data.py` downloads, checks and unpacks them.

| Asset | Release | Wave | Size | Files | Unpacked | sha256 |
|---|---|---|---|---|---|---|
| `waves-2026-11c-data-arm-metal-layout.tar.gz` | `waves-2026-11c` | 6 | 13.2 MB | 1776 | 130.3 MB | `49ad4c28f0b1bbc10faaf3b9d2706d1f3a3ea3fc4e47724233fd46c19e582452` |
| `waves-2026-11c-data-arm-vm-layout.tar.gz` | `waves-2026-11c` | 5 | 9.2 MB | 1255 | 87.0 MB | `9ed5e88d8b223ceda69331af1f3bcf0df4a648fccd22b12d6289a9cdb89caa85` |
| `waves-2026-11-data-code-layout.tar.gz` | `waves-2026-11` | 2 | 11.0 MB | 1160 | 124.8 MB | `a5e56f6209a59e7bfa106b525bb7c4a9d9c3d04406c264f36a6d98ebcfa893f7` |
| `waves-2026-11-data-connection-churn.tar.gz` | `waves-2026-11` | 3 | 5.7 MB | 982 | 84.0 MB | `9f6d79dbe6e03fe8563901e53374142c57f7196aa03a744cdfb7c3016758ff79` |
| `waves-2026-11-data-ext-proc-xds.tar.gz` | `waves-2026-11` | 1 | 8.3 MB | 858 | 80.0 MB | `257b7b4bcf86815324e85c0110e15a0527f81e6d0d0c7887c2b8015be99f0ee5` |
| `waves-2026-11b-data-http3.tar.gz` | `waves-2026-11b` | 4 | 4.7 MB | 785 | 63.5 MB | `f422feb18ecf5265588d2a9c0703d9925e0e3e2a489841457bec6fe9f28590d2` |
| `waves-2026-11c-data-mitigations.tar.gz` | `waves-2026-11c` | 5 | 15.8 MB | 2023 | 191.7 MB | `f84fdbbe6ad42fa42fcba40f37c5d654fe29db82d2d71300bf6fd1987180934a` |
| `waves-2026-11c-data-mitigations-cloud.tar.gz` | `waves-2026-11c` | 6 | 14.8 MB | 1879 | 182.4 MB | `180c0fd76ccd1b1906643a2e6feee8a6df557f10dbeca0f7c6f0ba0b0e9fb3a1` |
| `waves-2026-11-data-statsd-batching.tar.gz` | `waves-2026-11` | 1 | 15.5 MB | 1010 | 107.5 MB | `16732dc00e06811e1a8aba41d443fdcf0d67e3393a4a65d89c5f1d5331f3822a` |
| `waves-2026-11-data-topdown.tar.gz` | `waves-2026-11` | 1 | 8.4 MB | 848 | 100.1 MB | `6a29af2f107f0c513912200cbe2ce60fbfa4efcd446cacc8017454e30d759199` |
| `waves-2026-11-data-upstream-protocols.tar.gz` | `waves-2026-11` | 3 | 9.0 MB | 931 | 78.8 MB | `4a585966ddd92d8bae559ab9e32e67d4c13ffee9892a79a72c45e36cb7675e7c` |

Together: 116 MB to download, 1230 MB unpacked, 13507 files (`README.md` and `WHAT-WAS-CHANGED.md`
are in every archive: at the top in those of `waves-2026-11`, in the study's directory in the later ones). The same checksums are in `data/wave-data.SHA256SUMS`;
every file of every archive is in a manifest in `data/` (`wave-data.manifest`, and one per study of the later releases)
with its size and sha256.
