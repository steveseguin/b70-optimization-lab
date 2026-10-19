# Packet150 shared-correction gate — closeout

<!-- campaign-closeout -->

## Question and identity

Does packet149's measured exchange cost satisfy the approximately **1 ms per
miss** gate for building the shared-correction prototype tonight?

Input is packet149's completed lane-B v5 on two B70 cards: packet136 banked
bundle8, arithmetic `iq3-p49-split32-v1`, unchanged target and BF16 state,
one load with off/xchg/off/xchg/off, twelve realistic prompts and 128 generated
tokens per view. Each view has 331 corrected halves. The probe performs 96
serialized exchanges per miss across the specified large attention and
routed-expert projections while retaining all original rank0 computation.
The source window completed on October 18; this review used CPU only.

## Outcome

**Gate failed; do not build part (a).** The two measured exchange costs are
**7.685005539 and 7.697146022 ms per miss**, mean **7.691075780 ms**.
No shared-correction prototype, smoke proposal, on/off proposal or shared
readiness marker was created. The separate rank0 split handoff stays sealed.

The three control means are 11.808600906, 11.801620846 and 11.803889728 ms;
their mean is **11.804703827 ms**. Probe means are 19.489709366 and
19.501849849 ms. For each probe view:

`E = probe corrected-half mean − mean of the three control means`

The controls span only 0.006980060 ms; control decode-rate drift is 0.038345%.
Both observed costs independently exceed the 1 ms gate.

Let G be gross saved compute and A be additional assembly/peer-compute/draft
interference beyond this surrogate. Then `net = G − E − A`. A 2–3 ms net cut
would require **G ≥ 9.691–10.691 ms + A** at the measured mean E. This is a
cost requirement, not a prediction or measured optimization. No interval rate
or performance curve is extrapolated from it.

## What worked

The real packet149 report loader validates the complete window, unchanged
oracle outputs, per-prompt acceptance and draft proposals, reset/isolation,
artifact hashes and teardown. All five views have 331 corrected halves; each
probe correction has exactly 96 exchanges. Source files were hashed before
and after the read-only validation and did not change.

## What failed or remains uncertain

The registered exchange schedule is too expensive for the owner's build gate.
It is a serialized surrogate with no peer matrix computation, not a shared
implementation. It neither proves an unavoidable communication lower bound nor
measures an expert-only, coalesced or overlapped schedule. No subset cost is
inferred by dividing the measured total. Device parity and speed of a shared
implementation are untested because none was built.

## Evidence and patches

- [Decision and exact numbers](decision.json).
- [Read-only validation and derivation](decide.py).
- [Original summary snapshot](evidence/bracket-summary.json.txt),
  [completed window snapshot](evidence/window.json.txt),
  [identity snapshot](evidence/identity.json.txt), and
  [teardown snapshot](evidence/run-teardown.json.txt).
- Original device evidence remains at
  `../../packet149-shared-correction-probe/v5/evidence/device-xchg-v5-B/`.
  The snapshot records retain those source paths and byte hashes. Their embedded
  historical paths are provenance, not active packet150 runtime dependencies.

No native patch was made for this branch. No device was run, retried or stopped
by this review. All earlier evidence and the two-card record remain unchanged.

## When to revisit

Require a newly specified schedule with its own matched in-engine exchange
measurement at or below the owner's approximately 1 ms/miss gate, and enough
compute savings left for a 2–3 ms net cut. Any expert-row split must retain
whole-row FP32 reduction order and pass the unchanged target oracle. The
current 96-exchange measurement cannot qualify a different schedule.
