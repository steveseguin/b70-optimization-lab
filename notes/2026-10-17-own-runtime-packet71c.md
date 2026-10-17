# Packet71c: repair the router configuration before the depth-two screen

Prepared on steve-b70s, October 17, CPU only. Packet71b is frozen and copied
into [packet71c](../experiments/own-xpu-runtime/stage2/packet71c-depth2-engine/README.md).
The original smoke-B rank-0 failure was the standalone-router refusal; rank 1
reported its peer failure. The supplied incident had no GPU fault.

The cheapest bounded repair is option (b). Change only the candidate dispatch's
`fusions.small.ffn` from `p30.small.rows4` to `packet18`. This stops grouping the
router with shared projections, enabling the existing M=2 router. The separate
shared projections keep their exact arithmetic; other epilogue settings remain
unchanged. Production/control still use packet64's existing sealed
`1-draft-hc-batch` view, dispatch and binary. All native runtime sources and
kernels in 71c remain byte-identical to 71b. No new target arithmetic is introduced.

The old claim that the shared-up epilogue prevented a tuple was false for the
production plan. Imports alone could not catch it. A new full-shape CPU mock now
calls native option parsing, Engine configuration, actual target allocations,
prepared commands, draft setup, both candidate rows, rank-0 future rows and
`Rows::capture_pairs`. All 48 router sites are checked. Only backend execution
and weight payload reads are replaced; target/draft payload entrypoints are
blocked. The negative control uses the old dispatch and reproduces the exact
router refusal before any device access.

Five views pass both ranks: smoke, candidate, all-M1 diagnostic, control and
control repeat. Their real allocation censuses pass existing memory admission.
Each direct and queue `--plan` also runs the hash-bound mock for that selected
view and imports the actual worker/deferred runtime in the closed launch
environment. Eleven wrapper/import tests pass, including actual temporary lane
leases and post-drain release behavior. The memory note's rule is preserved in
`ops/review-log.md`: plans must exercise real startup paths; the standalone
memory note was not present in the available Codex memory directory.

GNU and Intel each pass **2,728 M2 byte checks plus 80 new full-shape checks**
comparing grouped versus standalone router/shared gate/shared up/shared scalar
outputs. Both Q6 and Q8 shared-expert formats, two independent rows and five
input patterns are covered. Expected and actual streams agree across compilers.
The new 80-check stream hashes to
`0bc7fd7305c8cd9cd0f713cb68d33ef4857972c5b27d10922e8a842ea2aa9ada`.
Both host and device builds pass; the device binary was compiled, never run.

Both candidate and all-M1 seals pass. The four proposed lane-B jobs—smoke,
control, candidate, control repeat—pass the real queue planner on a temporary
queue copy. Only `ops/lane-queue/proposed-p71c-B.txt` was created in ops; the
live queue and every existing packet/shared screen remained untouched.
Estimated durations remain 3/4/4/4 minutes, with 3,600-second watchdogs and no
retries. The candidate prepares 72 extra target commands per rank compared
with control; whether batched work covers that cost is unmeasured.

No GPU, model, service, sudo, reboot, kill, power, host memory, swap or page-cache
change occurred. Builds ran sequentially at nice19, cores 8–15/24–31, OMP2,
8 GiB address-space limits and stdin `/dev/null`; Python used `-B`. The initial
`git pull --rebase` refused a pre-existing dirty coordinator log; fetch confirmed
main was already aligned, and that log was neither stashed nor edited. Root
storage was already below the general 50 GiB reserve; this small preparation
retains the inherited 12 GiB build floor and 1 GB cap, with no bulk/model writes.

Next: coordinator runs smoke once, then the matched three quick screens. Device
exactness, determinism and speed remain pending. This is a screenable CPU
repair, not a promoted performance result.

[Full-shape receipts](../experiments/own-xpu-runtime/stage2/packet71c-depth2-engine/evidence/fullshape.json),
[unfused byte gate](../experiments/own-xpu-runtime/stage2/packet71c-depth2-engine/evidence/unfused.json),
[M2 byte gate](../experiments/own-xpu-runtime/stage2/packet71c-depth2-engine/fixture/m2-receipt.json),
[queue plans](../experiments/own-xpu-runtime/stage2/packet71c-depth2-engine/evidence/lanequeue-plan.jsonl),
[proposed jobs](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p71c-B.txt),
[closeout](../experiments/own-xpu-runtime/stage2/packet71c-depth2-engine/CPU-PREPARATION-CLOSEOUT.md).
