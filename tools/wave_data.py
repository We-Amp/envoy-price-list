"""The data of the wave studies (waves 1 to 3 and the code-layout work) as release assets: shared
pieces of build-wave-data.py and fetch-wave-data.py.

The raw records of these studies (about 570 MB unpacked) are not in git. They are published as one
gzip-compressed tar archive per study on the release of the tag below, in the same form as the
stats study's data (tools/stats_data.py, whose archive and list helpers are used here). Git keeps
the manifest (every file of every archive with its size and SHA-256) and the checksums of the
archives.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stats_data import read_manifest as _read_manifest  # noqa: E402
from stats_data import read_sums as _read_sums  # noqa: E402
from stats_data import sha256_file, tree_files, write_archive  # noqa: E402,F401

TAG = "waves-2026-11"
BASE_URL = "https://github.com/We-Amp/envoy-price-list/releases/download/%s/" % TAG
ASSET = TAG + "-data-%s.tar.gz"

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO, "data", "wave-data.manifest")
SUMS = os.path.join(REPO, "data", "wave-data.SHA256SUMS")
DEST = os.path.join(REPO, "data", "waves")
# files of the repository that go into every archive, at its top level
TOP_FILES = [("docs/wave-data/README.md", "README.md"),
             ("docs/wave-data/WHAT-WAS-CHANGED.md", "WHAT-WAS-CHANGED.md")]
# every study ran on the one bench box; its records carry this machine label
HOST_LABEL = "bench-x86_64"

# study directory -> (wave, what it prices, the example directory of its configs and scripts)
STUDIES = {
    "statsd-batching": ("1", "statsd datagram batching and the header-validation ceiling", "examples/wave1-b"),
    "ext-proc-xds": ("1", "ext_proc filter and xDS updates", "examples/wave1c"),
    "topdown": ("1", "top-down and code-footprint counters, official binary against PGO + ThinLTO",
                "examples/topdown"),
    "code-layout": ("2", "code layout: call-graph order, AutoFDO, PGO + ThinLTO, BOLT", "examples/wave2"),
    "connection-churn": ("3", "connection churn, TLS handshakes, listener accept settings", "examples/wave3e"),
    "upstream-protocols": ("3", "HTTP/2, gRPC and TLS upstreams, mTLS between hops", "examples/wave3f"),
}

# files that are not text but are published: request and response bodies the harness writes for
# the gRPC shapes (a few bytes of protobuf framing), named by their path inside the study
BINARY_OK = ("/origin/www/_authz/", "/origin/www/_grpc/")


def read_manifest(path=MANIFEST):
    return _read_manifest(path)


def read_sums(path=SUMS):
    return _read_sums(path)
