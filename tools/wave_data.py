"""The data of the wave studies (waves 1 to 8 and the code-layout work) as release assets: shared
pieces of build-wave-data.py and fetch-wave-data.py. Four releases: waves-2026-11 (waves 1 to 3, code
layout), waves-2026-11b (wave 4, HTTP/3), waves-2026-11c (waves 5 and 6) and waves-2026-11d (waves 7 and 8).

The raw records of these studies (about 2.3 GB unpacked) are not in git. They are published as one
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

TAG = "waves-2026-11"           # the first release: waves 1 to 3 and the code-layout work
TAG_B = "waves-2026-11b"        # the second release: wave 4 (HTTP/3)
TAG_C = "waves-2026-11c"        # the third release: waves 5 and 6 (mitigations, arm64 code layout)
TAG_D = "waves-2026-11d"        # the fourth release: waves 7 and 8 (second hop, feature stack, patch experiments)
RELEASE_URL = "https://github.com/We-Amp/envoy-price-list/releases/download/%s/"
BASE_URL = RELEASE_URL % TAG
ASSET = TAG + "-data-%s.tar.gz"

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO, "data", "wave-data.manifest")
# from the third release on, one manifest file per study (data/wave-data-<tag>-<study>.manifest), so that no
# file in git grows past 1 MB
SUMS = os.path.join(REPO, "data", "wave-data.SHA256SUMS")
DEST = os.path.join(REPO, "data", "waves")
# files of the repository that go into every archive, at its top level
TOP_FILES = [("docs/wave-data/README.md", "README.md"),
             ("docs/wave-data/WHAT-WAS-CHANGED.md", "WHAT-WAS-CHANGED.md")]
# per release: the archives of a published release must not change, so a later release brings its own
# README and WHAT-WAS-CHANGED, inside its study's directory (so that they never overwrite the first
# release's files at the top of data/waves/)
TOP_FILES_OF = {TAG: TOP_FILES,
                TAG_B: [("docs/wave-data/http3/README.md", "http3/README.md"),
                        ("docs/wave-data/http3/WHAT-WAS-CHANGED.md", "http3/WHAT-WAS-CHANGED.md")],
                # one README and one WHAT-WAS-CHANGED for the release, in each of its studies' directories
                TAG_C: [("docs/wave-data/waves-2026-11c/README.md", "{study}/README.md"),
                        ("docs/wave-data/waves-2026-11c/WHAT-WAS-CHANGED.md", "{study}/WHAT-WAS-CHANGED.md")],
                TAG_D: [("docs/wave-data/waves-2026-11d/README.md", "{study}/README.md"),
                        ("docs/wave-data/waves-2026-11d/WHAT-WAS-CHANGED.md", "{study}/WHAT-WAS-CHANGED.md")]}
# the machine label of the bench box that most studies ran on
HOST_LABEL = "bench-x86_64"
# the studies that ran elsewhere carry their own machine label
HOST_LABEL_OF = {"mitigations-cloud": "cloud-vm-x86", "arm-vm-layout": "arm-vm", "arm-metal-layout": "arm-metal"}

# study directory -> (wave, what it prices, the example directory of its configs and scripts)
STUDIES = {
    "statsd-batching": ("1", "statsd datagram batching and the header-validation ceiling", "examples/wave1-b"),
    "ext-proc-xds": ("1", "ext_proc filter and xDS updates", "examples/wave1c"),
    "topdown": ("1", "top-down and code-footprint counters, official binary against PGO + ThinLTO",
                "examples/topdown"),
    "code-layout": ("2", "code layout: call-graph order, AutoFDO, PGO + ThinLTO, BOLT", "examples/wave2"),
    "connection-churn": ("3", "connection churn, TLS handshakes, listener accept settings", "examples/wave3e"),
    "upstream-protocols": ("3", "HTTP/2, gRPC and TLS upstreams, mTLS between hops", "examples/wave3f"),
    "http3": ("4", "HTTP/3 (QUIC) against HTTP/2 over TLS: per request, GSO, per connection, resumption",
              "examples/wave4g"),
    "mitigations": ("5", "the kernel's CPU-vulnerability mitigations across boots, prctl arms, TCP_DEFER_ACCEPT and idle states",
                    "examples/wave5h"),
    "arm-vm-layout": ("5", "code layout on arm64 in a cloud VM: ordering file, PGO + ThinLTO, -mcpu", "examples/wave5i"),
    "arm-metal-layout": ("6", "code layout on arm64 bare metal: SPE AutoFDO and BOLT, file control", "examples/wave6j"),
    "mitigations-cloud": ("6", "the mitigation price on a current x86 CPU in a cloud VM", "examples/wave6k"),
    "second-hop": ("7", "a second proxy hop: HTTP against a TCP relay, Unix sockets between hops", "examples/wave7s1"),
    "bodies-streams": ("7", "chunked bodies, streamed events, a buffer limit, HTTP/3 at 0 B and 4 KB",
                       "examples/wave7s2"),
    "feature-stack": ("7", "a typical feature stack against the lean config, ten inert filters, idle timers",
                      "examples/wave7s3"),
    "tracing-tests-profile": ("7", "a deferred tracing span at 0% sampling; PGO trained on Envoy's own tests",
                              "examples/wave7s4"),
    "tests-profile-integration": ("7", "PGO trained on Envoy's integration tests alone", "examples/wave7s4b"),
    "relay-syscalls": ("7", "two empty kernel calls per relayed message removed (an experiment patch)",
                       "examples/wave7s5"),
    "chunked-copy": ("8", "an HTTP/1 chunked body as fragments instead of a copy (an experiment patch)",
                     "examples/wave8w1"),
    "http3-receive": ("8", "the HTTP/3 receive path: stop guard and buffer reuse, server retransmission counts",
                      "examples/wave8w2"),
}
# the release each study's archive belongs to (default: the first one)
TAG_OF = {"http3": TAG_B, "mitigations": TAG_C, "arm-vm-layout": TAG_C, "arm-metal-layout": TAG_C,
          "mitigations-cloud": TAG_C}
TAG_OF.update((s, TAG_D) for s, v in STUDIES.items() if v[0] in ("7", "8"))


def top_files(study):
    """[(repository path, path inside the study's archive)] of the files every archive of its release carries."""
    return [(src, dst.format(study=study)) for src, dst in TOP_FILES_OF[tag_of(study)]]


def tag_of(study):
    return TAG_OF.get(study, TAG)


def asset(study):
    """The asset file name of a study's archive: <tag>-data-<study>.tar.gz."""
    return tag_of(study) + "-data-%s.tar.gz" % study


def base_url(study):
    return RELEASE_URL % tag_of(study)

# files that are not text but are published: request and response bodies the harness writes for
# the gRPC shapes (a few bytes of protobuf framing), named by their path inside the study
BINARY_OK = ("/origin/www/_authz/", "/origin/www/_grpc/")


def manifest_of(study):
    """The manifest file that lists a study's archive."""
    tag = tag_of(study)
    if tag in (TAG, TAG_B):
        return MANIFEST
    return os.path.join(REPO, "data", "wave-data-%s-%s.manifest" % (tag, study))


def manifests():
    return sorted({manifest_of(s) for s in STUDIES})


def read_manifest(path=None):
    """[(sha256, size, study, path)] of one manifest file, or of every release's when path is None."""
    if path is not None:
        return _read_manifest(path)
    return [m for p in manifests() for m in _read_manifest(p)]


def read_sums(path=SUMS):
    return _read_sums(path)
