#!/usr/bin/env bash
# Verify the lossless-MTP1 overlay series: the bundle must carry tag
# q38-placement-mtp1-005dc578 whose commit is 1b2a17c1 with tree 1cb86e07,
# reachable from public vLLM commit 76cfe1cd. With --apply, the 55 patches are
# also applied onto 76cfe1cd in a throwaway worktree and must produce the same tree.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
tree="${REPRO_VLLM_TREE:?set REPRO_VLLM_TREE to a vllm clone that contains 1b2a17c1 (restore it from the lossless-MTP1 bundle first)}"
base=1b2a17c1e7c41985d6a5e0eb324ada4775c25e60
head=005dc57895896f770157ea94f68e473e7447139e
expected_tree=d82fb5f2461be1a1f1050c1f681d17f5e7325a17
bundle="$script_dir/vllm-q38-placement-mtp1-005dc578-20260906.bundle"
(cd "$script_dir" && sha256sum --quiet -c series.sha256)
git -C "$tree" cat-file -e "$base^{commit}" || { echo "base $base is not in $tree" >&2; exit 2; }
git -C "$tree" bundle verify "$bundle" >/dev/null
git -C "$tree" fetch --quiet "$bundle" "refs/tags/q38-placement-mtp1-005dc578:refs/tags/q38-placement-mtp1-005dc578" 2>/dev/null || git -C "$tree" fetch --quiet "$bundle" "+refs/tags/q38-placement-mtp1-005dc578:refs/tags/q38-placement-mtp1-005dc578"
[[ "$(git -C "$tree" rev-parse refs/tags/q38-placement-mtp1-005dc578^{commit})" == "$head" ]] || { echo "tag does not resolve to $head" >&2; exit 2; }
[[ "$(git -C "$tree" rev-parse "$head^{tree}")" == "$expected_tree" ]] || { echo "tree mismatch" >&2; exit 2; }
[[ "$(git -C "$tree" rev-list --count "$base..$head")" == 9 ]] || { echo "series length changed" >&2; exit 2; }
git -C "$tree" merge-base --is-ancestor "$base" "$head"
if [[ "${1:-}" == "--apply" ]]; then
  wt="$(mktemp -d)"
  git -C "$tree" worktree add --quiet --detach "$wt" "$base"
  git -C "$wt" am --quiet "$script_dir"/00*.patch
  applied="$(git -C "$wt" rev-parse HEAD^{tree})"
  git -C "$tree" worktree remove --force "$wt"
  [[ "$applied" == "$expected_tree" ]] || { echo "applied series tree $applied != $expected_tree" >&2; exit 2; }
  echo "series applies onto $base and reproduces tree $expected_tree"
fi
echo "overlay series verified: $head (tree $expected_tree) over the lossless MTP1 head $base"
