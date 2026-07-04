# DFlash mixed-SWA revisit: multi-KV drafter blocker

Status: **blocked for this optimization cycle**.

Goal: make the DFlash drafter respect Qwen3.6's mixed attention pattern instead
of forcing the draft stack into all-full or all-sliding attention, then test
whether DFlash acceptance improves enough to beat the current strict Qwen27
record (`65.27648650325429 tok/s`).

## Why this matters

The current DFlash rows are not competitive:

- default/full-attention DFlash is valid but slow, roughly `50 tok/s`;
- `all-sliding` is valid but collapses to roughly `20.6 tok/s`;
- `mixed` is the semantically appealing mode, but it crashes before readiness.

The mixed mode is still worth keeping as a future lane because the target model
uses interleaved full/sliding attention. If the drafter's attention pattern is
wrong, acceptance and/or draft quality can degrade before any useful speed
comparison.

## Root cause

The target/main vLLM runner is already multi-KV-group aware, but the
speculative drafter path is not.

Mixed full/sliding draft attention creates multiple `KVCacheGroupSpec` groups.
The current drafter initializer asserts that every draft attention layer
belongs to exactly one KV-cache group:

- `/home/steve/src/vllm/vllm/v1/spec_decode/llm_base_proposer.py`,
  `validate_same_kv_cache_group()`;
- first failing assertion: `All drafting layers should belong to the same kv
  cache group`.

That assertion is not merely over-conservative. Several DFlash/EAGLE drafter
structures currently assume one group:

- scalar `self.kv_cache_gid`;
- one `self.block_size`;
- one `CommonAttentionMetadata`;
- one block table;
- one slot-mapping buffer returned for every draft layer;
- DFlash context KV precompute writes every draft layer using the same
  `context_slot_mapping`.

The main runner already loops over multiple target KV groups and keeps
per-group slot mappings/block tables, but it selects a single
`spec_decode_common_attn_metadata` for Eagle/DFlash based on
`drafter.kv_cache_gid`.

## Why not patch it quickly

Removing the assertion alone would be wrong. It would let the server start with
one group's block table and slot mapping applied to layers belonging to other
groups, which risks silent draft-cache corruption and invalid benchmark data.

The smallest correct patch is not a benchmark knob; it is drafter-side
multi-KV support:

1. replace scalar `kv_cache_gid` with `draft_kv_cache_gids` plus
   `draft_layer_to_gid`;
2. initialize draft `AttentionGroup`s per `(kv_cache_gid, backend,
   kv_cache_spec)`;
3. require equal block size for the first patch, or make the DFlash
   slot-expansion kernel block-size aware per group;
4. pass per-draft-group `CommonAttentionMetadata` from the runner into the
   drafter;
5. create per-group context/query slot mappings for DFlash;
6. update `DFlashQwen3Model.precompute_and_store_context_kv()` to select the
   context slot mapping for each DFlash layer's KV group.

This preserves target verification semantics, but it is a substantial source
change touching the generic speculative proposer, DFlash input expansion, and
model-specific context-KV writes. It needs its own isolated patch cycle and
startup smoke before any performance run.

## Decision

Do **not** spend more short-cycle benchmark time on DFlash mixed-SWA configs
until the multi-KV drafter plumbing exists. Treat these DFlash rows as closed
for the current Qwen27 decode-record cycle:

- full/default DFlash: valid, too slow;
- all-sliding DFlash: valid, much too slow;
- mixed DFlash: architecturally blocked by single-KV drafter assumptions.

Future work should either implement the multi-KV drafter patch above or return
to the current stronger lanes: exact LM-head/top-ID primitives, verifier
row/cost reduction, or accepted-tokens-per-step improvements under the strict
fresh-response gate.
