#!/usr/bin/env bash
set -Eeuo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a42-fullgraph.sh"; rewriter="${script_dir}/rewrite-q38-a42-to-a43-fullgraph.py"; wrapper="${script_dir}/launch-tp4-mtp0-4352-ple-only-a43-fullgraph.sh"; client="${script_dir}/run-tp4-mtp0-4352-ple-only-a43-fullgraph-client.sh"
expected_base=10c7d2e1295b1eb12b76593fdb92cef15a773ab8f24512dda3d0b7763f9db68e; expected_rewriter=648555d26b137f6a8d064f09b2e682e2d71169442396bab3cea9902c1a621782; expected_wrapper=f61eb6bd3bc92c64d938d24c0038bf06f543ab89f60104dc34b8d9286b97118b; expected_client=2fc3d2e1ddfb8428a90aee45a8b7889011c1275737a507d4cbe3f1fc96019a73; expected_source=5a4e482fca19059f5f4dfaeaf2b607ed11b835a33c80e53d909212288df7b268
derive() { Q38_A42_SOURCE_ONLY=1 "$base" | python3 "$rewriter" supervisor --wrapper-hash "$expected_wrapper" --client-hash "$expected_client"; }
[[ $# == 0 ]]; [[ "$(sha256sum "$base"|cut -d' ' -f1)" == "$expected_base" ]]; [[ "$(sha256sum "$rewriter"|cut -d' ' -f1)" == "$expected_rewriter" ]]; [[ "$(sha256sum "$wrapper"|cut -d' ' -f1)" == "$expected_wrapper" ]]; [[ "$(sha256sum "$client"|cut -d' ' -f1)" == "$expected_client" ]]; [[ "$(derive|sha256sum|cut -d' ' -f1)" == "$expected_source" ]]
if [[ "${Q38_A43_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
