#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: $0 [--publish]"
  echo "  Default:   Build and load coppit/xeoma-test locally."
  echo "  --publish: Build and push coppit/xeoma to Docker Hub."
}

if (( $# > 1 )); then
  usage >&2
  exit 1
fi

case "${1-}" in
  '')
    docker buildx build --platform linux/amd64 --load -t coppit/xeoma:local .
    ;;
  --publish)
    docker buildx build --platform linux/amd64 --push -t coppit/xeoma .
    ;;
  -h|--help)
    usage
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
