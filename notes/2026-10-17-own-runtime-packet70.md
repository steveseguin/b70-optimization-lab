# October 17 — packet70 combined record bundle, CPU preparation

Packet70 is prepared in new paths on `main`. It reuses packet65's sealed
binary and exact C++ sources; nothing was compiled and no CPU model or GPU
was run. Packet64/61x/65/66/67/68, all shared screen sources and packet64's
orchestration were left unchanged. The coordinator keeps ownership of the
running chain and quick screens.

The fixed preset is packet64's `1-draft-hc-batch`, placement 1 (24/24), selected
at **17:37:52 UTC**. [Retained decision excerpt](../experiments/own-xpu-runtime/stage2/packet70-record-bundle/evidence/preset-decision.txt).
It carries the draft-head prefix, controller spin/pure-spin waits, packet60
target HC fusion, packet59 draft-HC fusion through packet63, batched rollback
miss copies, and optional packet65 expert kernels in one chain.
`fast_reseal.py --experts production|wide64|wg64|wg128|prefetch64` binds one of
five immutable views without rebuilding. Prepared selection is production.

Every queue gap is 90 seconds, including W windows and a resumed boundary.
The drain, teardown, fault and lane-admission code remains packet64's.
The supplied hourly review (18:07 UTC) reported over 40 screens using 90-second
gaps with the fault count unchanged at two. This is the policy evidence;
this task did not run a new soak. The eleven-window chain's five long gaps
shrink by 215 seconds each: 1,075 seconds less scheduled waiting, not a measured
model throughput gain. Ten total gaps now account for 900 seconds.

The screen fix addresses the reported memory note
`lane-marker-left-by-post-drain-failure`. The worker stages already exact
receipts before teardown and performs no summary work after draining.
The supervisor confirms successful drain, worker exit, isolation and fresh
postflight, then releases the cooperative lease **and** old v3 lane lock.
Only then does it aggregate/write reports. CPU reporting failure stays a failed
report, with no fault latch and no active lane marker. Failures before or
during drain/postflight keep the original conservative behavior. Six mock
checks include the full 13-request worker flow and a new lease after an
injected summary failure.

The submission copy accepts the registered chain, plus exactly pinned resumes
through `resume_chain.validate(prepared=True)`, matching packet61x commit
`05d39a699`. Registered resume destinations are validated too. The evidence
bundle and payload disclose imported early receipts and fresh model windows;
all seven requested optimization disclosures remain in notes and structured
flags. Twenty-two submission tests pass with the requested venv/pytest runner.
No payload was sent or fabricated from CPU preparation.

[Orchestration helper](../experiments/own-xpu-runtime/ops/packet70-orchestration/README.md)
reads packet65's original quick comparison and hash-checked receipts. It selects
an expert only when every screen is 13/13 exact and the expert wins against
the two-control mean on both lanes. It then fast-reseals and performs CPU
prechecks, writes readiness and prints the exact chain command. It never
launches the chain or a companion. Twelve helper tests and the dry run pass.

At the retained 18:18 UTC snapshot, lane A had not started and lane B had two
completed screens. Lane A is scheduled after packet64's chain ends, about
18:45 UTC. Both-lane selection is therefore pending; `ready.json` is false
with the command included. No helper is left running. The coordinator can
run it after the screens, then execute its printed command.

The seal, all eleven window plans, ten screen plans and storage admission pass.
The full census has 12,484 input files and 352 write paths, without reading
model payloads. Fifty-three focused chain/submission tests plus seven subtests
pass. The repeated fixture inputs and selection binaries use references or
hardlinks, not copied build trees. The full census is retained as byte-verified
gzip with a restoration receipt. Packet49 remains the quality authority;
full BF16 KV and fresh exactness gates are unchanged. Device performance and
the combined packet's full quality chain remain unmeasured.

[Packet and commands](../experiments/own-xpu-runtime/stage2/packet70-record-bundle/README.md),
[evidence index](../experiments/own-xpu-runtime/stage2/packet70-record-bundle/evidence/validation.json),
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet70-record-bundle/CPU-PREPARATION-CLOSEOUT.md).

## K2 wrapper repair and fresh-chain readiness

The 19:17 UTC chain passed K0, K1a and K1b. K2's two device owners also
passed and completed teardown, but CPU post-processing rejected the new
`experts` selection field: `selection must name exactly route/recurrence/hc`.
The chain stopped with `K2 exited 1; no retry`. The fault count remains two;
this repair started no device work or service.

`p49_dispatch.py` now removes both `miss` and `experts` before the strict
three-choice measurement gate. Every packet70 choices consumer was audited;
K2 is the only active window postprocessor needing this projection. The full
five-key submission validation and strict rejection of unknown keys remain.
The new CPU replay failed on all five expert choices before the fix, then
passed using the original K2 summary and round3 timings, with temporary output
copies. A reader inventory test covers future selection-consumer additions.
See [regression evidence](../experiments/own-xpu-runtime/stage2/packet70-record-bundle/evidence/k2fix-tests.log)
and [identity proof](../experiments/own-xpu-runtime/stage2/packet70-record-bundle/evidence/k2fix-identity.json).

All 246 failed-chain files, including STOP, were renamed together to
`/home/steve/own-xpu-runtime-results/packet70-record-bundle/build/device-cards01-a-k2fail-20261017T1933`.
The reseal guard permits only that exact archive with its complete hash-bound
inventory, failed K2 wrapper receipt and passed safe device teardowns. Every
other started chain still blocks resealing. Nothing was deleted. Existing
resume tools require passed K2 and W0p, so this repair prepares a fresh full
chain at the registered `device-cards01-a` path; no receipts are imported.
The submission helper admits that fresh path.

The packet-local selection and seal tools now validate/reseal packet70's five
views without touching frozen shared screen tools. All binaries, arithmetic,
selections, dispatch, screen artifacts, fixture/gate bytes and existing screen
source hashes are unchanged. The old seals are retained. The selected bundle
remains `1-draft-hc-batch-wide64`.

All five required prechecks pass: chain seal, input census (12,490 files and
352 write paths), storage, full-chain plan, and queue plan. Five repair tests
and twelve orchestration tests pass. The stopped chain fits the existing
storage budget without a change. The read-only review found no blockers.
[Ready record](../experiments/own-xpu-runtime/ops/packet70-orchestration/ready.json)
contains the exact coordinator command, current seal hashes, and check logs.
It uses the unused `packet70-chain-k2fix` unit and a separate log; the failed
unit is untouched. Readiness verification passes. No launch occurred.

The initial `git pull --rebase` was refused because unrelated packet71 work
and an orchestration log were dirty. Fetch confirmed local main matched
origin/main; those unrelated edits were preserved.
