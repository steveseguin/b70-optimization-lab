#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || {
    printf 'FAIL: run this from a b70-optimization-lab clone\n' >&2
    exit 1
}
cd "${repo_root}"

branch=$(git branch --show-current)
[[ ${branch} == main ]] || {
    printf 'FAIL: expected branch main, found %s\n' "${branch}" >&2
    exit 1
}

[[ -z $(git status --porcelain) ]] || {
    printf 'FAIL: worktree is dirty; preserve local work before synchronizing\n' >&2
    git status --short >&2
    exit 1
}

git fetch origin main
git merge --ff-only origin/main

printf 'Qwen3.8 worker synchronized at %s\n' "$(git rev-parse HEAD)"
printf 'Read: experiments/qwen38-27b-b70/MULTI-HOST-HANDOFF.md\n'
printf 'Read: experiments/qwen38-27b-b70/DO-NOT-REPEAT.md\n'
