# Qwen3.8 Flash-Next FP8 PLE fixed-input isolation

Date: 2026-08-30
Status: bounded fixed-input components pass

The A16/A21 trace comparison first differed at the complete output of
zero-based decoder layer 1, the checkpoint's only PLE-bearing layer. Three
fixed-input gates now close the leading PLE component mechanisms without a
model load:

- the exact owner-sparse FP8-byte/int8 TP4 reduction returned one hash across
  100 repeats on all four ranks and matched a CPU byte oracle;
- a pinned host table exposed through the XPU UVA view, with the real
  `[64,16,160]` PLE lookup geometry, owner masks, and the same reduction,
  returned one hash across 100 repeats on all ranks and matched its oracle;
- 64 sequential 64-token PLE short-convolution chunks returned identical
  output and final-state hashes across two repeats, and a deliberately dirty
  valid cache slot produced the exact clean trajectory when the first chunk
  declared no initial state.

The first convolution harness used slot 0 and appeared to preserve dirty
state. Slot 0 is `NULL_BLOCK_ID`, so that was correct padding behavior and is
recorded only as a harness error. The corrected valid-slot result is the only
admissible result.

The CPU n-gram context also passed every boundary from 0 through 4032 in
64-token steps, repeated at each boundary, plus request-slot reuse. Separately,
the loader now fails closed unless a split PLE checkpoint supplies every one
of its 128 logical shard indices; the checkpoint index contains all 128 and 15
focused PLE tests pass.

These results do not prove the full 12 GB/rank checkpoint table or real request
values are identical across starts. They do show that fixed-input transport,
lookup, reduction, convolution state, and context progression are not reasons
to change inference arithmetic. The next evidence is an all-rank internal
trace pair over raw FP8 lookup, dequantization, projection/gate, convolution
input/output, attention, and MLP boundaries.

Structured receipt:
[`../data/20260830-ple-fixed-input-isolation.json`](../data/20260830-ple-fixed-input-isolation.json).
