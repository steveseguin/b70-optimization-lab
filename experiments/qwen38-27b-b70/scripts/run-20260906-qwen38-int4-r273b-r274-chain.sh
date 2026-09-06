#!/usr/bin/env bash
# Requeued chain (the first one lost its group override to the sourced env file): R273b (GDN spec group 64), R273c (group 1), then R274 (c32 profile).
S=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
w() { while docker ps --format '{{.Names}}' | grep -q qwen38; do sleep 30; done; sleep 20; while docker ps --format '{{.Names}}' | grep -q qwen38; do sleep 30; done; }
w; SPEC_GROUP_OVERRIDE=64 RUN=r273b bash "$S/run-20260906-qwen38-int4-r273-gdn-spec-group-c16-c32-ladders.sh"
w; SPEC_GROUP_OVERRIDE=1 RUN=r273c bash "$S/run-20260906-qwen38-int4-r273-gdn-spec-group-c16-c32-ladders.sh"
w; bash "$S/run-20260906-qwen38-int4-r274-decode-profile-c32-nostack.sh"
