#!/bin/bash
# Pack the harness tree for the bench box: git archive of HEAD plus HARNESS_COMMIT (the box tree is not a git
# checkout, so the run metadata cannot name the commit otherwise).   [PACK_NAME=harness-wave2] pack.sh OUT.tgz
set -eu
OUT=${1:?OUT.tgz}
H=$(cd "$(dirname "$0")/../.." && pwd)
[ -z "$(git -C "$H" status --porcelain)" ] || { echo "uncommitted changes; commit first" >&2; exit 1; }
N=${PACK_NAME:-harness-wave2}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
git -C "$H" archive --prefix="$N/" HEAD | tar -x -C "$T"
git -C "$H" rev-parse HEAD > "$T/$N/HARNESS_COMMIT"
# the harness reports a VERSION file when there is one (experiment.harness_version), so the run metadata names the commit
V=$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import epl; print(epl.__version__)' "$H")
echo "$V $(git -C "$H" rev-parse --short=12 HEAD) (archive)" > "$T/$N/VERSION"
COPYFILE_DISABLE=1 tar --no-xattrs -czf "$OUT" -C "$T" "$N" 2>/dev/null || COPYFILE_DISABLE=1 tar -czf "$OUT" -C "$T" "$N"
echo "$OUT: $(cat "$T/$N/HARNESS_COMMIT")"
