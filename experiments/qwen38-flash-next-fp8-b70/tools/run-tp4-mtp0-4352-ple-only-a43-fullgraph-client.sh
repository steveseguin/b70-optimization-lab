#!/usr/bin/env bash
set -Eeuo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a42-fullgraph-client.sh"; rewriter="${script_dir}/rewrite-q38-a42-to-a43-fullgraph.py"; verifier="${script_dir}/verify-q38-a43-fullgraph-runtime.py"
expected_base=0d179506dfa6a9c8f66106932b327cfc12bf3f2d0af7267a9429acd626fc72ad; expected_rewriter=648555d26b137f6a8d064f09b2e682e2d71169442396bab3cea9902c1a621782; expected_verifier=c7748c0316de5cddf3366c28bea419294d51cad92ad14bad893d4c8234099888; expected_source=3c8c9df55d0a3cbeae18549b20f01a5e3eb250e87183d2e022f3c2664071ef5b
derive() { Q38_A42_SOURCE_ONLY=1 "$base" | python3 "$rewriter" client --verifier-hash "$expected_verifier"; }
[[ $# == 0 ]]; [[ "$(sha256sum "$base"|cut -d' ' -f1)" == "$expected_base" ]]; [[ "$(sha256sum "$rewriter"|cut -d' ' -f1)" == "$expected_rewriter" ]]; [[ "$(sha256sum "$verifier"|cut -d' ' -f1)" == "$expected_verifier" ]]; [[ "$(derive|sha256sum|cut -d' ' -f1)" == "$expected_source" ]]
if [[ "${Q38_A43_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
