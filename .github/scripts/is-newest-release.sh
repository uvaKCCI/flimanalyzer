#!/usr/bin/env bash
# Whether a release tag is the repository's highest release version (vX.Y.Z): only
# then does its release move the images' `latest` tags, so that a release of an older
# series (e.g. 0.6.3 after 0.7.0) leaves them on the newest release.
#   is-newest-release.sh TAG    prints true or false; reads the tags with git
set -euo pipefail
tag=$1
release='^v[0-9]+\.[0-9]+\.[0-9]+$'
[[ "$tag" =~ $release ]] || { echo false; exit 0; }
newest=$(git tag -l 'v*' | grep -E "$release" | sort -V | tail -n 1)
[[ "$tag" == "$newest" ]] && echo true || echo false
