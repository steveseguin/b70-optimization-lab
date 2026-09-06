#!/usr/bin/env bash
# After pid $1 and no qwen38 container: R274b = c32 profile with GDN spec group 64 (ungrouped path); R274c = c16 profile (group 16).
S=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ -n "${1:-}" ]] && while kill -0 "$1" 2>/dev/null; do sleep 30; done
w() { while docker ps --format '{{.Names}}' | grep -q qwen38; do sleep 30; done; sleep 20; while docker ps --format '{{.Names}}' | grep -q qwen38; do sleep 30; done; }
w; SPEC_GROUP=64 CONC=32 MNS=32 RUN=r274b bash "$S/run-20260906-qwen38-int4-r274-decode-profile-c32-nostack.sh"
w; SPEC_GROUP=16 CONC=16 MNS=32 RUN=r274c bash "$S/run-20260906-qwen38-int4-r274-decode-profile-c32-nostack.sh"
