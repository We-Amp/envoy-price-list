# Wasm filters for row 16

Two HTTP filters written in Rust with the `proxy-wasm` crate (0.2.2), built for
`wasm32-wasip1` and run by Envoy's V8 runtime (`envoy.wasm.runtime.v8`), one VM per
worker, loaded from a local file:

- `empty/`: every per-request SDK callback present, each returns Continue. The VM is
  entered for context creation, request headers, request body, request trailers,
  response headers, each response body chunk, response trailers, log and done. This is
  the runtime's minimum per-request cost, not the same work as the empty Lua script.
- `header/`: reads `:path` and adds `x-epl-filter: 1` to the request; adds
  `x-epl-filter: 1` to the response. The same job as the Lua header script.

Build (Docker, network for the crates; nothing else is installed):

    bash examples/settings-matrix/features2/wasm/build.sh

It runs `cargo build --release --locked --target wasm32-wasip1` in the pinned image
named in `build.sh` and `TOOLCHAIN` (by digest, with a fixed `--platform`), with source
paths remapped, and writes `out/*.wasm`, `SHA256SUMS`, `TOOLCHAIN` and `licenses/`.
Two builds in a row give the same digests. `Cargo.lock` pins every crate.

The harness carries each module's sha256 in the arm's `wasm` setting and checks the file
against it at the start and at the end of every run.

Licences: the modules link the Rust standard library and the crates in `Cargo.lock`;
their licence texts are in `licenses/` (Rust: MIT or Apache-2.0; proxy-wasm: Apache-2.0;
the other crates: MIT or Apache-2.0, zerocopy also BSD-2-Clause). The source here is
Apache-2.0, as the rest of the repository.
