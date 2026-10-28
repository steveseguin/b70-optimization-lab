# Explicit-local address-space candidate — not installed

The coordinator's combined actual-route gate and matched event timing passed.
Canonical runtime remains on the previously qualified generic-pointer r4
candidate while its independent CPU model comparison completes. No canonical
files or active source pins were modified by this experiment.

The helper templates retain the local pointer type for probabilities, indices
and frame storage. Frame fields are accessed explicitly; sort comparison and
operation ordering are unchanged. The caller requests decorated local pointers.
This removes the compiler's 321 generic-address control-flow warnings, reduces
MERGE=true machine code from 167,488 to 125,952 bytes, and leaves reported private
space unchanged at 1,024 bytes per SIMT thread. The same-run untied timing cost
versus the original route is 3.3% at one row and 4.6% at 64 rows; all-equal stress
still costs about 21–22 times the original route. See `result.json` and the
parent `timing-and-next-step.md`; these are kernel measurements only.

All twelve full-gate output/probability artifacts match the r4 artifacts bitwise.
The 12,512-case host ASan+UBSan gate and the device's complete 512-probability,
selected-weight, ID/route, capture-neutrality and refusal checks passed. The
full gate covers MERGE true/false, two/four output geometries and 64-row batches.
The source-only experiment is complete; no more kernels or GPU runs are planned
for this lever before model quality is resolved.

## Exact handoff after independent CPU quality

Files are in `/dev/shm/sc117-reference-route-addressed-20261028-r1/`; proposed
installed directory is `engine/src/stage2/packet194-expert-diet-engine/`.

| File | SHA-256 |
|---|---|
| `adapter.cpp` | `09de30d6253e51d905b60034c85116f6c593a89a1ae0e057f058c24c2e03bb4e` |
| `reference_sort_addressed.hpp` | `5eeb624c44f4e881630a1c50bea91b43c61a3b43715d1e7c635beab1c9269710` |
| `reference_sort.hpp` (unchanged dependency) | `17815205b889ada9b104865eb47c7a0f4e602aae701d75c637b5ccc83cbd542c` |

`adapter.patch` is the exact delta from gated r4. Keep the prior workspace helper
and original experiment records as history; no deletion is required. The sole
runtime treatment remains `OWNRT_REFERENCE_ROUTE_TIE_SORT=1`, absent/0 off.
Unsupported enabled route modes still refuse. `prepare.py` reconstructs this
overlay from the pinned r4 fixture without touching canonical files.

Before promotion, run the existing seven-request historical Phase A as one
changed-risk model gate, using the same native compile/link policy and comparing
against the authenticated r4 Phase A artifacts. Reuse that harness unchanged
instead of inventing a smaller test runner. Its essential coverage includes:

1. Cold historical 244-token request: exercises the position-177/layer-3 cutoff
   replacement and compares final logits, output tokens and complete state to r4.
2. Cold historical 527-token request: exercises the additional cutoff and internal
   selected-order swap, plus more than one 256-row prefill chunk; compare the same
   artifacts to r4.
3. Repeat the cold 244-token request after the 527-token request: require exact
   state/output equality and the existing reset/drain receipts.

This is one existing qualification sequence, not a restart chain.
Bind all unchanged compiled sources, runtime settings and logical input identities
to r4. Require byte-exact state, logits and token parity for this address-only
change; a difference is an unresolved failure, not a reason to relax tolerances.
Once the current independent CPU check has passed, reuse its reference evidence
through the exact r4 parity link rather than rerunning independent CPU references
without a changed risk; do not repeat the twelve free-generation requests merely
for this address-space-only change if Phase A and the actual-route gate are
bitwise exact. This remains the existing target-only qualification
scope; it does not newly qualify MTP serving or establish endpoint throughput.
