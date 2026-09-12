# GDN fresh one-token routing review — 2026-09-12

**Confirmed on current upstream at the CPU metadata level; already tracked by
issue #51562 and open PR #51565. Recommend contributing evidence there, not a
duplicate issue or competing minimal patch.**
This is not a current-upstream GPU reproduction or a downstream promotion.

Source: vLLM main `22f6e4eccb674b534f62810c66838317169b6b98`, resolved from the
GitHub commits/main API on September 12. Downloaded raw source snapshots and
SHA256 values are retained in `source/` and `source-manifest.json`.
The snapshots are upstream Apache-2.0 code, retained with original headers.

## Actual defect and smallest fix

`vllm/v1/attention/backends/gdn_attn.py:251` calls
`split_decodes_and_prefills(m, decode_threshold=1)` with the default
`treat_short_extends_as_decodes=True`. A real request with one scheduled token,
`is_prefilling=True`, and no computed context is therefore classified as a
decode. Fresh prefills require state initialization; decode kernels assume
existing state.

The current shared GDN forward supports the required semantics already:

- `gdn_attn.py:399` builds initial-state masks from computed context for prefills.
- `qwen_gdn_linear_attn.py:1373` calls the convolution prefill path with that mask;
  the decode branch at line 1391 calls `causal_conv1d_update` without it.
- `qwen_gdn_linear_attn.py:1526` selects and zeros fresh prefill SSM states;
  the decode branch passes existing `ssm_state` to the recurrent update.
- The general `KVBlockZeroer` in `worker_utils.py` explicitly skips Mamba layers.

The attached `gdn-short-prefill.patch` adds
`treat_short_extends_as_decodes=m.is_prefilling is None`. It is the same semantic
fix as the September 9 maintainer follow-up, ported to current source with a
shorter comment. It does not change the shared split helper's defaults, kernels,
precision, sampler, speculation verification, or model weights.

## Executed regression

Run:

```bash
/home/steve/.venvs/vllm-xpu/bin/python experiments/qwen38-27b-b70/upstream-review-20260912/phase/test_phase.py
```

`results.json`: **five of twelve candidate-routing expectations differ on stock; twelve of
twelve match the bounded local patch**. The test executes the AST-extracted actual helper
and actual GDN call from the retained source files, using real CPU torch tensors.
It does not replace the helper with a model of its behavior. It also does not
import or execute the full metadata builder, GPU kernels, graph replay, or model.
Only fresh-one, fresh-many, and decode-fresh establish incorrect routing.
Chunk-final-one can validly run decode because it already owns state. The mixed
short/long/fresh case merely changes where the prefill boundary starts: its fresh
request is already in the prefill tail on stock. Those two are regression-scope
differences, not additional bugs.

## Scope and regression review

- Fresh one-token prefills route through initialization after the patch.
- Continuing one-token decodes remain decodes.
- A final one-token chunk of a longer prefill becomes prefill; its computed
  context is nonzero, so the existing mask preserves its state. This may change
  numerical execution/performance for that chunk and requires device CI.
- Mixed reordered batches retain the decode-first split. Current upstream
  explicitly builds a prefill-tail mask and rebased cu-seqlens for this case.
- Decode-only graph padding `[1, 0]` remains classified as two decode requests.
- Metadata-less draft/capture calls retain legacy behavior. This is compatibility,
  not proof that every possible metadata-less fresh request is safe.
- The non-null speculative-mask branch is unaffected: current source reclassifies
  all non-spec one-token rows as prefills when spec decodes exist. Zero actual
  draft tokens reset that mask and correctly enter the patched branch.
- The fix is in shared code, not Intel-specific. NVIDIA/ROCm GDN implementations
  may benefit, but no device or graph regressions were run here. CPU classification
  is portable; current GPU symptom and graph compatibility remain unmeasured.
- The helper requires reordered batches. This patch does not repair callers
  violating that contract or general Mamba state clearing.

## Historical device evidence, separate from today's test

The September 9 maintainer packet is at
`community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/priority-20260909/README.md`:

- vLLM `0.27.2rc1.dev77+gac7509e2b`, kernels
  `1e90ffa672ba02f17a909da11838a4c55b199783`, two B70s.
- Compilation-disabled, MTP-disabled control: three of 24 tiny/mixed probes failed
  with repeated exclamation output. The same control plus phase guard passed 24/24.
- Two fresh compiled MTP servers passed 96 more probes and both full strict suites;
  all 12 complete normal-suite token arrays matched baseline and each other.
- Follow-up `validation/target-oracle-20260909.md`: two fresh compiled target-only
  strict runs and 96 further probes passed; all five target/repeat/MTP comparisons
  were 12/12 exact.

Those are historical matched-image B70 results, not tests of the September 12
upstream revision. They support the stale-state explanation but do not identify
every possible source of a user's long-session incident.

Provenance: this phase guard is lab maintainer follow-up. The distinct uniform
classifier fix belongs to allenzz-dev, with R50 adaptation/incident material from
dominick253; do not credit them with this separate delta or claim this fixes their
multi-hour incident.

## Duplicate check and recommendation

Read the full issue/PR bodies and PR #51565 diff; retained in `related-issues.json`
and `pr51565-files.json`:

- [#51562](https://github.com/vllm-project/vllm/issues/51562) reports this exact
  stateless first-chunk stale-read mechanism.
- [#51565](https://github.com/vllm-project/vllm/pull/51565) is open and fixes it.
  Its state-aware predicate preserves resumed one-token decode, excludes zero-query
  padding, and updates FULL graph metadata staging. Our old phase-only patch is
  a bounded local fix, not preferable as a universal upstream replacement.
- [#53051](https://github.com/vllm-project/vllm/issues/53051) and
  [#53059](https://github.com/vllm-project/vllm/pull/53059) concern runner-level
  shape-aliased FULL graph dispatch, a separate stale-write bug. Fixing only that
  dispatch does not fix this builder stale-read defect (historical failure also
  appeared without compilation/MTP).
- [#55516](https://github.com/vllm-project/vllm/pull/55516) addresses partial final
  speculative groups at max-model-len, not fresh non-spec initialization.

**Do not create another issue or submit the local phase-only patch as the final
shared-backend fix.** Add a focused independent-evidence comment to #51562/#51565,
with source pin and historical B70 evidence. Current CPU classification and source
consumer audit strengthen the report; historical B70 A/B gives device evidence
for a different patch on an older runtime, not validation of PR #51565.

The existing upstream PR handles a real gap our twelve-case local test does not:
a mixed fresh-prefill batch with trailing zero-length graph padding must exclude
that row from prefill chunk metadata. The simple phase patch leaves the splitter
counting trailing padding as prefill. It also does not update FULL graph staging.
Thus this packet does not approve downstream rollout of that simple patch onto
all graph configurations. Downstream promotion still needs the maintained recipe
rebuilt and model/device gates; no GPU work or production changes occurred here.
