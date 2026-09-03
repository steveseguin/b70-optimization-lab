# Qwen3.8 Flash-Next FP8 A76 4K-prefill determinism probe result

Date: 2026-09-03 02:57--03:43 EDT
Status: diagnostic positive; the deterministic graph line is logit-exact
through 4096-token prefill at 4352 capacity; no authority pinned; no
protected result touched

## Server

The A72 deterministic graph identity (overlay `2169dbfe...`,
`VLLM_XPU_MKLDNN_DETERMINISTIC=1`, full decode graph, public oneCCL
twoshots, tuned M1 W13-N32 map, PLE-only UVA placement, 128 MiB cache)
served at `MAX_MODEL_LEN=4352`. Launched behind a dropped page cache after
A75's guard stop; the offload receipt logged normally; load 13 minutes; no
hang; no kernel GPU fault; teardown 143 after the probe's stop file.

## Probe (fixture case 4096, depths 8/64/256/2048/4096)

| depth | first-step logits identical (8x) | spread | 128-token repeats (3x) | output hash |
| ---: | --- | ---: | --- | --- |
| 8 | yes | 0.0 | identical, zero logprob difference | |
| 64 | yes | 0.0 | identical, zero logprob difference | |
| 256 | yes | 0.0 | identical, zero logprob difference | |
| 2048 | yes | 0.0 | identical, zero logprob difference | `afffd2110812...` |
| 4096 | yes | 0.0 | identical, zero logprob difference | `c6193cc6c9a1553f56d7ce78faea9c8bfa628a67fcea229b1c99279a149f6639` |

Two facts worth stating plainly. The 2048-token continuation on this
4352-capacity server is the same `afffd2110812...` that A70, A71 and A72
produced at 2304 capacity: the deterministic line's outputs do not depend
on the served capacity. And the 4096-token continuation is one hash across
three repeats with zero logprob difference at all 128 positions, on a
prefix depth the native line never repeated reliably (A7, A10, A15, A24,
A25 all failed their 4K repeat gates).

## Standing

A73 (exact-4K rows with the frozen client) now needs only the authority
policy the decision memo already asks for; `c6193cc6c9a1553f56d7ce78faea9c8bfa628a67fcea229b1c99279a149f6639`
is the deterministic line's candidate 4K authority, recorded here without
replacing the protected native-line `1d833e5f...`. Receipt:
[`20260903-tp4-mtp0-a76-4k-logprob-determinism.json`](../data/20260903-tp4-mtp0-a76-4k-logprob-determinism.json).
