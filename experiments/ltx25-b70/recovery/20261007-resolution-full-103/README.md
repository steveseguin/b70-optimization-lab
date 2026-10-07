# 640×384 full-suite qualification and bounded continuity

This CPU plan extends the W2/B1 workload to all ten original fixtures, in their
original order: boat, marble, bird, pendulum, rain, paper, candle, pour, fabric,
and wheel. Each retains its original prompt, seed, and accepted encoder window
64. BF16 weights, 23/25 placement, 25 frames, 8+3 steps, sampler depth 2,
decoder depth 2, and the native/replica decoder arrangement stay unchanged.

[plan_reference.py](plan_reference.py) reconstructs
[candidate-plan.json](candidate-plan.json) from the pinned original graph and
fixture sources. The constructor source remains packet 99b; packet 102 is the
reviewed experimental predecessor. No historical plan was edited.

The plan contains twenty native requests: two independent serial passes of the
ten fixtures. Fourteen optimized candidate requests then emit ten comparison
clips, after four unscored fills. Forty-four requests in one timing phase emit
forty comparison clips, also after four fills. All emitted clips must match
their independent native reference across all four captured tensors.

Timing scopes are explicitly separate. Emitted clips 0–9 cover one complete
suite; clips 10–39 cover three additional passes without a phase reset. The
plan binds each scope to exact request names and records each emitted suite
pass. These inputs have already appeared during qualification. Neither scope
is a cold-request measurement or performance headline; thirty additional clips
provide bounded continuity evidence, not an endurance claim or longer video.

[setup-schedule.json](setup-schedule.json) contains nine setup requests. The two
sampler workers are separately pinned and captured at indices 99903030 and
99903041, with admission and retirement actions after each capture. Setup
capture depth stays 1. Both workers must qualify before optimized comparisons.

There are **87 submitted requests and 80 raw capture requests**, with an exact
capture cap of 80. The twenty native, fourteen candidate, forty-four timed,
and two setup captures account for all 80; the other seven setups write no raw
capture. The planned write allowance is **7 GiB**, conditional on fresh storage
admission and preserving the **50 GiB** free-space reserve. Request names use
`resolution-full-20261007`; the coordinator must reserve the namespace against
the current evidence tree before execution.

A successful campaign retains the application for authorized follow-up. Faults
halt new requests. This plan does not authorize automatic retry, restart chains,
host power changes, or host memory, swap, or page-cache changes.

CPU validation passed 15 plan tests and 11 schedule tests. Counts and source
hashes are in [cpu-validation.json](cpu-validation.json). No runtime packet was
built and no model request was submitted while preparing this folder. Native
and optimized runtime qualification remains to be performed.
