# Packet 13 — coordinator's real-model window

These commands are prepared, **not executed**. The coordinator must admit
physical card **3**, confirm exclusive ownership and resolve any host fault
halt first. Preserve other owners, LTX, port 8188, power and host settings.
No server or automatic retry is involved. Use the coordinator's already
approved supervision for this potentially long job; an agent shell is not
the GPU job owner. This document does not authorize a reboot or driver reset.

## Prepare on CPU

Run from `/home/steve/llm-optimizations` with the installed oneAPI environment
available for the later device command. No network or model download is needed.
The default build removes scratch, so recreate it before the admitted window:

```bash
P=experiments/own-xpu-runtime/stage2/packet13-integrate
PY=/home/steve/.venvs/vllm-xpu/bin/python
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/build.py" --keep-build
```

The build validates the CPU mini-model and compiles SYCL without running it.
`build/input` contains the complete oracle first prompt (87 IDs), vocabulary,
GGUF plan and frozen shard identity. The wrapper verifies source, binary and
input hashes before starting a child. Every output directory must be new.

## Card 3: full-model layer-streaming first-token command

After admission, run once:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --card 3 --cards 1 --memory layer-streaming \
  --stage first-token --seconds 10800 \
  --input "$P/build/input" --output "$P/build/card3-first-token-a"
```

This is a **bounded diagnostic**, not a speed configuration. It processes the
entire prompt through all 48 layers and requests eight greedy output steps.
The default context is 128. Dense/control weights are staged first for each
layer, then only routed expert slots; all layer weights are released before
the next layer. Copies use a 4 MiB pinned slab. The calculated owned device
peak is 880,477,352 bytes, excluding driver memory; the allocator also enforces
a 30 GiB cap. No bank pruning, KV compression or automatic fitting occurs.

The native run writes token IDs, 384 hidden-state files/hashes if all eight
steps complete, and separate GEMV/non-GEMV device times plus transfer and wall
times in `run/timings.jsonl`. EOS may reduce coverage and must be reported.
There is deliberately no old BLAS-oracle gate. Native output identity is still
pending. To compare after rebasing, add `--oracle /path/to/rebased-oracle-root`
with matching `arithmetic.json` (version and `arithmetic_sources` from the build
receipt), `input.json`, `result.json`, and all `stepN/layer-XX.bf16` files.

For localization only, `--stage layer --seconds 3600` runs all prompt positions
through layer 0. It is not a substitute for the full-model command above.

After a completed window and clean external postflight, a **separately admitted
fresh process** can use the same command with a new output path and
`--repeat-of "$P/build/card3-first-token-a/window.json"`. Every hash and token
must repeat. Nothing queues or launches that repeat automatically.

## Later: cards 2+3, resident weights

Only after coordinator admission of **both** cards and review of the one-card
diagnostic, run this separately registered later step:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --card 2 --cards 2 --memory resident \
  --stage first-token --seconds 10800 \
  --input "$P/build/input" --output "$P/build/cards23-first-token-a"
```

The calculated owned peaks are 26,477,351,920 and 26,776,493,896 bytes,
plus a 4 MiB pinned slab per owner; actual fit remains unmeasured. This is
resident **sequential layer placement**, the control retained by
[TWO-CARD-TP.md](../TWO-CARD-TP.md), not the unimplemented within-layer TP path.
It uses ordered host-bounce handoffs and exactly the one-card arithmetic.
It needs its own fresh-process repeat before a speed verdict. No projection
or warm operator number is a full-model performance result.

## Fault latch, cooperative stop and teardown

The wrapper watches the kernel journal every 250 ms using packet 2's specific
fault signatures. A new fault, journal loss, deadline, SIGINT or SIGTERM saves
evidence and sends **one SIGTERM to the captured child PID**. It never kills a
process group, retries, clears a coredump or resets a driver. Its boot-bound
`build/FAULT.json` blocks another window until the coordinator handles recovery;
do not delete or override it to continue. Missing/unsafe teardown also latches.

The runtime stops submissions at cooperative boundaries. Each operation wait
and owner shutdown has a 60-second drain bound. A stuck owner is retained for
the supervisor; **10,800 seconds is a submission/window deadline, not permission
to free busy memory or promise a hard process exit**. No automatic hard kill.

Require every owner's receipt to show `safe_to_exit=true`, zero live bytes and
zero in-flight events. Shutdown is quiesce → drain → graph leases → allocations
→ final idle marker → events → queue → context. The wrapper saves a five-second
post-exit journal tail. The coordinator must separately verify idle/health on
the admitted cards; `external_idle_health_still_required=true` remains explicit.

Copy the window JSON, native receipt, model/input/arithmetic identity, timings,
all step hashes/fixtures, stdout, kernel logs and memory census outside ignored
build storage before cleanup. Leave the cards empty. A diagnostic pass does not
establish oracle parity, fresh-process determinism or a publishable benchmark.
