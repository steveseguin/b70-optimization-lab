# Qwen3.8 Q8 DP4A2 transfer: exact, but not promoted

Date: 2026-08-16

## Decision

The later two-independent-accumulator DP4A schedule (`DP4A2`) from the
Qwen3.6 search is compatible with Qwen3.8 and passed the quality gates, but it
did not improve the Qwen3.8 endpoint. Keep the published Qwen3.8 one-chain
DP4A source snapshot and do not promote or retest DP4A2 unchanged.

“Transferred cleanly” in the bring-up notes means source and quality
compatibility only. It does **not** mean that DP4A2 is part of the promoted
Qwen3.8 patch.

## Full cold-suite evidence

Both DP4A2 runs used the fixed 12-prompt suite, one cold request per prompt,
`cached_tokens=0`, Q8_0 target weights, F16 KV, TP2, and no speculation,
DFlash, MTP, response reuse, or history acceleration.

| Run | helper median, tokens 1-100 after TTFT | conventional 100-token median | full-output after-TTFT median | wall median | TTFT median |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 37.098968 | 36.727979 | 36.703883 | 36.208250 | 181.132 ms |
| 2 | 36.866736 | 36.498069 | 36.546570 | 36.054612 | 174.437 ms |

The promoted one-chain endpoint is `36.772932 tok/s` conventional and
`36.661845 tok/s` full-output after TTFT. DP4A2 therefore produced one
near-tie and one slower replay, with no repeatable gain. All twelve output
SHA-256 values in each DP4A2 run exactly matched the promoted one-chain run.

## Retained local evidence

- run 1: `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-fixed-warmup-run1/suite.json`
  (`sha256:c349a2c002575964bc575c01497fa3743336c143533f1a40b31ea82fbff01b5c`)
- run 2: `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-fixed-warmup-run2/suite.json`
  (`sha256:74f8d6e8ca9c048be4f8abb5c36030aefe60a23d2ff1853ff1aadf24c3edc33b`)
- source/build alias: `/mnt/fast-ai/src/llama.cpp-q8-tp2-dp4a2`
- tested oneAPI 2026.1.1 server:
  `sha256:f7bc299a830cbbbbfc3e06ac46ef4f063b9d85e43995c04e07ffa9de0aa390bb`

The source mechanism and its Qwen3.6 A/B history remain documented in
[`notes/2026-08-14-qwen36-q8-tp2-40tps-pass2.md`](../../../notes/2026-08-14-qwen36-q8-tp2-40tps-pass2.md).

