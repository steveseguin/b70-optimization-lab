# Packet49c independent kernel review

Reviewed 2026-10-17 against the unchanged packet49b sources and packet51's
qualified route/HC/attention candidates. This was a source review: no compile,
model payload read, GPU execution, service action, or oracle action was performed
by the reviewer. Build and executable gate results belong to the packet's CPU
receipts, not this review.

**Outcome:** no unresolved source-level kernel blocker after the corrections
below. Fresh packet49c device byte gates and the shared-oracle model gates remain
required. Packet51's timing is not a packet49c model speed measurement.

## Corrections found during review

1. An HC gate dispatch block had also been inserted into `prepare_commands()`'s
   family classification. It referenced nonexistent local matrix/card variables
   and would have bypassed preparation. The duplicate was removed; the intended
   dispatch remains in `Engine::linear()`.
2. The operator fixture originally included attention split4 workspace in its
   cross-backend output hash. Device execution writes those partials while the
   existing host implementation keeps them local, so equal model outputs would
   still fail host/device hash admission. The fixture now excludes only that
   workspace from the canonical hash and explicitly records this exclusion.
   It continues comparing the entire workspace byte-for-byte against the
   baseline on the same backend. No kernel arithmetic was changed for this fix.

Both corrections were re-read in the source before this review was recorded.

A subsequent integration review found the direct HC gate fixture used only four
output rows. A focused follow-up review confirmed the correction to the actual
Q8_0 K=320, 10,240-output-row shape from `hc_attn_up`/`hc_ffn_up` in the model
directory. Its eight scenarios still run at M=1 and both M=2 rows, retaining 96
total fixture cases. This is a fixture coverage correction only; the production
kernel, wrapper and engine sources retain their reviewed hashes. The final
fixture hash below supersedes the earlier four-row fixture identity.

## Integration and arithmetic

- `p49c_kernel.hpp` from the route comment through the final dense template is
  identical to packet51 `candidate.hpp` after replacing the namespace/error-label
  spelling and `p48::load32` qualification. The local `load32` body is identical
  to packet48's helper. Excluded expert/QKV/inject candidates were not copied into
  the production dispatch.
- Routing retains four passes, the adjacent 16-value exponential reduction, the
  original denominator reduction, normalized floating-point division before
  ranking, index tie-breaking, gather descriptors, and the global scratch layout.
  Local caching changes repeated reads, not the comparisons or floating-point
  operation sequence.
- HC low keeps Q8_0 K=10240 split4, its per-lane product/add order, the same
  four-part tree and BF16 boundary before the original SiLU/div4 epilogue.
  HC gate keeps Q8_0 K=320 split1 and no epilogue. The production gate baseline
  is `p33.dense.segment`; its aligned eight-value lane arithmetic is the same
  as the inherited p28 arithmetic used by the operator fixture. The complete
  engine fixture explicitly uses the p33 baseline.
- Attention keeps Q6_K K=6144 split4, original global partials, the same final
  addition tree and BF16 boundary, and the original four residual updates. Its
  cached injection factor has exactly the original expression. Position checks
  are unchanged: the inherited attention epilogue admits position independently.
- `p49b_gemv.hpp`, `p49b_expert_submit.cpp`, `p49_qsa_submit.cpp`,
  `p39_submit.cpp`, `p39_fused.hpp`, and the inherited dispatch file are unchanged
  from packet49b. The existing p48b expert gate/up and down paths remain;
  packet51's expsgate, GDN QKV and HC inject proposals are not enabled.
- All real resident route calls reach the new route wrapper. Tagged HC a/f low
  and attention calls reach the new dense wrapper; both HC a/f gate calls are
  intercepted before the old ordinary dense dispatch. Miniature and streaming
  paths retain the baseline. The production small-group handling does not absorb
  these calls: HC lows already carry their epilogue tag, and gates are not
  members of the HC low/inject group.
- Prepared command capture calls the same `execute_site()` dispatch. Target
  verification continues to run its two rows serially through the same engine
  and `rank.hpp::half_step`; there is no row-zero-only branch. The newly selected
  calls therefore apply to M=1 and each M=2 row on either rank.

## Ownership, bounds and oracle

The dense wrapper validates the existing p28 matrix identity, extents, alignment,
memory kind, and read/write aliases before submission. Fused low and attention
calls additionally use p39's complete pointer-range/alias checks and validate
tail extents. Gate controls are live device allocations with checked lengths,
alignment and aliases. The route wrapper preserves packet51's live allocation,
extent, output alias, scratch and control checks, including the intentional
production repeated error/active input bindings.

The new kernels allocate no arena buffers. HC partials and route/attention
caches are workgroup-local; attention reuses the existing GEMV workspace.
The two attention submissions and four route submissions retain explicit event
dependencies. Existing transaction rollback and ownership code is unchanged.

`oracle-binding.json` is the unchanged packet49b binding to
`iq3-p49-split32-v1` and the packet49 oracle binary/source receipts.
`shared_oracle.py` retains static hash validation and completion validation;
the changed text only identifies packet49c. Reusing that oracle is justified by
the unchanged arithmetic, but does not waive completion or fresh model checks.

## Reviewed source hashes

| File | SHA256 |
| --- | --- |
| `main.cpp` | `218bede1d36966be478063cb6d50b3e693497ff59992ecf72de6137454d21d1a` |
| `p49c_kernel.hpp` | `2577620fc19fc83637279523ce2aa73eccd58e862f5a4f7bb149a06666f4641b` |
| `p49c_submit.cpp` | `2faeb6560dca467a4bdf3f93f1dfa93dd137b58b9b16db923bfa6ea3afa459e3` |
| `p49c_fixture.cpp` | `314b574eb1c7a7e1eb3f2a12be8a67210a90f2f35fa94c1509d59b5099cae176` |
| `p49c_engine_fixture.cpp` | `8f781041259ef74e89f68ad11da6db56efd31ba02794924cb8139600ba77b4fe` |
| `oracle-binding.json` | `3c270c8b3734ee5782875d8c1eb505dcc3d21adcc4cc66e96d7e8fb9960789c1` |

Later changes to these files need a focused follow-up review. Queue switching,
disk admission and final seal validation are covered separately.
