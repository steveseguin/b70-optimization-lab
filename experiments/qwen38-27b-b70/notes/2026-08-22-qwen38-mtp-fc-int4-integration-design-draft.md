# Qwen3.8 mtp.fc INT4 integration — design draft (NOT LAUNCHABLE)

Date: 2026-08-22

Status: **DRAFT design note only.** No code exists, nothing is authorized,
and this note deliberately freezes no hashes. It grounds the integration
experiment that the
[operator result](2026-08-22-qwen38-mtp-fc-int4-operator-result.md)
(`qualified-only-for-default-off-integration-design`, ~58-60 us/call saved
per shard) qualified the *idea* of. Launch requires a real preregistration
with frozen hashes, its own review, and explicit user authorization, per
the campaign standard.

## Source grounding (verified in the pinned vLLM tree)

- The production site is
  `vllm/model_executor/models/qwen3_next_mtp.py:67` —
  `self.fc = ColumnParallelLinear(hidden*2=10240, hidden=5120,
  gather_output=True, bias=False, return_bias=False, quant_config=…,
  prefix="mtp.fc")` — called once per MTP forward at line 117 after the two
  pre-fc RMS norms and the `[embeds, hidden]` concat.
- `quant_config` is already plumbed to the layer; the AutoRound checkpoint
  simply carries no INT4 payload for `mtp.fc` (it loads FP16 from
  `model_extra_tensors.safetensors`), which is why it runs FP16 today.
- The MTP path compiles under the `eagle_head` outer role of the sealed
  cache. **Any operator substitution inside `fc` changes compiled-graph
  content and therefore requires a new compile-cache identity** — the
  sealed `b991`/`f358` artifacts cannot be reused, exactly as the operator
  prereg's integration boundary demanded.
- The Q64xK32 precedent registers its door inside the compiled device
  library; this lever is different — it is a Python-level op substitution
  and must be gated by a new `VLLM_XPU_*` env registered in `envs.py` and
  included in `envs.compile_factors()` so the cache key forks.

## Proposed shape (default-off)

1. New env door (working name `VLLM_XPU_MTP_FC_INT4`, default 0),
   registered in `envs.py` + `compile_factors()`.
2. When on, at weight-load time for `mtp.fc` only: load the **frozen
   qualified packed buffers** (per-TP-rank packed backing / logical
   qweight / FP16 scales whose SHA-256s are already frozen in the operator
   prereg) rather than re-packing in-process — byte-identity to the
   qualified artifacts, no pack-math drift concern. Verify shas at load;
   fail closed to FP16? No — fail closed to refusing startup (a silent
   fallback would fake engagement).
3. Forward swap for that layer only: eager
   `torch.ops._xpu_C.int4_gemm_w4a16(bias=None, group_size=128,
   g_idx=None, input_dependency=True)` with the completion barrier env on,
   preserving publication before the `gather_output` all-gather consumes
   the shard output. Both runtime markers must appear exactly once per
   rank (engagement gate, same pattern as the operator screen).
4. VRAM accounting: initially retain the FP16 parameter alongside packed
   buffers (~+26 MiB/rank packed; FP16 shard ~100 MiB/rank retained) and
   measure; freeing the FP16 param is a later, separately-gated step.
5. Fresh persistent compile-cache identity: new cache build under a new
   namespace, sealed with a canonical-tree manifest before any A-B, with
   the marginfree anchor re-established on the new cache (the incumbent
   anchor is cache-identity-specific).

## Gate ladder (each preregistered before running)

eager parity screen (the operator screen's oracle, in-process) ->
compile/graph capture clean boot with markers -> real concurrent TP2
smoke -> MTP acceptance-rate non-regression on the short suite ->
target-token/quality battery -> endpoint A-B-B-A vs the incumbent
(short-KV suite; expected effect from the operator arithmetic is bounded
by ~290 us/target-step, i.e. low single-digit percent at ~40 ms/step —
the hurdle must be set from anchor resolution, not wishfulness).

## Interaction with the chunked-prefill corruption finding

None expected for the campaign's own validity: the integration A-B runs
the short single-chunk suite. But if the corruption fix (separate work)
lands first and touches the compiled graphs or the GDN splitting ops, the
fresh cache build here must be sequenced after it, or rebuilt.

## Cost estimate

The dominant cost is the fresh sealed cache build + anchor
re-establishment (one build + several anchor arms), then the standard
four-arm A-B-B-A. Roughly an evening of serialized GPU time on GPUs 2,3.
