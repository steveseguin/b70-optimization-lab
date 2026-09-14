# Prospective zero-cost acceptance v2

The [new task](../../../../../worker/tasks/ml-zero-electricity-cost-v2.json)
adds browser cache-stamp and numeric-control validity requirements. Its
[gate](../../../../../worker/acceptance/ml_zero_cost_v2.mjs) imports the unchanged
v1 behavior check. All model runs in the two overnight packets used v1.
No model requests or generated-patch repairs were made for this v2 verification.

The [verification receipt](verification.json) records four host-CPU checks using
Node v18.19.1, with exact source commit, rejected-patch hash, fixture hashes and
stdout/stderr hashes. This is not a new sandbox or model trial.

| CPU case | Expected and observed result |
| --- | --- |
| Original pinned source | Reject: SDK zero cost is wrong |
| Exact thinking-profile zero-cost patch | Reject: behavior passes, browser cache stamp is stale |
| Manual fixture after stamping only | Reject: numeric controls exclude zero |
| Manual fixture after stamping and setting both existing minima to zero | Pass |

The source is ML Bottleneck commit `8df1372c4f20fc8ae0bf4e35e1b75084327b17fc`.
The retained rejected patch is in the [initial screen](../../2026-09-14-profile-screen/README.md).
To reconstruct the manual gate fixture, apply that exact patch to an ordinary
source archive, run the repository's `node scripts/stamp-engine.mjs`, then set
only the existing `hoursPerDay` and `costPerKwh` input minima to zero. From that
source copy, run Node with the absolute path to `worker/acceptance/ml_zero_cost_v2.mjs`.
The fixture is an artificial gate check, not a model-produced patch, accepted
worker task, or merge candidate. Original source and frozen task workspaces were
never edited.

The original fake DOM tests calculations but does not implement HTML constraint
validation. Typed or stored zero already calculates correctly in the corrected
v1 patches, although the controls mark it out of range. V2 closes that separate
UI gap without changing historical acceptance counts or the thinking patch's
stale-cache rejection. The static checks cover these two known number inputs;
they are not a general HTML parser or substitute for browser testing.
