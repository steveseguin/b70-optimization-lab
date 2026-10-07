# Controlled client checkpoint comparison

This conditional CPU plan compares two client checkpoint policies inside one
application, after packet 103 passes every full-suite and continuity quality
check and fresh disk admission passes. It does not modify the current runtime
or implement either policy. The runtime coordinator owns implementation and
source-bound policy readout receipts before any execution.

The numerical workload is unchanged: all ten original fixtures in order,
original seeds and prompts, accepted encoder window 64, native BF16 weights,
640×384, 25 frames, 8+3 steps, W2/B1, 23/25 sampler placement, sampler depth 2,
and decoder depth 2 with the existing replica. The new qualification basis
explicitly labels the client-policy comparison as non-numerical metadata.

[plan_reference.py](plan_reference.py) reconstructs the
[candidate-plan.json](candidate-plan.json). Twenty native requests create and
repeat independent references. Fourteen candidate requests emit ten comparison
clips. Fourteen control requests then emit ten clips under policy `always`;
fourteen fast requests emit the same ten-fixture workload under policy
`storage-change-only`. Each optimized block has four unscored fills. All raw
emitted tensors must match the same native references. No continuity phase is
included.

The only permitted difference is skipping a redundant rewrite of an unchanged
client storage ledger. Source/hash verification, fault and halt checks, fresh
free-space checks, budget accounting, all mutated ledger checkpoints,
request-attempt and completion durability, and event flush/fsync remain required.
Each plan row binds its policy. All setup, native, candidate, and control rows
use `always`; only `timed-fast` uses `storage-change-only`.

The standalone [schedule.py](schedule.py) seals nine setup requests and requires
a durable `control_verified` barrier before the first fast request. The future
runtime must finish control parity verification, drain and preserve completed
tails, and record the policy change before entering the fast block. Both timing
blocks remain in the runtime's timing authority phase; this is not a generic
continuation endpoint.

Each timing block emits one ordered ten-fixture pass. Both reuse qualification
inputs, and control always precedes fast, so this is a short controlled screen
with order effects still possible. Neither block is a cold-request measurement,
performance headline, record, or endurance result. The plan separately binds
both emitted blocks and requires a future source-bound readout of actual policy
and checkpoint/write counts.

The exact budget is **71 requests and 64 raw capture requests**, cap 64, with a
**5 GiB write allowance above a 50 GiB free-space reserve**. Names use
`resolution-client-20261007`; native indices are 99904000–99904019, setup capture
indices are 99904030/99904041, and candidate/control/fast indices start at
99904100/99904200/99904300. The coordinator must reserve these against current
state before execution. Success retains the application; faults halt requests
and never trigger automatic retry or restart.

CPU validation passed 16 plan tests and 12 schedule tests, including exact
control/fast graph equivalence apart from request names and clip indices,
policy-tamper rejection, and required control-barrier dependencies. Evidence is
in [cpu-validation.json](cpu-validation.json). Historical plans and the authored
103 runtime schedule remain unchanged. No GPU request, runtime build, or
namespace reservation was performed for this preparation.
