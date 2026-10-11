# Packet 18 prepared device windows

No device ran during preparation. No speed is claimed. These commands are
prepared for separate coordinator admission; nothing launches automatically.
Use the coordinator's approved user-unit supervision. Never hard-kill a device
process, its process group, or its owning unit during a cooperative drain.

Run from `/home/steve/llm-optimizations`. Every command has idle CPU and I/O
priority and two numeric threads. All physical card indexes are parameters:
`--card` selects the single card for W1, and the first of two adjacent cards
for W2/W3. The native loader controls the actual placement. No discovery
probe, server, port 8188, LTX unit, sudo, power or host-memory setting is used.

```bash
P=experiments/own-xpu-runtime/stage2/packet18-decode-v2
PY=/home/steve/.venvs/vllm-xpu/bin/python
ORACLE=experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective
```

## W0: cards 2+3, weight-free two-card canary

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --window W0 --card 2 --seconds 600 \
  --output "$P/build/w0-cards23-b"
```

Run W0, W1, W2, then W3, each separately admitted. W0 uses the same sealed
`own-rt-iq3` binary as the model windows. It never opens model weights or RoPE
tables. It requests **672 device bytes per card, 1,344 bytes total**, and a
256-byte pinned host buffer. It performs 100 verified round trips:
Q0 kernel, host drain, Q0-to-Q1 peer copy, host drain, Q1 kernel, host drain,
Q1-to-Q0 peer copy, then host byte comparison. Each peer copy starts after
both queues are drained and their events retired.

It next exercises the real owner and adapter begin/broadcast/boundary/return/
commit paths with tiny buffers, including all five outward and two return
copies. It checks result, error, streams and both committed positions. Finally
it chains 1,000 kernels on each card, with one completion wait at the end of
each chain; neither chain shares an event with the other card. Host readbacks
verify the results. A native profiling check requires every recorded submission
below 100 ms, well below one second. A slow completed submission is recorded as
`submission_budget_passed=false`; the canary finishes the fixed coverage and
teardown normally and writes a failed receipt. No timing expectation signals it.
The child watchdog defaults to **600 s**, accepts **300..1800 s**, and refuses
anything tighter. The former 30 s total is only a reported expectation, never a
pass gate. There is no aggregate device-work time gate.

Before device work, the native program constructs both queues and materializes
the executable SYCL kernel bundle for both devices. `startup_jit_ms` measures
that phase. `device_work_ms` sums profiled execution intervals of recorded
submissions, excluding startup/JIT and host issuing gaps; it is zero in the CPU
mock, which has no device clock. `work_wall_ms` measures the work phase including
host overhead, `teardown_ms` measures shutdown, and `wall_ms` records the full
native elapsed time. All three wall phases are separate from the profiled sum.
Completion waits and canary teardown allow five seconds each. Blocking driver
calls cannot be safely forced to honor a short bound; only the roomy child
watchdog can request a stop. No retries are scheduled.
The clean watcher adds five seconds of postflight (up to two more for a journal
read). Driver-internal allocations are not measurable from the requested-byte
census and remain a device-qualification risk; no measured device-memory claim
is made from this CPU preparation.

W2 and W3 require `--w0` with a passing receipt on the same boot, binary, card
pair and recorded environment. They re-hash W0's native receipt and recheck its
coverage, memory/submission bounds and safe teardown. W0 does not substitute for W1.
`ldd` and environment checks run before any output directory or fault latch is
created. A device window still requires coordinator admission after FAULT HALT.

## W1: card 3, one card, streamed layers, eight generated tokens

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --window W1 --card 3 --seconds 10800 \
  --input "$P/build/input" --oracle "$ORACLE" \
  --output "$P/build/w1-card3-b"
```

Expected W1 duration: roughly 10–20 minutes, an unmeasured planning estimate;
the explicit watchdog remains three hours. W1–W3 accept only 7,800..10,800 s;
the floor includes more than 4× the retained 1,897.718 s CPU full gate plus
17 s first-run JIT proxy. See [all deadline margins](DEADLINES.md).

The native arguments are `--card 3 --cards 1 --memory layer-streaming
--stage first-token --max-new 8 --context 256 --nongemv parallel --gemv frozen`.
All 48 step-1 layer files, all 336 retained layer files for steps 2–8, and all
eight tokens must match the v2 CPU oracle directly. No previous device result
is accepted as the oracle. Arithmetic identity is `iq3-p17-detmath-v2`.
Step 1 is the last prompt position, which predicts the first generated token.

This is the lane's first true device exactness gate. The receipt lists every
layer's equality and hashes. Any mismatch fails; the first differing layer
includes the unequal-value count, first differing BF16 words and index,
finite maximum/mean absolute difference, and nonfinite-value count. The site
label is `layer_output`: the retained fixture localizes the earliest layer
boundary, not an unrecorded inner operation. Further operation-level tracing
is required if that gate fails. Missing output files are also listed.

## W2: cards 2+3, resident, frozen GEMV

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --window W2 --card 2 --seconds 10800 \
  --input "$P/build/input" --oracle "$ORACLE" \
  --w0 "$P/build/w0-cards23-b/window.json" \
  --w1 "$P/build/w1-card3-b/window.json" \
  --output "$P/build/w2-cards23-b"
```

Expected W2 duration: roughly 5–20 minutes, unmeasured; three-hour deadline.

Native arguments: `--card 2 --cards 2 --memory resident --stage decode
--max-new 64 --context 256 --nongemv parallel --gemv frozen`. All 64 tokens
and the 384 fixtures for steps 1–8 must match. W1 must have passed on the same
boot, binary and prompt, on a card included in the admitted pair, against the
same v2 oracle. W1's native safe teardown and every fixture hash are rechecked.

## W3: cards 2+3, resident, R5 GEMV

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --window W3 --card 2 --seconds 10800 \
  --input "$P/build/input" --oracle "$ORACLE" \
  --w0 "$P/build/w0-cards23-b/window.json" \
  --w1 "$P/build/w1-card3-b/window.json" \
  --output "$P/build/w3-cards23-b"
```

Expected W3 duration: roughly 5–20 minutes, unmeasured; three-hour deadline.

This has W2's coverage and admission rules with `--gemv r5`. The reduction
order is unchanged. Native per-card allocation census and the 30 GiB cap
remain binding; the wrapper never changes precision or placement to fit.

## Fixed environment and host-memory admission

All four windows refuse if **any NEO debug key is present**, even with an empty
value or zero. `NEOReadDebugKeys` and `EnableDeferBacking` are forbidden. The
policy is closed: unknown environment names are refused, so a future NEO key
cannot slip through an incomplete denylist. Ordinary shell/agent metadata is
allowed at the wrapper but not forwarded to the child. Every receipt contains
the full native environment and all admitted runtime-related values; credentials
and unrelated agent metadata are excluded. W2/W3 require W0 and W1 environment
identity. Testing a NEO debug key is a **separately preregistered experiment**
and is not part of this packet. Never add keys to make a prepared window fit.

Without the NEO key, device buffers can acquire a host-RAM shadow. This can be
as large as owned VRAM and appear as `GPUActive` in `/proc/meminfo`, not RSS.
W2/W3 print all admission numbers and refuse before launch if `MemAvailable`
is below the sum of both cards' owned device bytes, the 29,321,610,240-byte
host-backed embedding/PLE tables, and a 12 GiB reserve:

| Window | Both cards' owned device bytes | Tables | Reserve | Required MemAvailable |
| --- | ---: | ---: | ---: | ---: |
| W2 frozen | 53,261,285,328 | 29,321,610,240 | 12,884,901,888 | 95,467,797,456 |
| W3 R5 | 55,071,143,888 | 29,321,610,240 | 12,884,901,888 | 97,277,656,016 |

The wrapper records memory before launch and at the end; the native program
records `MemAvailable` and `GPUActive` immediately before load, after load, and
at the end in `run/host-memory.jsonl`. W2/W3 require those three samples to pass.
An unavailable `GPUActive` field is explicitly null. A child parked on a fault
cannot produce a native end sample; the wrapper retains its own end observation
and fails the window. No memory, swap, cache, power or driver setting is changed.

## Fresh-process repeats

Separately admit the same window again, choose a new output directory, and
append `--repeat-of "$P/build/w2-cards23-b/window.json"` for a W2 repeat (or
the corresponding W1/W3 receipt). Boot, binary, prompt, manifest, dispatch,
non-GEMV mode, topology, memory mode, stage, context, arithmetic, oracle hashes
and expected tokens must match. Every fixture and token must repeat exactly.
W2 cannot anchor a W3 repeat. No run queues another run.

## Preflight, timings, and failures

The wrapper checks the current device binary against the build receipt, then
runs **`ldd` before creating or writing any fault latch**. Missing libraries
fail admission without starting the executable. It checks the CPU receipt,
all bound sources and inputs, the complete v2 oracle arithmetic identity,
and all 384 oracle fixtures. CPU coverage must be frozen GEMV 64/64 tokens,
R5 at least 8/8 tokens, and 384/384 layers for each. The native loader verifies
model shards and the host-generated RoPE model constant. Bindings are checked
again after the process exits. A fresh output directory under packet18's
ignored `build/` is mandatory. Existing evidence is never overwritten.

`run/timings.jsonl` has one row per generated token, including the first:
`wall_ms`, `gemv_device_ms`, `non_gemv_device_ms`, `transfer_wall_ms`,
`kernel_submissions`, and `host_waits`. Resident tokens have 16 counted event
waits, or 18 with snapshots. Retirement also calls both queue waits after each
completed batch: 32 or 36 additional calls, normally already complete. See
README for each boundary. Decode tok/s is 63 divided by the
whole wall-clock span of tokens 2–64 for W2/W3. Device kernel times do not
form the denominator. The receipt records first-token/prefill timing
separately. Fixture capture stays inside measured wall time. This is one
prompt's exactness window, not a performance headline or realistic-suite
result.

The watcher polls specific kernel-fault signatures every 250 ms, with a
two-second journal subprocess bound. A new fault, journal failure, deadline,
or signal saves evidence and sends one SIGTERM to the captured native PID.
There is no restart, retry, reset, reboot, hard kill, or automatic next window.
The boot-bound `build/FAULT.json` blocks further windows pending coordinator
recovery. A comparison failure, changed binding, missing/unsafe teardown,
or failed native exit also fails closed and preserves the output.

After a stop request, the cooperative drain has a 60-second watcher bound.
A still-running child is retained, its PID is recorded, and
`child_still_running=true` returns responsibility to the coordinator. Keep
that child's owning unit alive. A wrapper exit does not prove idle cards.
Clean exits receive a five-second bounded journal tail (a running journal
read can add at most two seconds). Teardown must report zero live bytes,
zero in-flight events and `safe_to_exit=true`; a shared owner must explicitly
cover both cards. External idle and health admission/postflight remain the
coordinator's responsibility.

Preserve the wrapper/native receipts, timing rows, every retained fixture,
input/source identities, allocation census, stdout and kernel evidence before
cleaning ignored output. Full fresh-process determinism and broader prompt
quality still need their own completed evidence.

## October 11 watchdog repair and CPU-only reseal

[Deadline audit](DEADLINES.md) lists every timeout, its evidence and expiry action.
No device ran. The 39 wrapper tests, rebuilt CPU canary, unit/mini checks and
compile-only SYCL build are fresh. The long frozen/R5 oracle gates and dependency
sanitizer gates are reused under [the narrow reuse audit](deadline-reuse.json):
model computation and all its bound numerical inputs are unchanged; only the
canary/default-selection/helper and wrapper code changed. Original gate receipts
retain their original tested binary hashes. This is not a fresh full-model run.

CPU-only rebuild/reseal (from repository root):

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B \
  experiments/own-xpu-runtime/stage2/packet18-decode-v2/build.py \
  --keep-build --reuse-real-gates --reuse-sanitizer-gates
```

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
