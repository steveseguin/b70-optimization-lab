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
150 arithmetic, 4 owner-retirement, 7 chain/lifetime, 28 window protocol and 2
wrong-fixture rejection checks pass. Final binary/source identities are retained in
[build-receipt.json](build-receipt.json) and [cpu-tests.json](cpu-tests.json).
W1/W2/W3 remain unrun and require coordinator admission.

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
was observed in that interrupted attempt. Native arithmetic,
peer-copy behavior, resident fit, fresh-process determinism and speed are open.
The prepared wrapper rejects shorter coverage and names the first differing
retained layer boundary, with BF16 value statistics. It does not pretend that
layer-only fixtures identify an unrecorded internal site. V2 output is not a
losslessness claim against arithmetic v1, a different model or FP8.

## Evidence and patches

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

After separate coordinator admission, run W1 directly against the v2 CPU oracle.
Only a passing W1 on the same boot/binary permits W2/W3. Fresh-process repeats
then test each dispatch. Use the measured packet15 kernel costs as planning
weights for the deferred exact fusion candidates in README, after device parity
is established. Nothing queues a device window automatically.
