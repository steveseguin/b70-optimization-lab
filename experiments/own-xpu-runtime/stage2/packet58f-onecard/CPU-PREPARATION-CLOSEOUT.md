# Packet58f device masking and drain boundary — CPU closeout

<!-- campaign-closeout -->

## Question and identity

October 17, four-card host. New packet copied from frozen 58e, card 0,
unchanged IQ3 weights/arithmetic `iq3-p49-split32-v1`, full BF16 KV.
Repair the selector-only discovery and prelaunch/report-only stale drain.

## Outcome

CPU preparation passes. No GPU, model, service or live coordination operation
ran. Native device isolation, complete device memory, exactness and speed
remain pending. This is a wrapper repair, not a performance result.

## What worked

The exact BDF resolves passively to `/dev/dri/renderD130`. A real CPU child
receives the exact filter, affinity 0 and selector 0 while temporary A/B leases
coexist. Full-window CPU mocks exercise successful K1, preflight refusal,
report-only failure and failed postflight. Wrong-card FDs are rejected and
retained. Only clean completed device work releases early; CPU report failure
cannot qualify a result or advance the queue. No shared drain is taken before
prelaunch admission. Memory, memory-fence, storage and fault checks are repeated after the drain wait.
Existing 60-second drain spacing remains unchanged.

All 81 Python checks pass, including 22 full admission/mask checks. The native
full-shape host setup passes 144 expert banks, 48 route sources, three post-load
allocations and two invalid-lifetime regressions using 2,457,406 backing bytes.
Request reset agrees across fresh/persistent runs and 40 retained fixtures.
K1 passes 24 checks with its unchanged exact hash. The exact memory boundary
remains 85,565,068,816 bytes; one byte less fails. Both native build modes are
compiled serially, without executing the device binary. All 165 native source
and constant files match the parent. The seal and actual fresh card-0 plan
are the final admission checks.

## What failed or remains uncertain

58e did not apply the lane-pair mask: its child environment, like 58c's,
contained only the SYCL selector. Its newly strict sensor rejected an extra or
unidentified Xe FD. The failed record lacks the actual offending BDF. Earlier
screen-v3 source investigation supports pre-open filtering; native FD proof
still requires the coordinator's K1. The filter is not a kernel device sandbox.
The private monitor now retains offending FD rows. The earlier coordinator
fault-review refusal and all parent latches remain untouched.

## Evidence and patches

[Mask cause](evidence/mask-root-cause.json), [mask CPU proof](evidence/mask-cpu.json),
[admission](evidence/admission-cpu.json), [post-load](evidence/postload-allocation-cpu.json),
[Python gates](evidence/python-cpu-gates.json), [plan](evidence/queue-plan.txt),
[native identity](evidence/native-unchanged58f.json), [artifact retention](ARTIFACT-RETENTION.md).
The parent manifest pins the frozen copy. Historical evidence retains its old
identity. Build scratch is ignored and reproducible from the local build inputs;
this is not a public clean-build recipe.

## When to revisit

The coordinator reviews retained lineage stops and runs the newly sealed chain
from K1a at `evidence/card0-58f-a`. Inspect actual owned Xe FDs before advancing.
Do not reuse old K1 receipts, change latches, relax the sensor or retry a failure.
