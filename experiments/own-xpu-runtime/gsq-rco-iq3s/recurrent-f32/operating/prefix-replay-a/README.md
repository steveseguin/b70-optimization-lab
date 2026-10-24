# First-divergence shared-prefix replay

This is a single diagnostic request using unchanged corrected engine `5926a247`.
The closed longer-run review `d986a765` independently found the first difference
at output index 70: native token 220, CPU token 264. The input is the original
87 raw prompt IDs plus the 70 matching CPU output IDs, exactly 157 raw IDs.
Startup remains `--max-new 128`; the actual target-only RPC requests one token.
There is no template, MTP request, arithmetic change, compilation, or speed claim.

The request must reproduce native 220 before its captured final logits can be
used to localize that earlier disagreement. A different result is retained as a
failed diagnostic; it is not substituted into the original evidence. CPU 264
remains the independent reference and the quality hold remains in effect even
if this diagnostic passes. Query position is 156; the resulting committed token
position is 157. Source rationale is retained in
[shared-prefix replay appraisal](../../reference-longer-plan/SHARED-PREFIX-REPLAY.md).

The inherited one-pair coordinator, physical-contact monitor, fault stop,
RetainedOwner handling, and normal close remain unchanged. One full RESET,
one target request, explicit DUMP/repeat, and FINISH retain two capture groups:
640,127,112 raw bytes, plus the standing 128 MiB metadata allowance and 2 GiB
external floor. Initial external admission additionally reserves 128 MiB:
3,056,046,216 bytes. Initial root admission is 27,268,435,456 bytes; ongoing
root floor plus cache allowance is 27,134,217,728 bytes. Acknowledged capture
remaining bytes are 640127112 → 320063556 → 9699332 → 0. These are payload
forecasts with separate reserves, not quotas or guaranteed completion at the
exact free-space threshold. HOME is inherited without replacement.

`authority.json` binds the actual safely closed mismatch and CPU readback.
A source review is required before `once.py --plan`; only the root coordinator
may admit and run that plan. The focused mocks exercise actual RPC serialization,
source-bound prefix derivation, acknowledgements, failed RESET, and failed native
reproduction. They do not execute an Engine, GPU, or model. No actual run has
been performed by this preparation.
