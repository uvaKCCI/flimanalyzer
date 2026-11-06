#!/usr/bin/env bash
# Checks a built batch image before it is published:
#   check-image.sh IMAGE REVISION [VERSION]
# FLIMAnalyzer inside is built from REVISION from a clean tree (and is VERSION, for
# releases), the labels say the same, and flimbatch starts.
set -euo pipefail
image=$1 revision=$2 version=${3:-}

label() { docker inspect -f "{{ index .Config.Labels \"org.opencontainers.image.$1\" }}" "$image"; }
read -r v commit dirty < <(docker run --rm --entrypoint python "$image" -c \
    'from flim import _version as v; print(v.__version__, v.__git_commit__, v.__dirty__)')
echo "image: version $v, commit $commit, dirty $dirty; labels: version $(label version), revision $(label revision)"

fail=0
[[ $dirty == False ]] || { echo "built from a dirty tree"; fail=1; }
[[ $commit == "$revision" ]] || { echo "built from $commit, not $revision"; fail=1; }
[[ $(label revision) == "$revision" ]] || { echo "revision label is not $revision"; fail=1; }
if [[ -n $version ]]; then
    [[ $v == "$version" ]] || { echo "version $v is not $version"; fail=1; }
    [[ $(label version) == "$version" ]] || { echo "version label is not $version"; fail=1; }
fi
docker run --rm "$image" --help > /dev/null || { echo "flimbatch --help failed"; fail=1; }
exit $fail
