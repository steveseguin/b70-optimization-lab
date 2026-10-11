# Arithmetic v2 chained decode preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Prepare packet16's chained decode runtime on the exact packet17 arithmetic
identity `iq3-p17-detmath-v2`. Separate Unsloth Flash-Next UD-IQ3_XXS quantized
compressed version; unchanged model weights, frozen r234 SG32/split4 BF16 trees
and R5 shape dispatch. CPU-only preparation on steve-b70s, October 11, 2026.
The unchanged incident-retrospective prompt has 87 input tokens. The CPU gates
require frozen 64 outputs/R5 eight outputs and 384 layer fixtures for each.

## Outcome

Device compilation and CPU preparation are separate from native qualification.
No device binary ran; no GPU or server was started; no speed is claimed.
Frozen matches **64/64 tokens and 384/384 fixtures**; R5 matches **8/8 tokens
and 384/384 fixtures**. Both non-GEMV modes pass 13 integration cases each. The
150 arithmetic, 4 owner-retirement, 7 chain/lifetime, 36 window protocol and 2
wrong-fixture rejection checks pass. Final binary/source identities are retained in
[build-receipt.json](build-receipt.json) and [cpu-tests.json](cpu-tests.json).
W0/W1/W2/W3 remain unrun and require coordinator admission.

## Packet19 containment and window hardening

Ported the reviewed snapshot and index-guard fixes into packet18's v2 arithmetic
without changing protected packets13–17,19,20. Cross-card native dependencies
are now rejected by owner and backend. Host drain and retirement precede queue
switches and every peer copy, including the final card1 commit before card0
readback. [Independent review](review-queue-isolation.md) lists all accepted
cross-queue event edges: **[]**. This contains a leading suspect; it does not
establish the cause of packet16's fault or authorize lifting FAULT HALT.

Resident tokens have 16 recorded completion waits, or 18 with layer snapshots;
retirement adds 32/36 native queue waits. README identifies each wait. W0 uses
the same binary and owner/adapter paths, 1,344 requested device bytes, 100 peer
round trips and 1,000 local chained kernels per card. It remains unrun. W2/W3
require its passing same-boot/binary/cards/environment receipt and W1's oracle
receipt. All windows reject NEO/unknown environment keys before creating a latch.
W2/W3 require owned device bytes plus host tables plus 12 GiB available RAM and
record MemAvailable/GPUActive before load, after load and at the end.

The CPU dependency sanitizer uses seeds0,1,17,73, both card counts and both
non-GEMV modes on the mini model; four seeds on the two-card resident short
real prompt; and one full87-position real first-token comparison to v2. Checker
self-tests and malformed index tests accompany the numerical runs. See
`sanitizer-*.json`; the final build receipt binds their pass status and current
source/binary identity. No native root-cause or speed conclusion follows.

## What worked

Both non-GEMV paths now use the v2 elementary functions and hash-checked
process-lifetime RoPE tables. Precision flags are enforced on compile and link
commands. A recursive device-source grep rejects platform transcendentals.
The event chain directly binds position/active/error buffers, eliminating 1,190
control-copy launches per token without changing the arithmetic graph. See
[census](census.json) and [independent reviews](review.md).

## What failed or remains uncertain

Loader-only inspection found libsycl unavailable without shell setup; the
packet adds a compiler-relative device RPATH and verifies it with ldd.
An initial CPU R5 streaming attempt was cooperatively stopped before fixtures
and replaced with the resident CPU path to avoid repeated expansion; its
[receipt](cpu-r5-streaming-interrupted.json) is retained. No numerical mismatch
was observed in that interrupted attempt. The two preliminary CPU jobs were stopped cooperatively to finish W0's field
order and position assertions, then definitive gates started with rebuilt
binaries; [interruption record](cpu-pre-final-interruption.json). Native arithmetic,
peer-copy/backing behavior, resident host-shadow fit, the 30-second canary bound,
driver-internal memory, fresh-process determinism and speed are open.
The prepared wrapper rejects shorter coverage and names the first differing
retained layer boundary, with BF16 value statistics. It does not pretend that
layer-only fixtures identify an unrecorded internal site. V2 output is not a
losslessness claim against arithmetic v1, a different model or FP8.

## Evidence and patches

- [Packet19 patch provenance](integration-provenance.json), [queue-isolation review](review-queue-isolation.md).
- [Local runtime and rationale](README.md), [prepared commands](WINDOW.md).
- [Original source hashes](source-provenance.json); adaptations stay in this directory.
- [Frozen CPU receipt](cpu-real-frozen.json), [R5 CPU receipt](cpu-real-r5.json).
- [Mini core](cpu-mini-core.json), [mini parallel](cpu-mini-parallel.json).
- [Build flags, binary hashes and checks](build-receipt.json).
- [Byte/launch census](census.json), [do-not-repeat index](DO-NOT-REPEAT.md).

Completed CPU scratch is removed after receipts are retained. Rebuild using
README's CPU-only command; ignored build artifacts are reconstructible. The
unchanged oracle fixtures remain at their repository path. The coordinator's
active packet16 sources/build tree and packets13/14/15 history are untouched.

## When to revisit

After recovery and separate coordinator admission, run W0 then W1 directly
against the v2 CPU oracle. Only passing W0 and W1 on the same boot/binary and
recorded environment permit W2/W3. Fresh-process repeats
then test each dispatch. Use the measured packet15 kernel costs as planning
weights for the deferred exact fusion candidates in README, after device parity
is established. Nothing queues a device window automatically.
