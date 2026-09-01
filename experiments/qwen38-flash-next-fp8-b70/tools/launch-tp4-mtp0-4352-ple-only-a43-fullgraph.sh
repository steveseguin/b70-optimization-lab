#!/usr/bin/env bash
set -Eeuo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a42-fullgraph.sh"; rewriter="${script_dir}/rewrite-q38-a42-to-a43-fullgraph.py"
expected_base=62f584a1dccb04f5135208b875a1c1813362f4307b3b007b629f3be7a19f340d; expected_rewriter=648555d26b137f6a8d064f09b2e682e2d71169442396bab3cea9902c1a621782; expected_derived=4f4d4160b675d933e479621e20dbcb838c8549ba6c3a65779473da944f4e7b94; expected_source=f3de9192cad32395262c84bf29b968d1b3e893bcdfa3503ec55d8baebc43ccac
derive() { Q38_A42_SOURCE_ONLY=1 "$base" | python3 "$rewriter" launcher --derived-hash "$expected_derived"; }
[[ $# == 0 ]]; [[ "$(sha256sum "$base"|cut -d' ' -f1)" == "$expected_base" ]]; [[ "$(sha256sum "$rewriter"|cut -d' ' -f1)" == "$expected_rewriter" ]]; [[ "$(derive|sha256sum|cut -d' ' -f1)" == "$expected_source" ]]
if [[ "${Q38_A43_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
torch_trace=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-4352-ple-only-r1-attempt43/torch-trace
[[ ! -e "$torch_trace" ]]; export TORCH_TRACE="$torch_trace"; source <(derive)
