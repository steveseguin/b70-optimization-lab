# Qwen3.8 Flash-Next FP8 EP4 M1 sparse expert-assignment A1 preregistration

Date: 2026-09-01
Status: CPU candidate only; **not launch-authorized**

## Purpose and profile basis

The A28 target-step profile records exactly 48 calls per generated token on
each rank to `_moe_C::moe_align_block_size`. Its align/scan kernel averages
`0.240581 ms/token` across ranks and its associated sort kernel another
`0.043295 ms/token`, or `0.283876 ms/token` together. The same step has 48 M1
routed-MoE layers. Each call receives only ten selected global expert IDs
(`M=1`, `top_k=10`) but the current generic path is parameterized for all 512
global experts. Even perfect elimination projects only about `+0.157%` at the
protected target rate, so this is a bounded stackable bookkeeping candidate,
not a numerical model change or major endpoint lever.

The [A28 endpoint profile](2026-08-30-tp4-mtp0-a28-target-step-profile-result.md)
also records the immediately preceding TopKGating region 48 times per token.
The separately preserved TopKGating component result establishes lossless
shape behavior, not endpoint multiplicity, and neither result proves that this
assignment candidate is fast or endpoint-visible.

## Frozen production contract

- Qwen/Qwen3.8-Flash-Next-FP8, target-only decode;
- TP4/EP4, 512 global experts, 128 local experts per rank;
- contiguous maps: rank 0 owns `0..127`, rank 1 `128..255`, rank 2
  `256..383`, and rank 3 `384..511`, each mapped to local `0..127`;
- `M=1`, ten unique global expert IDs, `BLOCK_SIZE_M=16`;
- preserve the production `ignore_invalid_experts=True` semantics: map global
  IDs to rank-local IDs first and filter remote (`-1`) selections;
- preserve stable ascending mapped-local-expert order and flattened
  token-position order;
- compare all three outputs exactly: the 160-entry `sorted_token_ids`, the ten
  `expert_ids`, and scalar `num_tokens_post_pad`.

The sparse candidate may inspect and order only the ten selected IDs. The CPU
authority independently scans the complete 512-entry map and all 128 mapped
local IDs. Both initialize the full 160-entry sorted buffer to flattened-token
sentinel `10` and the ten-entry expert buffer to `0`, matching the XPU general
kernel's `inactive_expert_id=0`. With `h` local hits, the active blocks contain
mapped local IDs, `num_tokens_post_pad=h*16`, and both tails retain those
sentinels. Because local expert 0 and the unused expert tail have the same
value, active-prefix length is determined only as
`num_tokens_post_pad / BLOCK_SIZE_M`, never by inspecting expert-ID values.
Valid production inputs always have ten unique global experts.

## Required CPU evidence

The experiment-local runner must pass:

1. all four exact contiguous expert maps;
2. seeds `20260827`, `20260828`, and `20260829`;
3. 100 changing unique routes per seed on every rank (1,200 rank cases);
4. per-rank adversarial boundary/interleaving cases with exactly 0, 1, 5, and
   10 local hits (16 cases);
5. exact equality of all three outputs and no input mutation;
6. fail-closed shape, dtype, uniqueness, range, and map validation.

## Authorization boundary

This preregistration adds no live vLLM change, invokes no XPU API, performs no
full-model load, and authorizes no endpoint experiment. Its runner must report
`launch_authorized=false`, `endpoint_authorized=false`, and
`gpu_execution_authorized=false`.

The source audit closes immediate XPU implementation as low priority behind
W13-N32 and HC gate-mix. A future native gate must use one workgroup/submission,
support invalid and duplicate routes without host reads, exercise eager and
captured modes, compare all three outputs, and use matched timing arms. The
[deferred native design](2026-09-01-ep4-m1-sparse-expert-assignment-xpu-design-deferred.md)
preserves the exact requirements. Only new profile evidence with a meaningful
ceiling should reopen it; all protected speed and quality results remain
unchanged.
