#!/bin/bash
# Build the ext_proc test service (epl-extproc) for linux/amd64, reproducibly, in a pinned Go
# image, after its unit tests pass.
#
#   bash tools/extproc/build.sh
#
# Go standard library only (no modules to fetch). Static (CGO_ENABLED=0), -trimpath, no build
# id, no VCS stamp, so two builds give the same digest. Writes out/epl-extproc-linux-amd64,
# SHA256SUMS and TOOLCHAIN. out/ is not tracked: copy the binary to the bench box with the
# harness tree; the harness checks its sha256 (origin.ext_proc_sha256 in the config, from
# SHA256SUMS) before it starts the service, and refuses to run on a mismatch. Needs Docker.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
IMAGE=${IMAGE:-golang:1.27.4-alpine@sha256:70bd7ddea8b6cbe5d6943cde279d6b67feb10cc924fb9100d1d8757c1575b280}
PLATFORM=${PLATFORM:-linux/arm64}
docker run --rm --platform "$PLATFORM" --network none -e IMAGE="$IMAGE" -e PLATFORM="$PLATFORM" \
  -e GOFLAGS=-mod=mod -e GOCACHE=/tmp/gocache -e GOTOOLCHAIN=local \
  -v "$HERE":/src -w /src "$IMAGE" sh -euc '
    CGO_ENABLED=0 go vet ./...
    CGO_ENABLED=0 go test -count=1 ./...
    mkdir -p out
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -buildvcs=false -ldflags="-s -w -buildid=" \
      -o out/epl-extproc-linux-amd64 .
    (cd out && sha256sum epl-extproc-linux-amd64) > SHA256SUMS
    { go version; echo "image $IMAGE"; echo "platform $PLATFORM"; echo "target linux/amd64";
      echo "command: CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -buildvcs=false -ldflags=\"-s -w -buildid=\""; } > TOOLCHAIN
  '
cat "$HERE/SHA256SUMS"
