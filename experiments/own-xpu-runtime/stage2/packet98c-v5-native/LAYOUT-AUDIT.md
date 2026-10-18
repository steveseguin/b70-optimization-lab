# Packet98c switch boundary

The engine is copied from packet97's checked bundle sources. The v5 wrapper
is copied from packet98. Neither parent is edited. `source-copy-provenance.json`
records the originals; only absolute include roots are relocated in `sources/`.
Native additions live in `native/` and `native_source.py`.

| Dimension | Load and dispatch evidence in packet97 | Decision |
| --- | --- | --- |
| Route | `p49d_submit.cpp:resolve/site` selects route-exp32-rank4 or route-fast. `main.cpp:load` has no route-dependent weight transformation. Both bind the existing route buffers. | Switch these two registered kernels. UI production means route-exp32-rank4. |
| Recurrence | `p49d_submit.cpp:recurrence_validate` checks the same 19 allocations; rows4-shared, rec-parallel and rec-both-plus use the same BF16 state. `main.cpp:load` does not inspect recurrence. | Switch all three; rec-parallel is the decision's baseline. Raw `production` is rejected by the frozen selection parser. |
| HC gate | `main.cpp:submit_hc_fused` passes the wide flag to `p60::submit`; production and wide read the same weights. Only hc-weightcache changes `p90_hc_weight` and load conversion. | Switch production/wide only. Keep HC mixing and HC norm fixed. |
| Draft attention | `mtp.hpp:bind` selects implementation 12 for qsa_attention=packet59; otherwise dispatch chooses 5. Constructor buffers, weight loads, head and KV extents are identical. | Rebind draft prepared specs and recapture every draft command at context extent 32. No stale attention capture. |
| Experts | `main.cpp:p90_expert_weight/load` changes expanded extent and performs expert_repack for half-cache. | Fixed, including wide64 in proposed brackets. No expert selection switching. |
| Head/dense | `packed_weight`, `load` and draft constructor change byte layout, allocation size or shared-prefix ownership. | Refuse any change. |
| Other draft choices, host retirement, miss banks, placement | Not part of this qualified native switch; some alter loaded state or constructor-only fields. | Refuse changes; fixed rank1 draft, 24/24, BF16 KV. |

Switching drains work, checks target and draft quiescence and rejects unsupported
choices before modifying selection. It then recaptures target commands for both
recurrent banks. `request_reset` clears every non-weight device allocation,
including KV tails, recurrent banks, speculative backups, scratch and draft state.
Pinned target slabs and draft publication/staging buffers are cleared explicitly.
Draft captures are rebuilt after the reset. Allocation IDs, sizes, categories,
lifetimes, pointers and live flags must remain identical. Weight uploads are
forbidden after loading. Descriptor equality alone is not a weight-byte proof:
the miniature poison test separately hashes actual weight and mutable bytes.

Full-shape tests must verify real binding/capture and complete reset extents for
both ranks. Miniature protocol tests compare each switched view to a fresh
packet97 v4-style process and repeat the bracket. These are CPU proofs only.
Every device view still needs incident64 plus all twelve oracle requests exact,
cached_tokens=0 and unchanged acceptance. Draft split32 has its own reduction
order: equivalence is to that same selection in v4, not a new quality waiver.
