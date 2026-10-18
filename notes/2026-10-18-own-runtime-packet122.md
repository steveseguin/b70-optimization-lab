# Packet122: cutting draft time before the target halves

The CPU work is ready. The coordinator has three proposed files: two fresh
budget runs, two fresh runs of the HC change, and a one-load bracket that
refuses to start until both HC runs pass. All three files pass planning on
temporary queues. No GPU, service, live queue, power or memory setting changed.

The budget measures one whole draft step on packet118 bundle7 at 128 and 4096
occupied context. Its byte table covers all 47 actual draft event classes.
The 150 real hidden-state/token inputs are hash checked. The long cache fill
cycles those captures, so this is a diagnostic replay, not a natural 4K prompt.
Initialization, copies, restoration and comparisons stay outside event sums.
Every replay compares all mutable draft bytes. Measured times are still missing.

The chosen HC change gives each column's four streams to one subgroup and
computes their sigmoid products in parallel. It removes the shared-memory
barrier but preserves each arithmetic chain, reduction, BF16 rounding and
stream-order sum. The original exceptional-value expression is retained.
GNU and Intel each pass 16 byte cases twice; all four runs have the same full
output hash. Target arithmetic, full 16-bit KV, verification and the fixed 80,128-row
prefix stay unchanged. The closed draft load8, split-prefix and rank0 arms
were not reopened.

Both views and ranks pass full-size startup and five-view switching checks.
Four fresh reset checks and two fresh miniature protocol brackets pass, with
both draft schedules matching the unchanged parent's tokens and full state.
The resource-limit gate refuses a leaked CPU cap before native execution.
Ten micro-policy tests and 17 bracket-policy tests pass. The drain fix is present.

Each affected HC class and their sum must cut to <=0.8 production at both
contexts, in both orders, and in both fresh processes, with exact bytes.
The v5 job rechecks those hash-bound raw receipts; a saved pass flag is not
sufficient. The full bracket remains cold, checks every target token against
iq3-p49-split32-v1, and retains each arm's prompt acceptance. No gain is claimed.

The budget binary compiled first and shipped in 824bc2ddb. Source review then
caught an unrelated copied report callback; it was removed, the wrapper was
rebound and replanned, and the native binary stayed unchanged. Pull initially
refused unrelated dirty files; fetch confirmed HEAD==origin/main at c21b6000f.
Those files and all existing frozen packets were preserved.

Expected device time: about 2 minutes per micro process (1,200-second watchdog),
then about 15 minutes for v5 if qualified (3,600-second watchdog). These are
estimates. The final CPU receipt records combined build and free-space bytes;
all packet122 builds together remain below 250 MB and root free exceeds 25 GB.

- [Budget proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p122-draft-budget-B.txt)
- [HC micro proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p122-draft-hc-micro-B.txt)
- [Conditional v5 proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p122-v5-B.txt)
- [Fresh budget/roofline](../experiments/own-xpu-runtime/stage2/packet122-draft-budget/ROOFLINE.md)
- [Lever ranking](../experiments/own-xpu-runtime/stage2/packet122-draft-budget/LEVER-RANKING.md)
- [Candidate and CPU evidence](../experiments/own-xpu-runtime/stage2/packet122-draft-hc/README.md)
- [Final CPU receipt](../experiments/own-xpu-runtime/stage2/packet122-draft-hc/evidence/cpu-preparation.json)

The next step belongs to the device coordinator: run the budget and HC micros.
If any HC gate fails, close this arm; only an exact 20% micro win admits v5.
