# Reuse a restored encoder across placement modes: source proposal

Status: source-only, not implemented or qualified. The recorded host OOM/xe
fault still halts native work. This is a separate future alternative to the
conservative replacement-loader v2; none of its files were changed.

The existing tensor objects can be reused after complete CPU restoration.
There is no numerical need to reload the checkpoint, rerun the encoder
constructor, change `assign=False`, or unload the video models. The current
ownership API does **not** safely support simply adopting that state into a new
group. Retirement prevents encoding but intentionally permits state APIs, and
there is no exclusive model-to-group lease.

## Pinned inspected sources

`P` is `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-host-embedding-11/source`.
Line numbers below for core files refer to this frozen packet, not the base
checkout. The packet's small-state extensions differ from base source; this
proposal leaves that option disabled, as the host adapter already requires.

| Source | SHA256 |
| --- | --- |
| `P/comfy/sd.py` | `41cbf195657cc81a60173f13f192966c4276bf7931a6c10f75870a66c59546b0` |
| `P/comfy/model_patcher.py` | `768d9b6f24b632dffba9e4c3c2d2962b3c309bf33182cf599d8c9abda2125d99` |
| `P/comfy/model_management.py` | `ef3f3af0657c1b022ad69b25928fa52dd429db9aed9cb688e89c7fbe68ab50cd` |
| `scripts/host_embedding_clip_v2.py` | `53d45d883bcc46d1a5889d3b6f162b0e95417e834c62dde8d8836791cffe2994` |
| `scripts/ltx_host_embedding_candidate.py` | `b58bf0bbfc084ea89f2673f3c10d9520b5f6ac1993517c79e346ea2c573ca7e9` |
| `scripts/test-host-embedding-integration-cpu-fixture.py` | `2fa5d3636afdc7f17fc5957916cc525fa935ff1181efc90dad8753860e69f79e` |

## What existing source proves

Native `CLIP(no_init=True)` returns before constructing the encoder (sd.py
239–242). Native `CLIP.clone` (309–318) makes this metadata shell and shares the
model/tokenizer. Static `ModelPatcher.clone` (427–504) also shares the model and
backups rather than copying parameter tensors. However it sets `n.parent=self`
(454), so repeating clones retains previous patchers and can grow parent chains.
It is not a weak-death replacement. Dynamic/deep-copy paths are out of scope.

`HostEmbeddingCLIP.adopt` (185–191) requires an exact native CLIP shell and
shallow-copies its metadata. A future private transfer factory could construct
that shell with the same restored static patcher/model/tokenizer, copying the
native clone's explicit CLIP metadata fields. It must not call `load_clip`, the
ordinary parameter constructor, `load_sd`, or a forced deep clone. Calling the
base `CLIP.clone` directly on a retired adapter would bypass its public retirement
check; this is not an acceptable general public shortcut.

Integration `detach_restore` (155–180) calls encoder detach, restores the table,
removes its retired host-container registration, removes state hooks and the
embedding observation hook, checks zero loaded bytes/CPU parameters/original
size, and retires the group. Standalone `HostEmbeddingOwner.restore` (203–217)
removes its ON_CLONE and ON_LOAD callbacks from every live registered patcher and
recomputes their sizes. **Standalone restore alone is insufficient:** it retains
the table registration in the old host container; integration lines165–168
remove that second registration. Old owner objects also retain ordinary strong
references to the table/delegate/parent even after becoming inactive. Those are
aliases, not additional parameter storage.

Retired wrappers' `clone`, `load_model`, and `encode_from_tokens` call the group
guard and reject (adapter107–120,193–236). Native ordinary encoding funnels into
those methods (sd.py342–430); scheduled encoding/generation encounter the
overridden loader before model execution, though they can reset model options
first (342–401,476–485). This is not a concurrent-use API.

## Required ownership changes before implementation can be safe

1. Introduce an explicit transfer generation and a single active lease for the
   underlying encoder model. Current `bind` (102–105) only checks model identity;
   two control groups can bind the same model. A private transition must consume
   one restored-owner token exactly once and publish the new group only after
   old-group retirement and all restoration checks succeed. Never clear an old
   group's `retired` flag or rebind its surviving wrappers. Failure stays sticky.
2. Add a distinct transferred/tombstoned state to old groups. `_state_api`
   (239–260) presently checks only `not active()`, so retired wrappers may still
   call `load_sd`/`add_patches` against the reused model. The existing CPU fixture
   (160–202) deliberately tests successful `load_sd` after retirement. Preserve
   that historical standalone-restoration contract; deny old state APIs once
   transfer is consumed, and test this separately. State extraction also needs
   an explicit boundary because returned state tensors can alias live weights.
3. Reuse a private native metadata shell and the restored static patcher, rather
   than repeatedly building parent-linked patcher clones. Pin the exact allowed
   CLIP fields, tokenizer identity/options, layer/schedule flags, patcher options,
   UUIDs, callbacks, and model identity. Check all surviving old bound clones:
   none may encode/clone/load/patch/save through its supported CLIP APIs after
   transfer. Preserve the native memory estimator and load/offload policy.
4. Keep loader bookkeeping explicit. `LoadedModel` holds weak patcher references
   and can fall back to a parent (model_management.py757–778). Direct
   `patcher.detach()` does not remove `current_loaded_models` records. Native
   `load_models_gpu` (946–976) reuses an exact patcher record and removes records
   sharing its model via `is_clone`; it does not make ownership-group exclusivity
   true. An old empty host patcher has a different model and may retain a loader
   record. Qualify targeted encoder/retired-host record cleanup, including
   finalizers and all old clones; never substitute `unload_all_models` or assume
   GC means release. No two records may account for the extracted table.

This can prove exclusivity for the supported, pinned CLIP workflow. It cannot
revoke previously exported raw tensors, `.cond_stage_model`, or `.patcher`
references: direct mutation bypasses CLIP guards, and inference tensors may have
no version counter. Do not claim protection against arbitrary raw-object users.
Either reject those unsupported consumers or require their release before
transfer; no existing registry tracks every such reference. A bare new group
without these boundaries is therefore not ready for implementation/admission.

## Memory and qualification boundary

The constructor review records 26,231,584,372 registered encoder bytes and a
52,495,358,666-byte checkpoint-plus-constructor working-set budget, not a measured
physical peak. Reuse avoids those *new constructor/checkpoint* allocations.
It does not eliminate the preceding CPU detach: up to 24,218,318,452 remaining
encoder bytes can still need CPU storage beyond the table. Keep the retirement
headroom gate and margin; do not credit swap/cache reclamation. Module/storage
addresses may change during CPU/device transfers, so require weight-byte and
metadata equality, not invariant pre-detach pointers.

Future tests must cover control→host→control→host, retained clones, stale transfer
tokens, overlapping groups, late mutations, observer/callback cleanup, and loader
records. Tiny actual CPU tests should count constructor/checkpoint invocations
(zero after initial construction), compare parameter/buffer bytes and original
embedding registration after each restoration, and verify save/load boundaries.
After independent review and host fault resolution, require bounded full native
conditioning plus all four clip oracles and memory observations on one persistent
application. No speed or memory-safety qualification follows from this source
audit. No native imports or tests were run for this proposal.
