#!/usr/bin/env bash
# Chain after pid $1 and no qwen38 container: R273a (GDN spec group 64), R273b (group 1), R273c (group 16 control), then R274 (c32 profile).
S=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ -n "${1:-}" ]] && while kill -0 "$1" 2>/dev/null; do sleep 30; done
w() { while docker ps --format '{{.Names}}' | grep -q qwen38; do sleep 30; done; }
w; GDN_SPEC_GROUP=64 RUN=r273a bash "$S/run-20260906-qwen38-int4-r273-gdn-spec-group-c16-c32-ladders.sh"
w; GDN_SPEC_GROUP=1 RUN=r273b bash "$S/run-20260906-qwen38-int4-r273-gdn-spec-group-c16-c32-ladders.sh"
w; GDN_SPEC_GROUP=16 RUN=r273c bash "$S/run-20260906-qwen38-int4-r273-gdn-spec-group-c16-c32-ladders.sh"
w; bash "$S/run-20260906-qwen38-int4-r274-decode-profile-c32-nostack.sh"
