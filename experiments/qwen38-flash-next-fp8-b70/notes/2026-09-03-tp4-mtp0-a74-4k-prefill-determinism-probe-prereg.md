# Qwen3.8 Flash-Next FP8 A74 4K-prefill determinism probe preregistration

Date: 2026-09-03 (overnight; diagnostic only; no authority is pinned, no
protected result is touched)

## Question

The deterministic graph line is logit-exact through 2048-token prefill
(A66/A67 probes) and repeat-exact at 2K across three servers (A70-A72) at a
2304-token capacity. Is it also exact at 4096-token prefill with the same
identity served at 4352 tokens? This is the evidence the A73 proposal
needs before any 4K authority question is put to the user.

## Design

`tools/rewrite-q38-a72-to-a74-4k-probe.py` derives A74 from the frozen A72
packet (head `2169dbfe...`, flag, graph, map, public oneCCL) with one server
change: `MAX_MODEL_LEN=4352` (the launcher's frozen-capacity rule, message
and static assertion move from 2304 to 4352; the 128 MiB cache is kept, as
A9/A10 served 4352 tokens with it). The supervisor's identity checks follow.
The frozen client is renamed for hash pinning only; the arm runs
`probe-q38-a59-logprob-determinism.py` with `--prompt-case-depth 4096`
(fixture case 4096, bound by the fixture's recorded digest) at depths
`8,64,256,2048,4096`: eight `max_tokens=1` repeats and three 128-token
repeats per depth. Attempt 74 / port 19746.

## Reading

- Identical first-step logits and identical 128-token repeats at 4096: the
  deterministic line is exact through 4K prefill; A73's authority question
  is the only remaining step for a 4K record.
- Exact through 2048 but not at 4096: a second source enters between 2K and
  4K prefill (QSA subset selection at 4K, GDN chunk state); the trace is
  re-armed at that depth.
