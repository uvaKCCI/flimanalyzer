#!/usr/bin/env bash
# The version for an image's labels: docker/metadata-action's version output without
# the variant's tag suffix (e.g. 0.6.1-cpu -> 0.6.1; the tag stays 0.6.1-cpu).
#   image-version.sh METADATA_VERSION [SUFFIX]
set -euo pipefail
version=$1 suffix=${2:-}
echo "${version%"$suffix"}"
