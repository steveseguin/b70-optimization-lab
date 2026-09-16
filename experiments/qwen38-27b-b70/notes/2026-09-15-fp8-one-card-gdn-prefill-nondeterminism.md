# One-card FP8: nondeterministic GDN prefill found and fixed (head groups)

**On one B70, identical long prompts did not always produce identical results.
Every repeat of a request of 512 tokens or more changed the model's scores
slightly, and occasionally an output token. The two-card service is unaffected.
The cause is a race in the XPU chunked gated-delta-rule kernel when one call
carries all 48 value heads. A research overlay that runs the unchanged kernel in
two 24-head groups (the TP2 per-rank shape) removes it, gives bitwise identical
values, and costs about 2% prompt-reading speed.** Tested September 15, 2026 on
R309 (`7d3219a0`) and R304 (`7cd7bb16`).

## How it showed up

- **Context screen:** the one-card MTP0 server on R309 (512/2,048/12,288-token
  continuations, rung 25) returned a different 128-token continuation for
  `prose-2048` on its second repeat (token 105).
- **Replaying the same request order:** a fresh server reproduced it exactly.
  On R304 a different prompt flipped (`prose-12288`, token 32), so R309 did not
  cause it.
- **Exact logprob comparison** (`--logprobs 1`): every repeat of every prompt
  differed from its first run from the first generated token. Most tokens
  survived because the top choice had a wide margin.
- **Two-card service** (R304, same 21-request order): all logprobs identical,
  bitwise.

## Localisation

| Test | Result |
| --- | --- |
| Host embedding plugin off (eager, GPU embedding) | Same nondeterminism: plugin cleared |
| Per-module output hashes (`b70_layer_hash`, eager) | Layer 0 `in_proj_qkvz` identical, `out_proj` input differs: inside the GDN core |
| W8A16 GEMM alignment census | Deterministic for aligned inputs; odd 2-byte input offsets change results (never produced by the model) |
| `gdn_attention` op census | Stale state or allocator contents: no effect. One-card widths, N ≥ 1,024: repeats differ. TP2 widths: stable |
| Stage stress, 200 repeats | Conv stage 0 mismatches. Delta-rule stage, 48 heads: 7/33/38/71 of 200 at N = 1,024/2,048/4,096/8,192; `core_attn_out` only, final recurrent state always identical. 24 heads (TP2) at 8,192: 0 of 200 |
| Same stage in 2 head groups of 24 | 0 of 200 at every length, bitwise equal to an unglitched whole call |

A source review points to `chunk_fwd_o_kernel`
(`csrc/xpu/gdn_attn/xe_2/chunk_gated_delta_rule_kernels_xe2.hpp`): the output
read (`gemm_TTS(O2, U_T)`, around line 1163) follows only a
`fence_space::local_space` barrier. That barrier covers work-group local memory,
not the USM buffer other sub-groups just wrote. The state update reads the same
buffer later, which matches "output differs, state identical". The global range
grows with value heads (`(batch, num_v_heads, 1)`), so 48 heads oversubscribe
where 24 do not. The suggested kernel fix, not built or tested, is
`global_and_local` barriers at those reads.

## The fix used here

[`b70_gdn_head_groups`](../overlays/b70-gdn-head-groups/b70_gdn_head_groups.py)
(`B70_GDN_HEAD_GROUPS=2`, launcher `--gdn-head-groups 2`):

- For pure non-spec prefill calls only, it runs the unchanged conv stage once,
  then the unchanged delta-rule stage once per 24-head group.
- Each group call uses `tp_size=2` shapes on head slices of the same state cache.
- Decode and speculative calls go to the original fused op.
- Op check
  ([`qwen38-gdn-head-groups-op-check.py`](../scripts/qwen38-gdn-head-groups-op-check.py)),
  including a second chunk continuing from cached state: 12 of 12 grouped runs
  identical, equal to the fused op's most common result. The fused op gave 3-5
  distinct results per 12.

## Server results with the fix (compiled, R309, host embedding, one B70)

- **MTP0, 21-request history replay with logprobs:** zero token and zero
  logprob differences (before: every repeat differed).
- **MTP0 context screen:** all 18 repeats identical.
- **Strict suite:** 12/12 identical to the earlier R309 MTP0 reference (rung 13),
  so the depth 3/4/5 identity results stand.
- **Prompt reading (server prefill, input tokens/s):**

  | Input tokens | Before (rung 25) | Head groups (rung 35) |
  | ---: | ---: | ---: |
  | 512 | 1,650 | 1,614 |
  | 2,048 | 2,214 | 2,158 |
  | 12,288 | 2,088 | 2,044 |

## Kernel fix (R310) replaces the head-group overlay

vllm-xpu-kernels patch
[r310](../patches/vllm-xpu-kernels-gdn-fwd-o-global-barriers-r310-20260915.patch)
changes `chunk_fwd_o_kernel`:

- It turns the `local_space` fences into `global_and_local`.
- It adds two more fences before the output GEMM reads O2/U from USM memory.

The image is R310 (`eb816507`): R304 plus kernels built with
[`build-kernels-0.1.14.1-r310-gdn-barriers.sh`](../docker/rebase-v0290/build-kernels-0.1.14.1-r310-gdn-barriers.sh).

| Test on R310, no head-group overlay | Result |
| --- | --- |
| Stage stress, whole 48-head calls, 200 repeats | 0 mismatches at 1,024/2,048/4,096/8,192 tokens (R309: 7/33/38/71); bitwise equal to the head-group split |
| MTP0 21-request history replay, logprobs | zero token and zero logprob differences |
| MTP0 strict vs rung 35 | 12/12 |
| Depth 5 + INT4 shortlist: strict / context screen / chat quality vs MTP0 | 12/12 / 18/18 / all match |
| MTP0 prefill 512 / 2,048 / 12,288 | 1,650 / 2,220 / 2,088 tok/s (head groups: 1,614 / 2,158 / 2,044) |
| Depth 5 prefill 512 / 2,048 / 12,288 | 1,370 / 2,025 / 1,984 tok/s (head groups: 1,340 / 1,979 / 1,947) |
| Depth 5 strict decode | 53.452 tok/s |

The fence fix makes prefill deterministic at no speed cost, and the head-group
overlay is no longer needed.

## Second issue: long-context depth 5 vs no-MTP (verifier attention rows)

With the GDN fix, depth 5 + shortlist still matched MTP0 on the strict suite
and at 512/2,048 input tokens, but after a 12,288-token prompt `prose-12288`
flipped at token 32 (rung 36), a near-tie that the older nondeterminism had also
flipped.

- **Served-argument trace** ([`b70_fa_trace`](../overlays/b70-fa-trace/b70_fa_trace.py)):
  no-MTP decode and depth-5 verify call the same FA2 paged kernel with identical
  arguments except the query row count (1 vs 6) and key length.
- **Census** ([`qwen38-fa-verify-row-census.py`](../scripts/qwen38-fa-verify-row-census.py),
  served interleaved cache layout, expanded descales, 26-page tables): row r of
  a 6-query causal call equals the same query alone for key lengths up to 1,984.
  From 1,985 it differs by FP16 ULPs, row by row exactly as each row's key length
  crosses 1,985. This holds for contiguous and scattered page tables, and the
  chunk itself repeats exactly.
- **The existing r38 switch `VLLM_XPU_FA_SERIAL_SPEC_DECODE=1` is not a fix**
  (rung 38, 10/12 strict): it also splits prefill chunks into single rows.

[`b70_fa_verify_rows`](../overlays/b70-fa-verify-rows/b70_fa_verify_rows.py)
(`B70_FA_VERIFY_ROWS=1`, launcher `--fa-verify-rows`):

- It applies only to one-request calls with 2-8 query rows and a key length
  above 1,536.
- Each row becomes a single-query call with the decode arguments: `seqused_k`
  and `max_seqlen_k` shortened per row, the same caches, block table and
  descales.
- Prefill, shorter contexts and no-MTP decode are unchanged, and it adds no host
  synchronisation.

## Final one-card recipe results (R309, both overlays, depth 5 + 67k draft shortlist, 13,824 context)

| Rung | Strict vs MTP0 (rung 35) | Context screen vs MTP0 (512/2,048/12,288, 2 repeats) | Strict tok/s | Prefill 512 / 2,048 / 12,288 tok/s | Decode after 12,288 prompt (tokens 1-100) |
| --- | --- | --- | ---: | --- | ---: |
| 41 | 12/12 | 18/18 exact + warmups | 53.395 | 1,340 / 1,979 / 1,947 | 61.7 |
| 42 (fresh server) | 12/12 | 18/18 exact + warmups | 53.395 | 1,343 / 1,981 / 1,948 | 61.7 |

- **Strict speed** without either overlay was 53.602 / 53.463 (rungs 22/23), so
  the overlays are within noise.
- **Prefill** is lower with MTP than MTP0 (1,614 / 2,158 / 2,044) because the
  draft layer also processes the prompt.
- **Host memory:** the fixed embedding plugin raised the minimum available host
  memory during a depth-5 run from 5.33 to 6.97 GiB.
- **Health:** no kernel faults; cached tokens zero on every run.

Evidence: `/mnt/fast-ai/bench-results/optimization-validation-20260915/`
(`fp8-tp1-25`…`42`, `gdn-*census*`, `fa-verify-row-*`,
`gemm-alignment-census-r309`, `tp2-history-probe`) and
[copied receipts](../data/2026-09-15-fp8-one-card-determinism/).
