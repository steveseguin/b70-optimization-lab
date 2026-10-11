# First integrated device window — coordinator runbook

**Preparation only. No command below was run on a GPU by this job.** The
coordinator owns exclusive card admission, host health, journal access and
postflight. Do not touch LTX/port 8188, other cards' work, servers, power,
host-memory settings, driver/reset/reboot or the competing shard readers.
The current real-layer CPU hash does **not** match the oracle. The first layer
window is diagnostic; it cannot pass or advance stages unless exact agreement
is actually obtained. Never change the oracle or add a tolerance to get past it.

## Admission and identity

Use physical **card 3**, one B70, while the coordinator has admitted it as clean
and exclusive. Packet 2's 108 bit-exact device checks are primitive evidence,
not a whole-layer gate. Preserve any host fault halt until the coordinator has
resolved it. No device query/health probe is run by this packet's CPU builder.

The shell must use nice 19, idle I/O priority and `OMP_NUM_THREADS=2`. Existing
shards remain read-only; the helper validates the frozen admission stat identity
and tokenizer header hash without rehashing the 82 GB payload. Rebuild locally
before using the sealed binary; no stale binary/hash override is provided.
Driver shadows and free VRAM must be admitted separately. The first layer's
weights plus request buffers fit the program's 30 GiB/card allocation cap in
arithmetic; this is not a native fit result. One-card full-model execution
streams one layer at a time. No automatic fitting, retry or device reset exists.

```bash
P=experiments/own-xpu-runtime/stage2/packet4
PY=/home/steve/.venvs/vllm-xpu/bin/python
ORACLE=experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle/runs/official-sigmoid-20261011/incident-retrospective/step1
# CPU builds/tests and bounded tokenizer header preparation only:
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/build.py" --keep-build
```

The builder creates `build/input/{tokens.txt,vocab.bin,plan.tsv,identity.tsv,input.json}`.
The input must match the oracle's complete 87-token prompt, not a one-token
suffix. `window.py` verifies build/source/input hashes and covered oracle files
before starting any child. Its output directory must be new. The script contains
no Docker, systemd or server command. Use the coordinator's approved supervisor
for a long device job; do not attach one to an agent shell.

## Stage 1: complete prompt through first layer

**First device command, after coordinator admission:**

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --card 3 --stage layer --seconds 600 \
  --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/card3-layer-a"
```

At most 600 seconds. This uploads the first layer, runs every prompt position
through that layer, and writes `run/step1/layer-00.bf16`. Require exactly
20,480 BF16 bytes with the oracle's hash and no sticky errors, out-of-bounds
status, nonfinite output, journal fault or incomplete teardown. Capture all
failed evidence, including differences from the retained CPU integration array.
That array's hash is not a replacement gate for the independent oracle.

After a pass and clean coordinator idle postflight, run a fresh process once:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --card 3 --stage layer --seconds 600 \
  --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/card3-layer-b" \
  --repeat-of "$P/build/card3-layer-a/window.json"
```

Both runs must pass on the same boot, card, binary, prompt and oracle hashes.
Failure closes this preregistered attempt; it does not queue or cycle a process.
Localize with CPU/operator evidence before registering another candidate.

## Stage 2: one full generated token

Only after the layer repeat passes, all 48 oracle layer files exist, the oracle
has its first generated token, and the coordinator admits the streaming window:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --card 3 --stage token --seconds 3600 \
  --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/card3-token-a" \
  --previous-window "$P/build/card3-layer-b/window.json"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --card 3 --stage token --seconds 3600 \
  --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/card3-token-b" \
  --previous-window "$P/build/card3-layer-b/window.json" \
  --repeat-of "$P/build/card3-token-a/window.json"
```

At most 3,600 seconds per process. All 48 last-prompt-position hidden states
and the first greedy token must be byte/ID exact, repeated in fresh processes.
This includes the full prompt prefill, not merely evaluating its last token.
A timeout is a failed diagnostic attempt, never a performance extrapolation.

## Stage 3: eight generated tokens

Only after the full-step repeat and oracle coverage of eight tokens:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --card 3 --stage eight --seconds 10800 \
  --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/card3-eight-a" \
  --previous-window "$P/build/card3-token-b/window.json"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --card 3 --stage eight --seconds 10800 \
  --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/card3-eight-b" \
  --previous-window "$P/build/card3-token-b/window.json" \
  --repeat-of "$P/build/card3-eight-a/window.json"
```

At most 10,800 seconds per process. Require all eight token IDs, EOS behavior,
step-1 hidden hashes and fresh-process output identity. Never manufacture eight
tokens if EOS ends the oracle early; revise the registered coverage explicitly.
Two cards are the primary runtime target, but two-card execution needs its own
coordinator admission after these layer/operator gates; the compiled CLI exposes
`--cards 2 --card 2` for physical cards 2 and 3. These commands are correctness
bring-up, not the realistic-suite speed or publication gates.

## Stop, fault latch and ownership

The watcher uses packet 2's exact journal fault signatures/cursor boundary and
polls every 250 ms. First fault, unavailable journal, SIGINT/SIGTERM or deadline
sends **one SIGTERM to the captured child PID**, stopping new submissions. It
never hard-kills, retries, unloads a driver, clears a coredump or reboots. New
fault evidence latches `build/FAULT.json` for the current boot and refuses later
windows. The coordinator owns evidence-first recovery; this packet does not
clear the latch or run a health probe automatically.

The executable drains every submitted event, then uses the same owner shutdown:
quiesce → drain → graph leases → scratch/state/weights/staging release → final
idle marker → events → queue → context. Completed-event retirement between eager
segments cannot retire pending work or graph leases. SIGTERM is checked between
bounded copies, matrix tiles on CPU and native operator submissions. Native
operation waits and shutdown each have a 60-second bound. If ownership still
cannot safely close, it stays alive for the supervisor; the watcher continues
saving evidence. A deadline is not permission to abandon busy GPU memory.

Require the full teardown receipt (`safe_to_exit=true`, zero live bytes/events),
a clean five-second post-exit journal window, and the coordinator's external
idle/health postflight after each run. `external_idle_health_still_required=true`
is intentional. No server is left running and no claimed pass substitutes for
that postflight. Copy deliberate evidence outside ignored `build/` before
removing regenerable binaries/scratch after the coordinator's window.
