# Speculation divides the captured concurrency range by (1 + depth)

Established from the vLLM source in `src/vllm-current-main` and confirmed against
the servers this lane actually ran. Relevant to every speculative lane here, not
only the 4B.

## The rule

`max_cudagraph_capture_size` counts **tokens**, not sequences. A uniform decode
step under speculation is `1 + num_speculative_tokens` tokens per sequence
(`gpu_model_runner.py`: `self.uniform_decode_query_len = 1 + self.num_spec_tokens`).
So the largest concurrency that still has a captured decode graph is

```
max_concurrency_captured = max_cudagraph_capture_size / (1 + depth)
```

At this lane's settings — capture sizes 1..64, `max_cudagraph_capture_size` 64,
depth 3 — that is **16 sequences**. At depth 6 it would be 9. Without
speculation it is 64.

Two further details from `v1/cudagraph_dispatcher.py`:

- the decode capture list is filtered to
  `uniform_decode_query_len <= x <= uniform_decode_query_len * max_num_seqs`;
- capture sizes are first rounded to a multiple of `uniform_decode_query_len`
  (`config/compilation.py`: "MRV1 adjusts cudagraph sizes to be a multiple of
  uniform_decode_query_len"), then deduplicated.

## It matches what the servers report

Rounding this lane's 18 capture sizes up to multiples of 4 and deduplicating
gives `4, 8, 12, 16, 20, 28, 32, 40, 52, 60, 64` — eleven distinct shapes, the
largest 64 tokens, i.e. 16 sequences.

The servers say exactly that:

```
depth 3 :  Capturing CUDA graphs (decode, FULL): 11/11
MTP0    :  Capturing CUDA graphs (decode, FULL): 18/18
```

The MTP0 server captures all 18 because its tokens equal its sequence count.

## Consequences for this lab

**Every depth-3 ladder rung above c16 has been running without cudagraph replay.**
That includes the c32 and c64 rungs of the published 4B matrix and of the 9B and
27B ladders at the same depth. Those measurements are not wrong — the server did
what it did and the numbers are what it produced — but a sentence like "measured
with full decode-only capture" describes only the rungs at or below
`64/(1+depth)`.

**A capture-on versus capture-off comparison is empty above that concurrency.**
The 4B `f2` arm was designed as exactly that comparison and its depth-3 half had
to be withdrawn for this reason; its MTP0 half, where the range really is c64,
stands.

**It is a plausible cause of the c16 identity step**, and it is confounded with
the GDN speculative group size of 16 sequences, which predicts the same boundary
at this depth. The `k128` arm raises the ceiling to 128 tokens (32 sequences at
depth 3) at a fixed group size while `s08`/`s16`/`s32` vary the group size at a
fixed ceiling, which separates them.

**Raising the ceiling is cheap and probably worth it** for any speculative lane
that serves more than `64/(1+depth)` concurrent users, but capture sizes and
`max_cudagraph_capture_size` must rise together — an entry above the ceiling is
ignored, and the ceiling without the sizes leaves gaps. Capture cost is small
here: the 4B server reports "Graph capturing finished in 2 secs, took 0.13 GiB".

## What this does not say

It does not say capture helps. Where the comparison is valid — MTP0, c32 and c64
— capture changed neither divergence (11 of 1920 against 9 of 1920) nor
throughput (1722.7 against 1717.9 tok/s). Whether it helps at depth 3 above c16
is unmeasured, which is what `k128` will show.
