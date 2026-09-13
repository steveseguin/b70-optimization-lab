#!/usr/bin/env bash
# Verify the exact-serial-GDN kernel series: the bundle must carry tag q38-gdn-exact-serial-bbae3c5
# whose commit is bbae3c5 (two patches over the lane kernel head e421889). With --apply the two
# patches are applied onto e421889 in a throwaway worktree and must produce the same tree.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
tree="${REPRO_KERNEL_TREE:?set REPRO_KERNEL_TREE to a vllm-xpu-kernels clone that contains e421889}"
base=e421889999bc1e5a5f11044d14548b9afdba644d
head=bbae3c59e226c1b0c2a2dca6c51b4465cf36fd26
expected_tree=e87a7a7a5deba4e816f7e24dbf0b6ccf04c03b2b
bundle="$script_dir/vllm-xpu-kernels-q38-gdn-exact-serial-bbae3c5-20260913.bundle"
(cd "$script_dir" && sha256sum --quiet -c series.sha256)
git -C "$tree" cat-file -e "$base^{commit}" || { echo "base $base is not in $tree" >&2; exit 2; }
git -C "$tree" bundle verify "$bundle" >/dev/null
git -C "$tree" fetch --quiet "$bundle" "+refs/tags/q38-gdn-exact-serial-bbae3c5:refs/tags/q38-gdn-exact-serial-bbae3c5"
[[ "$(git -C "$tree" rev-parse refs/tags/q38-gdn-exact-serial-bbae3c5^{commit})" == "$head" ]] || { echo "tag does not resolve to $head" >&2; exit 2; }
[[ "$(git -C "$tree" rev-parse "$head^{tree}")" == "$expected_tree" ]] || { echo "tree mismatch" >&2; exit 2; }
[[ "$(git -C "$tree" rev-list --count "$base..$head")" == 2 ]] || { echo "series length changed (expected 2)" >&2; exit 2; }
git -C "$tree" merge-base --is-ancestor "$base" "$head"
if [[ "${1:-}" == "--apply" ]]; then
  wt="$(mktemp -d)"
  git -C "$tree" worktree add --quiet --detach "$wt" "$base"
  git -C "$wt" am --quiet "$script_dir"/vllm-xpu-kernels-32798565-gdn-spec-round-state.patch "$script_dir"/vllm-xpu-kernels-bbae3c5-gdn-spec-unroll.patch
  applied="$(git -C "$wt" rev-parse HEAD^{tree})"
  git -C "$tree" worktree remove --force "$wt"
  [[ "$applied" == "$expected_tree" ]] || { echo "applied series tree $applied != $expected_tree" >&2; exit 2; }
  echo "series applies onto $base and reproduces tree $expected_tree"
fi
echo "kernel series verified: $head (tree $expected_tree) over the lane kernel head $base"
