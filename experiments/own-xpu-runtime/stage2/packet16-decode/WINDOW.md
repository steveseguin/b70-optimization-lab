# Packet 16: prepared device windows

**No device window was run while preparing this packet. No device speed is
claimed.** These commands need separate coordinator admission of the named
cards. Nothing below queues or automatically launches a later window. Use the
coordinator's existing approved systemd user supervision, with its stop policy
preserving the native owner during a cooperative drain. Do not use a watchdog
that hard-kills the GPU process or its process group.

All commands run from `/home/steve/llm-optimizations`. Rebuild only packet16's
own ignored build tree when necessary, following its README. Do not alter the
packet13/14/15 sources or their active build trees. No server, port 8188, LTX
unit, device-discovery probe, power or host memory setting is involved.

The completed packet13 baseline passed a CPU-only receipt admission in
[baseline-admission.json](baseline-admission.json), but its step-1 device
fixtures match **0/48** CPU-oracle layer files (first differing layer 0). Its
first token agrees at 332. The W1 command below therefore omits the optional
CPU oracle; adding it correctly refuses this baseline. W2/W3 still require
CPU oracle parity, so this unresolved native arithmetic discrepancy is a
real blocker to passing those gates. This does not authorize a device window:

```bash
P=experiments/own-xpu-runtime/stage2/packet16-decode
PY=/home/steve/.venvs/vllm-xpu/bin/python
BASELINE=experiments/own-xpu-runtime/stage2/packet13-integrate/build/card3-first-token-a/window.json
ORACLE=experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v1-parallel-20261011/incident-retrospective
```

The wrapper verifies the build receipt, its CPU-test receipt hash and minimum
eight-token CPU oracle coverage for both dispatches, every retained source
hash, the device binary hash, the input manifest and every input file before
starting anything.
It records and rechecks the binding after the native process exits. Model
shards are checked by the native loader against the bound identity file. A new
output directory beneath packet16 `build/` is mandatory for each run.

## W1: card 3, one-card streaming, first token

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --window W1 --seconds 10800 \
  --input "$P/build/input" --baseline "$BASELINE" \
  --output "$P/build/w1-card3-a"
```

W1 fixes native arguments to `--card 3 --cards 1 --memory layer-streaming
--stage first-token --max-new 1 --context 128 --nongemv parallel --gemv frozen`. It requires
a completed, passing packet13 card-3 first-token window, its safe native
teardown, all 48 unchanged step-1 fixtures, and the identical prompt. All 48
packet16 layer hashes and the first generated token must match. The optional
`--oracle` additionally checks the frozen CPU oracle; omission is allowed only
for W1. A disagreement between packet13 and the CPU oracle refuses the window
before launch. Step 1 predicts the first answer from the **last** prompt
position, not the first prompt token.

## W2: cards 2+3, resident, frozen GEMV dispatch

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --window W2 --seconds 10800 \
  --input "$P/build/input" --oracle "$ORACLE" \
  --w1 "$P/build/w1-card3-a/window.json" --output "$P/build/w2-cards23-a"
```

W2 fixes `--card 2 --cards 2 --memory resident --stage decode --max-new 64
--context 256 --nongemv parallel --gemv frozen`. The 256-position capacity
holds the 87-token prompt plus all 63 subsequent decode positions. It refuses
to start without a passing W1
receipt from the **same boot, binary and prompt**. The CPU oracle is mandatory:
all 64 tokens and all 384 available layer fixtures (48 layers, steps 1 through
8) must match. Missing fixtures, early EOS and shorter output all fail the
registered coverage. There is no tolerance. The first differing layer fixture
or token is named in `window.json`; site localization requires the separate
checked native diagnostic and is not silently inferred from a final hash.

## W3: cards 2+3, resident, R5 GEMV dispatch

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --window W3 --seconds 10800 \
  --input "$P/build/input" --oracle "$ORACLE" \
  --w1 "$P/build/w1-card3-a/window.json" --output "$P/build/w3-cards23-a"
```

W3 uses W2's fixed topology and coverage with `--gemv r5`. It has its own
oracle gate and measured result. The native per-card memory census must fit
the 30 GiB cap; the wrapper never lowers precision or changes placement to fit.

For a fresh-process repeat, separately admit the same window again, change
the output to a new directory, and append, for example:

```bash
  --repeat-of "$P/build/w2-cards23-a/window.json"
```

The anchor must have passed with the same boot, binary, input manifest,
dispatch, non-GEMV mode, context capacity, arithmetic, oracle hashes and expected tokens. The
repeat must reproduce every fixture hash and all tokens. W2 cannot be used as
W3's repeat anchor. No repeated run is automatically scheduled.

## Measurement and safety receipts

`run/timings.jsonl` has one row per generated token, including the first.
Each row must contain `wall_ms`, `gemv_device_ms`, `non_gemv_device_ms`,
`transfer_wall_ms`, `kernel_submissions` and `host_waits`. The native receipt
separates prefill and first-generated-token timing, then calculates decode
throughput from the whole wall-clock span for generated tokens 2 through N.
Device times are a diagnostic breakdown, never the throughput denominator.
No warmup token is hidden. Fixture capture overhead remains in measured wall
time; this is one prompt's correctness/performance window, not a realistic
suite or a publication-quality speed claim.

The wrapper polls packet2's specific kernel fault signatures every 250 ms;
each journal subprocess has a two-second timeout. A new fault, journal loss,
deadline or signal saves evidence and sends **one SIGTERM to the captured
native PID**. There is no retry or hard kill. Its boot-bound `build/FAULT.json`
refuses later windows on that boot pending coordinator handling. Unsafe or
missing teardown, failed comparisons and changed bindings also latch closed.

The cooperative drain has a 60-second watcher deadline. If the native child
is still alive, the receipt sets `child_still_running=true`, retains its PID,
fails the window and returns control to the coordinator without releasing or
killing that child. Keep that process's owning systemd unit alive; do not infer
idle cards from the wrapper's exit. Every native event/owner wait has its own
bounded drain contract. A clean exit receives a bounded five-second kernel-log
tail (an in-progress journal read can add at most two seconds). One shared-context owner may cover both queues: its native receipt must
say `owner_cards=2`, and teardown must show `safe_to_exit=true`, zero live
bytes and zero in-flight events. External idle/health admission and postflight
remain explicitly the coordinator's responsibility.

Preserve `window.json`, native receipt, timing rows, all step fixtures/hashes,
source/input identities, memory census, stdout and kernel evidence before
cleaning ignored output. A wrapper pass establishes its stated prompt and
coverage only. Fresh-process determinism, broader prompts and a performance
headline each need their own completed evidence.
