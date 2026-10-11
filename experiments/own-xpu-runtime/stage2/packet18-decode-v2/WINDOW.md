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

## W1: card 3, one card, streamed layers, eight generated tokens

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --window W1 --card 3 --seconds 10800 \
  --input "$P/build/input" --oracle "$ORACLE" \
  --output "$P/build/w1-card3-a"
```

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
  --w1 "$P/build/w1-card3-a/window.json" \
  --output "$P/build/w2-cards23-a"
```

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
  --w1 "$P/build/w1-card3-a/window.json" \
  --output "$P/build/w3-cards23-a"
```

This has W2's coverage and admission rules with `--gemv r5`. The reduction
order is unchanged. Native per-card allocation census and the 30 GiB cap
remain binding; the wrapper never changes precision or placement to fit.

## Fresh-process repeats

Separately admit the same window again, choose a new output directory, and
append `--repeat-of "$P/build/w2-cards23-a/window.json"` for a W2 repeat (or
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
`kernel_submissions`, and `host_waits`. Decode tok/s is 63 divided by the
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
