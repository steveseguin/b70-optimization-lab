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

Request reset inventory: [ROLLBACK.md](ROLLBACK.md). Packet40 source reviews:
[draft ordering](review-p40-nonblocking-draft.md),
[cancellation and retention](review-cancellation-retention-p40.md), and
[token authority](review-retention-token-authority.json). Copied packet38
`review-resume-*` reviews remain historical evidence; the final seal maps their
obligations to current proofs.
Dynamic gates and remaining device qualification are in the seal.

KD retains the authenticated table `build/capture-incident-retrospective.tsv`,
the `build/captured-incident-retrospective/` stream inputs, and the verified
compressed archive named by `capture-run-incident-retrospective.json`. The old
raw capture `output` directory is disposable scratch and must be absent after
preparation. KD validates archived fixture hashes against
`draft_capture_fixture_sha256`, binds the capture input receipt through
`draft_capture_input_sha256`, and verifies stream/table hashes. It then creates
a fresh CPU reference under the selected K2 dispatch before either device owner
launches. The per-window host-reference scratch follows the window's verified
archive and cleanup policy. No raw cache/logit output is a permanent KD input.


## Packet40 compute-boundary observers

Each half installs two same-thread owner observers only for its launch loop.
The pre-submit observer may cancel before a kernel is submitted. The post-submit
observer records the actual owned event even when a multi-pass operation has
not returned its grouped result. Both observers are cleared before drain,
rollback, fixture export and every exceptional exit. Capturing/preparing
commands does not invoke them. No observer outlives its stack Candidate or
Engine; no second thread calls the owner. Cancellation is caught before the
backend's ordinary fault handler and never clears a device failure.

Snapshot clear uploads and one-time standalone scratch initialization occur
with owner events drained as normal uploads require. They do not release or
rebind any prepared target/draft allocation. Snapshot buffers are zero again
before final-state hashes are collected.
