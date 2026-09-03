# Qwen3.8 Flash-Next FP8 A70 full-decode-graph deterministic battery result

Date: 2026-09-02 22:26--22:47 EDT
Status: every quality gate passed on the protected hashes; short and exact-2K
rows measured; the client failed closed only on the exact-2K output
authority, which the prereg reserved for the user; no protected result
changed; no promotion yet (fresh-server repeat pending)

## Server

A70 is the A67/A56 full-decode-graph identity (`VLLM_XPU_ENABLE_XPU_GRAPH=1`,
`FULL_DECODE_ONLY` capture size 1, public oneCCL `4ceafd1` with twoshots,
tuned M1 W13-N32 map, PLE-only UVA placement, 2304 max model length, 128 MiB
cache) at overlay head `805cde59...` with `VLLM_XPU_MKLDNN_DETERMINISTIC=1`
(four `mkldnn.deterministic=True` lines, `mkldnn_deterministic=1` identity
receipt). Load 13 minutes (weights 22:37, healthy 22:41). No hang, no kernel
GPU fault; teardown 143 after the client exited.

## Client gates (frozen A56-lineage client, port 19742)

| gate | result |
| --- | --- |
| runtime identity, twoshots selector, W13-N32 resolver receipt | pass |
| recovery canary | pass |
| exact semantic cases | 6/7, sole miss `code_execution=30` (inherited boundary) |
| 16-repeat | 16/16, one hash, the protected `3b0b3192...` |
| exact cache-zero 2K needle | pass, 2048 prompt tokens, cached 0 |
| short rows (p146/o256/c1, after first text) | `23.028483 / 24.019366 / 22.577949 tok/s`, median **`23.028483`** |
| exact-2K rows (p2048/o128, 99-interval) | `13.257063 / 13.948739 tok/s` |
| exact-2K output identity | both rows one hash `afffd211...`; **not** the protected `5fd297f7...` |

For reference, A56 (same identity without the flag) measured short rows
`23.626811 / 22.218021 / 23.809477` (median `23.626811`) and exact-2K rows
`12.982052 / 12.333460`. A70's rows are within the short-row spread and above
the 2K rows; the deterministic flag costs nothing measurable here.

## The exact-2K authority

The protected `5fd297f7...` output was recorded on 2026-08-27 by the eager
3072-context attempt 2 server, a server of the class this campaign has since
shown to be run-to-run non-repeatable at the logit level (the same 2K/4K
rows failed their own repeat gates in A7, A10, A15, A24 and A25). A70's two
rows agree with each other byte for byte and diverge from that record at
generated token 12 of 128 (114 later positions differ). Decoded, the prompt
ends inside a JSON array of benchmark cases; the authority continues
`"branch": "main", "prompt": "You are refactoring a small Python repository
... Include one risky step and how to verify it."`, while A70 continues
`"branch": "main", "commit": "0000...", "prompt": "You are refactoring a
small Python repository ... Include enough detail for a maintainer to execute
the refactor directly."`. Both are well-formed, on-task continuations of the
fixture; neither is a quality authority, and the semantic battery, repeat
hash and needle are unchanged.

Nothing was overwritten. Whether `afffd211...` becomes the exact-2K authority
of the deterministic line (with the old hash retained as the native-line
record) is the user's decision.

## Next

- A71: byte-identical fresh-server repeat of A70 (new attempt, empty caches)
  with the client's exact-2K pin set to `afffd211...`; two independent
  servers agreeing on every gate is the promotion evidence the campaign has
  lacked since 2026-08-28.
- The 27B TP2 public-chain replay holds the GPUs first (user request).
