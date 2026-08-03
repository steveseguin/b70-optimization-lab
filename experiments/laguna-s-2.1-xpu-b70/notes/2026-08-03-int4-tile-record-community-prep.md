# Laguna INT4 tile-record community branch preparation

Date: 2026-08-03 America/Toronto

Status: **two focused current-upstream branches are committed, host-tested,
and pushed to contributor forks; no pull request opened**.

## What is appropriate to publish

The full integration worktrees are durable research branches, not focused
community pull-request branches. After refreshing upstream on 2026-08-03:

- the XPU-kernel integration branch was 22 upstream commits behind and 109
  local commits ahead of `vllm-project/vllm-xpu-kernels:main`;
- the vLLM integration branch was 760 upstream commits behind and 218 local
  commits ahead of `vllm-project/vllm:main`.

Those histories include the broader Laguna exact-small stack and should not be
pushed as if they were reviewable single-purpose community changes.

The standalone host packers do replay cleanly onto current upstream `main` and
are isolated in one-commit community branches:

| repository | worktree / branch | commit | validation |
| --- | --- | --- | --- |
| `vllm-project/vllm-xpu-kernels` | `/home/steve/src/community-vllm-xpu-kernels-laguna-int4-20260803`, `community/laguna-int4-tile-record-20260803` | `268cb6e` | 9/9 host tests, Ruff pass |
| `vllm-project/vllm` | `/home/steve/src/community-vllm-laguna-int4-20260803`, `community/laguna-int4-tile-record-20260803` | `31f2e44e1` | 6/6 host tests, Ruff pass |

Both branches are based directly on the refreshed upstream heads and are one
commit ahead. They contain no model artifacts, credentials, build outputs,
runtime logs, or quarantined evidence.

## Push state

The optimization-lab branch
`experiment/laguna-kernel-loop-20260728` was pushed successfully to
`steveseguin/b70-optimization-lab` using its repository deploy key.

Contributor forks were created and added as the separate writable remote
`fork`; community upstream remains `origin`. The focused branches are now at:

- `steveseguin/vllm-xpu-kernels`, branch
  `community/laguna-int4-tile-record-20260803`, commit `268cb6e`;
- `steveseguin/vllm`, branch
  `community/laguna-int4-tile-record-20260803`, commit `31f2e44e1`.

The full experiment branches were not pushed as community PR branches.

No pull request has been opened. Before opening one, explain that these are
host packing primitives with byte-exact tests; they do not claim device-speed
improvement or runtime integration on current upstream.
