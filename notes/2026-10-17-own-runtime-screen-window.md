# October 17: one-load screen preparation

Prepared a new diagnostic wrapper in
[stage2/screen](../experiments/own-xpu-runtime/stage2/screen/README.md).
It reuses packet 56 and packet 58 sealed engines and dispatches. No native
build, GPU work, service action, model payload read, large pin, host setting
change or cleanup ran. Packet 57 and packet 58's coordinator work remain
protected. Work is on `main`; pull was clean and already current at entry.

The two-card worker holds the same rank pair through a 64-token incident
check and the full 12 × 128-token suite, resetting state between requests.
Every token is compared to the existing packet 49 oracle. The unchanged WS128
metric implementation reports class-balanced and all-prompt rates, TTFT,
acceptance and hit/miss cycles. Outputs are diagnostic `screen`, never an
independent submission. There is no cooldown inside the lifetime.

Packet 58's sealed native interface has a hard twelve-request limit and one
global token cap. A separate 64-token request plus twelve 128-token requests
is impossible without a new binary. The owner was asked about the compatible
prefix alternative during preparation. The prepared `--incident-prefix`
option makes that deviation explicit: check the first 64 tokens of the first
suite response from flushed timing rows, then compare every token of all
twelve responses. Without the flag, one-card screen refuses. The prepared
command selects this alternative; it does not claim a separate 64-token request.
One-card MTP statistics are not applicable. No device command was run.

Safety reuses the inherited fault supervisor and PF_EXITING handling, the
54/56 offline contract, closed environment, past-UTC fault review, storage
admission and cooperative stop. Native teardown receipts are required.
Locks, latches, caches and outputs stay in the new folder. Future compatible
candidates can supply their own sealed binary and dispatch. The new lean
seal binds a build plus one exact-byte fixture instead of rerunning all CPU
campaigns. The owner's GPU-first fix loop is documented in
[LEAN-CPU.md](../experiments/own-xpu-runtime/stage2/screen/LEAN-CPU.md).

Measured WS128 windows were 191.054198 s (49d) and 188.508088 s (56), from the
retained queue start/stop receipts. KD receipts lack explicit elapsed fields;
use the brief's approximately four-minute measured-window report, not their
old planning constants. Together they support a conservative **7–8-minute
two-card estimate including load**, with load counted twice in that sum.
The under-15-minute target still needs a coordinator measurement. There is
no measured one-card estimate. Exact commands and safety limits are in the
[screen README](../experiments/own-xpu-runtime/stage2/screen/README.md).

CPU checks cover token mismatches through token 128, 99-interval metrics,
class balancing, complete-suite membership, the persistent two-card request
sequence, seal tampering, closed environment, review boundaries, memory
fence, PF_EXITING, and cooperative fault handling. Both existing seals and
the packet 49 oracle pass read-only `--plan` checks. Final test counts and
source hashes are retained alongside the screen code.
