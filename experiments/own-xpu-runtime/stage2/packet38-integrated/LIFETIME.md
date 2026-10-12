# Lifetimes

One process owns each rank's device/queue, target buffers, both rollback banks
and prepared lists. Draft rank1 borrows the immutable head and RoPE from that
same owner. All writable draft buffers are private. Draft construction completes
before execution; preparation creates closures without executing kernels.

Draft destruction never frees shared-owner allocations. Reset zeroes private
state without releasing or allocating anything. Releasing any allocation on a
shared owner changes its generation and invalidates target captures: forbidden
between requests. The owner teardown drains real events, destroys command
borrowers, releases allocations, queue and context in the established order.

Shared mapping remains alive until both ranks exit. Native mailbox request and
reply publication use release/acquire counters; payloads are written only by
their owner and cannot be overwritten while pending. Worker completion includes
the op0 acknowledgement before Python can reset shared bytes. There is no
unbounded spin. Cancellation/failure wakes both waits and is checked at bounded
intervals. A stuck owner is reported and retained, never force-killed/retried.

Request reset inventory: [ROLLBACK.md](ROLLBACK.md). Independent source reviews:
[controller](review-resume-controller.md), [token authority](review-resume-authority.md),
[reset](review-resume-reset.md). Earlier reviews remain historical evidence.
Dynamic gates and remaining device qualification are in the seal.

KD needs a small retained CPU reference after preparation cleanup. Keep the
`output` directory named by `capture-run-incident-retrospective.json`,
`build/capture-incident-retrospective.tsv`, and
`build/captured-incident-retrospective/` stream inputs. KD checks every retained
reference fixture against `draft_capture_fixture_sha256`, binds the capture
input receipt through `draft_capture_input_sha256`, and verifies stream/table
hashes before either fresh owner launches. These are sealed window inputs,
not disposable fixture scratch. `cleanup.py` preserves them. All ordinary CPU
fixture scratch is removed after its receipt; large raw `output.bin` files and
raw event/trace logs do not belong in that retained reference set.
