# Packet129 — acceptance-first faithful draft experts

CPU-only preparation began at 13:06 UTC, with a 2.5-hour limit. Pull refused
unrelated dirty files; fetch confirmed main and origin/main at
`2165ebe90119526861fd4bcca760639ac683374d`. Existing packet trees, screen,
orchestration and live queues remain frozen. Root starts with about 31 GB
available; stop below 25 GB. Builds stay below 300 MB, with packet94's serial
compiler turn, nice19, CPUs 8–15/24–31, closed job stdin and 8 GiB CPU limits.

The new tree copies packet124c while preserving symlinks. Production still
uses bundle7, the unchanged `iq3-p49-split32-v1` target, BF16 KV, full target
verification and the independently selected 80,128-row draft prefix.

Source inspection confirms that all 512 routed draft experts' gate/up/down
FP8 tensors are converted to symmetric INT8 with FP32 scales per 16 values.
Draft attention, shared experts and HC projections retain publisher BF16.
Norm gains are widened and adjusted by the existing convention. The production
head shares the target's expanded Q6_K head; it is not publisher BF16.

The preregistered candidate retains publisher FP8 values and BF16 block scales,
decoding their product to FP32 before the unchanged lane reduction. For this
acceptance-only test, only ten selected experts are staged at a time. The
production draft supplies every actual proposal. The candidate replays the
expert-to-head suffix on the same inputs; production mutable state is restored
before its proposal is published. No diagnostic timing is a speed claim.

The independent set uses the first and last 128 tokens of each of packet114's
five original pinned general documents, with a 128-token generation cap per
request. The full twelve-prompt suite is secondary only. Keep the candidate
only at an independent acceptance gain of at least 1.5 percentage points;
otherwise close it. No prefix or corpus tuning from suite outcomes is allowed.

The coordinator owns the eventual lane-B load. This session launches no GPU,
service or native device process and changes no host settings. Candidate
adoption, full new-format KD gates and a timing bracket remain conditional on
the actual independent acceptance result.

## Compiled diagnostic and proposal milestone

Preregistration `05f436d86` was pushed before any acceptance measurement.
Before device results, revision 2 clarified natural EOS: do not force
continuation after completion; all ten independent requests remain mandatory,
and at least 512 verified proposals are needed for a decision. The text windows,
tokens, single candidate and +1.5-point threshold are unchanged. The suite has
no role in selection or the acceptance decision.

GNU and Intel pass all 254 finite FP8 codes, both routed matrix widths,
paired/unpaired outputs, repeated expert IDs and invalid-route bounds, twice
per compiler. Four fresh miniature runs preserve 96 target fixtures, 24 output
tokens, production proposals and persistent draft state. Three requests in one
CPU load verify resets and shadow restoration. These are CPU checks, not device
quality or speed results.

Full-size mocked initialization keeps rank0 at 28,144,182,388 device bytes and
rank1 at 31,475,905,242, leaving 736,349,478 bytes below rank1's 30 GiB arena cap.
Actual device residency remains unmeasured. The selected-expert shadow banks
add 49,920,000 bytes; the full production INT8 bank stays untouched.

The real worker emits both native argument vectors. The actual native parser
and full-size startup accept them on CPU; only rank1 receives the shadow flag.
The real oracle CLI accepts the preserved authority symlink. Acceptance tests,
drain race/negative controls and the recursive drain scan pass. The first parser
attempt lacked OMP_NUM_THREADS=2; rerunning through the CPU entry wrapper fixed
that environment issue without changing runtime behavior.

The new proposed file is `ops/lane-queue/proposed-p129-accept-B.txt` under this
runtime lane. The real queue planner passes it in a temporary queue copy.
One load covers independent text first, then the complete secondary suite.
Expected duration is 15–30 minutes, with a 7,200-second watchdog and cooperative
drain; timings remain diagnostic. No live queue was edited.

The [packet](../experiments/own-xpu-runtime/stage2/packet129-draft-acceptance/README.md)
retains format costs, exact input pins, native source, reused-object hashes,
CPU gates and queue plan. Build size at this milestone is 108,901,401 bytes.
No device acceptance result exists, so candidate adoption and the conditional
v5 timing proposal have not been prepared.

## Final CPU lifecycle checks

The diagnostic milestone was pushed as `ec146a530`. The complete worker then
passed a CPU rehearsal through all 22 requests, 23 resets and one model load.
Real selection, input and oracle checks ran; device transport, generated rows,
monitoring and teardown permits were synthetic and confined to deleted temporary
scratch. A changed-production-guess negative control failed after its first
request and exercised cooperative failure drain. No synthetic acceptance result
is retained or used for the candidate decision.

Actual runtime imports preserve every inherited resource limit. An intercepted
native launch passes with unlimited address space; a separate capped CPU child
is refused before exec. The tiny byte fixtures used by the seals are explicitly
retained alongside their hashes, even where repository-wide ignore rules would
otherwise omit them. Native binaries and runtime source are unchanged from the
diagnostic milestone. The only remaining dependency is the coordinator's device
acceptance result; no GPU process was launched by this task.
