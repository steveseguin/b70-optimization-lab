# Packet49c CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

On 2026-10-17, combine sealed packet49b with only packet51's winning route,
HC a/f gate/low and attention output/combine kernels. Preserve the quantized
compressed IQ3 lane's arithmetic `iq3-p49-split32-v1`, weights, BF16 KV,
23/25 split, draft rank 1 and 4K context. Intended device work uses cards 0+1
on steve-b70s; this preparation used CPU builds and synthetic fixtures only.

## Outcome

CPU preparation accepted and sealed; integrated device and model results
remain pending. GNU, Intel device compilation and ASAN/UBSAN builds pass
with the same 159 compiled-source bindings. Ten fresh GNU fixture runs and
six ownership suites pass. The added kernels pass 384 checks over four
GNU/sanitizer processes. Two fresh actual-engine CPU processes each pass
36 cases and 5,472 byte comparisons. All 56 admission/storage/retention tests
pass. Both ordinary and sanitizer state gates pass 31 cases and 26 checks.
The seal and its verification pass. No GPU, model payload, service or host
setting was used or changed. The existing oracle and packet49b units remain
untouched. No integrated performance or full-model quality claim is made.

## What worked

Selected packet51 arithmetic bodies retain their original operation order;
the existing production dispatch reaches M=1 and each independently scheduled
M=2 row. The unchanged shared CPU oracle is hash-bound. The queue STOP tests
prove a waiting predecessor exits without launching KD and releases its own
flock; the new queue does not reject the predecessor's directory.

Both requested chains fit at the recorded storage check: retained build
539,704,546 bytes, root free 20,465,577,984 bytes, required free
20,375,904,414 bytes, margin 89,673,570 bytes. This preserves all
5,818,804,480 bytes of packet49b's pending writes, the 8 GB free floor and
500 MB oracle growth. Only this packet's 350,250,872 regenerable object bytes
were removed. Its 848,599,576 sanitizer executable bytes are retained as
100,224,902 verified gzip bytes. No other packet scratch was deleted.

## What failed or remains uncertain

The initial duplicate HC preparation hook failed GNU compilation. Its raw
log was accidentally overwritten; the reconstructed rejected block and
retention limitation are explicitly recorded. Intel compilation caught an
out-of-scope prepared range capture; replacing local `wg=256` with literal
256 preserved geometry and arithmetic. Final builds and gates were refreshed.
Attention's device-only split4 workspace is checked against the same-backend
control and excluded only from the cross-backend canonical digest.

The CPU engine adapter exercises actual dispatch with legacy execution,
not prepared replay or the complete MTP schedule. Device and shared-oracle
model gates are still required. There is no atomic device lock between the
two queues: the coordinator must prevent an oracle-completion race during
49c early work. STOP is for a waiting queue, not an active GPU-window kill.
The disk margin is small and changes with other writes; live admission is
mandatory. WS128 is a 128-token record comparison, not the 512-token public
promotion gate. The 39.422 tok/s record is unchanged.

## Evidence and patches

- [Integration and call coverage](INTEGRATION.md), [kernel review](REVIEW-KERNELS.md), [queue/storage review](REVIEW-INDEPENDENT.md).
- [Build seal](build-receipt.json), [kernel provenance](p49c-kernel-provenance.json), [shared oracle binding](oracle-binding.json).
- [CPU fixtures](p49-cpu-gates.json), [new-kernel gates](p49c-round2-gates.json), [engine comparisons](p49c-engine-gates.json), [Python tests](p49-python-gates.json).
- [Storage receipt](storage-precheck.json), [object identities](object-cleanup-receipt.json), [sanitizer retention](asan-artifact-retention.json), [restore policy](ARTIFACT-RETENTION.md).
- [Initial correction limits](evidence/preparation-corrections/receipt.json), [device compile refusal](evidence/device-compile-refusal/receipt.json).

Native binaries and raw CPU fixtures remain in the packet's external build
tree, reached by its tracked build symlink. Compact state evidence is under
`evidence/`. Restore/build commands are in [CPU-BUILD.md](CPU-BUILD.md).

## When to revisit

The coordinator runs the new early chain, then performs the conditional clean
switch and queues the model chain with `--wait-oracle`, following
[the exact runbook](WINDOW.md). A device or model failure requires a separate
recorded candidate; do not edit this sealed packet after device work starts.
