#!/usr/bin/env bash
# The T5 prefetch-reachability campaign. Fire only after an adversary PROMOTE.
#
# Four arms, round-robin, binary swapped in per leg:
#
#   old       53f3d294  the incumbent. Its generic decode path cannot see
#                       PREFETCH_DIST at all, which is the whole finding, so it
#                       needs only one arm rather than three. Distance is
#                       passed as 6 to match the recorded incumbent config
#                       byte for byte.
#   new-pd6   e0bb78a3  what the plumbing itself cost. Not neutral by
#                       construction: the mainloop gained a 2->4 predicate
#                       chain and a 1->3 token sync.allrd in the loop body.
#   new-pd3   e0bb78a3  does a shorter distance help
#   new-pd12  e0bb78a3  does a longer distance help
#
# Read three comparisons separately and do not conflate them:
#   best-new vs old        the ship decision
#   new-pd6  vs old        the plumbing tax
#   pd3/pd12 vs new-pd6    the lever itself, clean because every plumbed arm
#                          carries the same tax
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly rounds="${1:-5}"

readonly old_tree="/home/steve/src/laguna-xpu-kernels-incumbent-46a88e0"
readonly old_lock="$script_dir/runtime-lock-mad.json"
readonly new_tree="/home/steve/src/laguna-xpu-kernels-tile12-20260728"
readonly new_lock="$script_dir/runtime-lock-pfreach.json"

readonly old_expect=53f3d2941ce322bcdff1b0463ec6fe72387036ea54d3f602a08d690744b3459f
readonly new_expect=e0bb78a3f12e7340cf5c69c225272585c02a0663e88c2ba32463e899435f9a75

# Assert each tree holds the binary its arm is named for. Without this, a
# forgotten install leaves the new tree carrying the incumbent .so and all four
# arms measure the same code -- for 140 minutes, producing a confident null
# result that means nothing. The campaign's whole value is that the arms
# differ.
assert_so() {
  local tree="$1" want="$2" label="$3" got
  got="$(sha256sum -- "$tree/vllm_xpu_kernels/libgrouped_gemm_xe_2.so" | cut -d' ' -f1)"
  [[ "$got" == "$want" ]] || {
    echo "arm $label: $tree has $got, expected $want" >&2
    echo "  (did you forget to install build/temp/libgrouped_gemm_xe_2.so ?)" >&2
    exit 2
  }
}
assert_so "$old_tree" "$old_expect" old
assert_so "$new_tree" "$new_expect" new
echo "binary identity asserted for both trees"

# args 4..25, differing only in argument 21, the prefetch distance
argtail() { printf "12 11 1 0 0 0 0 0 0 1 1 0 0 '' 64 0 '' %s 0 1 0 ''" "$1"; }

exec "$script_dir/laguna_xbin_campaign.sh" pfreach "$rounds" \
  "old|$old_tree|$old_lock|$(argtail 6)" \
  "new-pd6|$new_tree|$new_lock|$(argtail 6)" \
  "new-pd12|$new_tree|$new_lock|$(argtail 12)" \
  "new-pd3|$new_tree|$new_lock|$(argtail 3)"
