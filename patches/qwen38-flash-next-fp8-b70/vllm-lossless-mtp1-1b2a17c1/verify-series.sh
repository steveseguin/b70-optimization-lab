#!/usr/bin/env bash
# Verify the lossless-MTP1 overlay series: the bundle must carry tag
# q38-lossless-mtp1-1b2a17c1 whose commit is 1b2a17c1 with tree 1cb86e07,
# reachable from public vLLM commit 76cfe1cd. With --apply, the 55 patches are
# also applied onto 76cfe1cd in a throwaway worktree and must produce the same tree.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
tree="${REPRO_VLLM_TREE:?set REPRO_VLLM_TREE to a vllm-project/vllm clone that contains 76cfe1cd}"
base=76cfe1cd88d30d525eec8be5bff75f8b77471c88
head=1b2a17c1e7c41985d6a5e0eb324ada4775c25e60
expected_tree=1cb86e078991895906e75544207733ee7373c55d
bundle="$script_dir/vllm-q38-lossless-mtp1-1b2a17c1-20260906.bundle"
(cd "$script_dir" && sha256sum --quiet -c series.sha256)
git -C "$tree" cat-file -e "$base^{commit}" || { echo "base $base is not in $tree" >&2; exit 2; }
git -C "$tree" bundle verify "$bundle" >/dev/null
git -C "$tree" fetch --quiet "$bundle" "refs/tags/q38-lossless-mtp1-1b2a17c1:refs/tags/q38-lossless-mtp1-1b2a17c1" 2>/dev/null || git -C "$tree" fetch --quiet "$bundle" "+refs/tags/q38-lossless-mtp1-1b2a17c1:refs/tags/q38-lossless-mtp1-1b2a17c1"
[[ "$(git -C "$tree" rev-parse refs/tags/q38-lossless-mtp1-1b2a17c1^{commit})" == "$head" ]] || { echo "tag does not resolve to $head" >&2; exit 2; }
[[ "$(git -C "$tree" rev-parse "$head^{tree}")" == "$expected_tree" ]] || { echo "tree mismatch" >&2; exit 2; }
[[ "$(git -C "$tree" rev-list --count "$base..$head")" == 55 ]] || { echo "series length changed" >&2; exit 2; }
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
echo "overlay series verified: $head (tree $expected_tree) over public $base"
