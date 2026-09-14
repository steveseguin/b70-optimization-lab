# Radiance MTP transfer audit, September 14

The most useful small lead is removing unnecessary attention-metadata work. The other reviewed MTP ideas are already present in concept, previously negative, or inactive under our current serving configuration. There is no new measured speed improvement from this audit.

Scope: static primary-source review of Radiance commit `f295b9ef51ad413a68e4192371e0377741a354ce`, against the qualified R304 official FP8/MTP1 source. No contributed module was imported or run, and no model requests, GPU operations or service changes were performed. Sources and SHA-256 identities are in [the audit receipt](2026-09-14-mtp-audit-source.json). The GDN builder reconstructed independently from public v0.29.0 plus the repository's R303/R304 patches exactly matches both its frozen contract and the served file (`94498e7d…`).

## Worth a small follow-up

**Defer unused GPU metadata subtraction.** The R304 builder assigns GPU `query_lens` at line 291, but every read is within the mixed branch, at lines 351, 372, 377 and 382. An AST check confirms that the steady all-spec path never consumes it. An [inactive two-line patch and proof](2026-09-14-mtp-audit-query-lens/README.md) defer that assignment to its consumer branch. This removes one GPU integer subtraction per affected metadata build; its runtime effect is unmeasured and is expected to be small.

Radiance's [metadata review](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/patch_gdn_metadata.py#L3-L25) motivated this check. Its actual `LENS_NEW` replacement still contains the eager subtraction, so the pinned implementation does not itself realize the advertised deferral.

The same source replaces several CPU tensor dispatches with NumPy integer bookkeeping. That may be useful, but all three relevant replacement anchors fail to match R304: its first-chunk classification, mixed-request handling and active width have evolved. A direct transplant is inappropriate. A future isolated port must compare every count, mask and width for first prompts, resumed chunks, rejected drafts, zero-length padding and mixed requests, while preserving asynchronous source-buffer lifetimes. No full rewrite was prepared.

## Retain existing choices

**Local-vocabulary draft argmax is a known negative lab screen.** Radiance [reduces draft logits on each rank before exchanging small statistics](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/radiance_draft.py#L83-L129). Existing vLLM has `LogitsProcessor.get_top_tokens`; the lab tested a model hook on August 26. It preserved sequential outputs but measured **−0.98% at one user and −8.70% at c64**. That was the older FP8 W8A16 MTP2-reuse recipe, not current R304/MTP1. The [negative result](../../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-w8a16-mtp2-local-argmax-r1-result.md) remains sufficient reason to leave it off unless a new profile establishes a relevant bottleneck. No Radiance boost attribution or new experiment is warranted from payload size alone.

**Draft-only head compression already exists here.** Radiance uses an [INT2 shortlist with reranking](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/radiance_drafthead.py#L1-L49); our accepted draft-only INT4 head already reduces draft weight traffic while keeping the full target head. Further compression is not inherently forbidden on the drafter, but it needs acceptance, complete-output and speed evidence. Source comments about empirical shortlist recall cannot establish exact target verification. Do not enable a target-head shortlist to obtain this optimization.

## Not applicable to this service

- **Shared GDN builds:** [the patch](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/patch_gdn_shared_build.py#L1-L19) targets multiple groups in the V2 worker's full-graph steady-spec path. Current V1 serving lacks that activation path. Its care to copy into each graph's original buffers is a useful lifetime lesson; blindly sharing one metadata object is unsafe.
- **MTP loop early exit:** [the inserted break](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/patch_mtp_loopbreak.py#L1-L36) skips later draft forwards. R304 already returns after the first pass at MTP1, so there are no later forwards to save. The accompanying controller also uses history n-grams and per-slot device-to-host synchronization; those are outside the selected measurement policy.
- **Multimodal mask compaction:** [the fix](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/patch_mtp_mm_mask.py#L1-L20) addresses rejected-token compaction with image placeholders. The restored service runs language-model-only, so this is a conditional future correctness fix, not a current speed opportunity.

Evidence classification remains source review of community-reported work. The inactive subtraction patch is a concrete follow-up artifact; native correctness and performance remain untested, and nothing in this audit changes the live package or its published metrics.
