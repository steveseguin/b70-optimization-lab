#!/usr/bin/env bash
# cleanup.sh [--images]: remove every agentbench-* container (and with --images, every agentbench-* image).
set -uo pipefail
ids=$(docker ps -aq --filter name=agentbench-)
[ -n "$ids" ] && docker rm -f $ids >/dev/null && echo "removed containers: $(echo $ids | wc -w)"
if [ "${1:-}" = --images ]; then
  imgs=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep '^agentbench-')
  [ -n "$imgs" ] && docker rmi $imgs >/dev/null && echo "removed images: $(echo $imgs | wc -w)"
  docker image prune -f >/dev/null
fi
true
