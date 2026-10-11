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
150 arithmetic, 4 owner-retirement, 7 chain/lifetime, 39 window protocol and 2
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
peer-copy/backing behavior, resident host-shadow fit, first-use startup/JIT duration,
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

## October 11: watchdog correction, CPU only

The old W0 30 s cutoff could signal a normally initializing GPU process. Closed
arm: **a watchdog set to the expected run time**. W0 now defaults to 600 s
(300..1800); its native receipt separates startup/JIT, device submission times,
work wall, teardown and total wall. Total time is recorded, never a pass gate.
A completed submission beyond 100 ms fails the budget in the final receipt after
normal coverage/teardown; five-second completion waits protect pending work.
W1–W3 keep 10,800 s with a new 7,800 s minimum. [Audit](DEADLINES.md).

Both host and SYCL binaries were rebuilt; only the host was run. Unit/mini,
canary and 39 wrapper tests were rerun. Long frozen (64 tokens/384 layers), R5
(8 tokens/384 layers), and dependency sanitizer gates were **reused**, with
original receipts and binary identities preserved. [Reuse proof](deadline-reuse.json)
reverses the exact model-neutral default/helper edits to the prior source hash,
checks every other bound numerical source/data/build input, and separately binds
the isolated canary. The new build receipt explicitly labels reused evidence;
no claim that the long gates ran on the new binary is made. No device ran,
no device discovery occurred, and PID 183867 and FAULT HALT remain untouched.

Seven [host-only native CLI checks](deadline-native-cli-tests.json) also pass: default 600 s, accepted 300/1800 s, and refused 0/30/299/1801 s. No device binary ran.

## October 11: SYCL lifetime repair (CPU only)

Closed arm: **SYCL object outliving the owner's context release**. The canary's
bundle and all work captures now die in an inner scope before owner shutdown,
including exception unwinding. [Lifetime inventory and reuse reasoning](LIFETIME.md)
covers two-card decode, peer copies, fixtures and all linked kernel sources.
The native decode/owner/adapter arithmetic and launch order are unchanged.
Fresh unit, mini/integration, canary mock and mini dependency-sanitizer checks
are recorded in `build-receipt.json`; full-model gates are explicitly carried
forward in `lifetime-reuse.json`, with original hashes and binary identities.
No device binary, discovery, real-model CPU run or host setting change occurred.

The original W1 device receipt and W0 passing-work/abnormal-exit evidence are
preserved. Both old build window directories and the existing fault latch remain
untouched. The coordinator resolves the existing latch under its admission
protocol before running these fresh commands; these commands do not clear it.
Use the new `-b` directories below. W1 and W0 must both pass on this new binary
before W2/W3. A native passing receipt followed by abnormal exit remains failed,
with the exact diagnosis “device work passed; exit abnormal”.

Cheap-only rebuild/reseal: `nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2
/home/steve/.venvs/vllm-xpu/bin/python -B
experiments/own-xpu-runtime/stage2/packet18-decode-v2/repair_build.py`.
The earlier `build.py` watchdog-only reuse command is historical and cannot
validate this repair; it deliberately refuses existing device-window evidence.
