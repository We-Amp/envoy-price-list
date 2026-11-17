#!/bin/bash
# Build the two Wasm filters (empty, header) for row 16, reproducibly, in a pinned Rust image.
#
#   bash examples/settings-matrix/features2/wasm/build.sh
#
# Runs `cargo build --release --locked --target wasm32-wasip1` in the image below (pinned
# by digest, platform fixed), with paths remapped so the output does not depend on where
# the repo or the cargo home sit. Writes out/epl_wasm_empty.wasm, out/epl_wasm_header.wasm,
# SHA256SUMS, TOOLCHAIN (rustc and cargo versions, image, platform) and the licence
# texts of the Rust standard library and of every crate in Cargo.lock under licenses/.
# The harness checks each module's sha256 (from SHA256SUMS, carried in the config) at the
# start and at the end of every run. Needs Docker and network access for the crates.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
IMAGE=${IMAGE:-rust:1.84.1-slim-bookworm@sha256:69fbd6ab81b514580bc14f35323fecb09feba9e74c5944ece9a70d9a2a369df0}
PLATFORM=${PLATFORM:-linux/arm64}
TARGET=wasm32-wasip1
docker run --rm --platform "$PLATFORM" --cpus 4 --network bridge \
  -e CARGO_HOME=/cargo -e IMAGE="$IMAGE" -e PLATFORM="$PLATFORM" -e TARGET="$TARGET" \
  -e SOURCE_DATE_EPOCH=0 \
  -v "$HERE":/src -w /src "$IMAGE" bash -euo pipefail -c '
    rustup target add "$TARGET" >/dev/null
    [ -f Cargo.lock ] || cargo generate-lockfile
    export RUSTFLAGS="--remap-path-prefix=/src=/build --remap-path-prefix=/cargo=/cargo-home"
    cargo build --release --locked --target "$TARGET" --target-dir /tmp/target
    mkdir -p out
    for m in empty header; do cp /tmp/target/"$TARGET"/release/epl_wasm_$m.wasm out/; done
    (cd out && sha256sum epl_wasm_empty.wasm epl_wasm_header.wasm) > SHA256SUMS
    { rustc --version; cargo --version; echo "target $TARGET"; echo "image $IMAGE"; echo "platform $PLATFORM";
      echo "RUSTFLAGS $RUSTFLAGS"; echo "command: cargo build --release --locked --target $TARGET"; } > TOOLCHAIN
    rm -rf licenses && mkdir -p licenses/rust-std
    sysroot=$(rustc --print sysroot)
    for f in LICENSE-APACHE LICENSE-MIT COPYRIGHT; do
      p=$(find "$sysroot" /usr/local/rustup -name "$f" -path "*doc*" 2>/dev/null | head -1 || true)
      [ -n "$p" ] && cp "$p" licenses/rust-std/
    done
    awk "/^name = /{n=\$3} /^version = /{v=\$3; gsub(/\"/,\"\",n); gsub(/\"/,\"\",v); print n\"-\"v}" Cargo.lock |
    while read -r crate; do
      case "$crate" in epl-wasm-*) continue;; esac
      d=$(ls -d /cargo/registry/src/*/"$crate" 2>/dev/null | head -1 || true)
      [ -n "$d" ] || continue
      mkdir -p licenses/"$crate"
      for f in "$d"/LICENSE* "$d"/COPYRIGHT* "$d"/NOTICE*; do [ -f "$f" ] && cp "$f" licenses/"$crate"/; done
    done
  '
cat "$HERE/SHA256SUMS"
