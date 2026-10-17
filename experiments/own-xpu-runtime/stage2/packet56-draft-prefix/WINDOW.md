# Packet56 coordinator windows

Preparation runs no GPU, service or health probe. The coordinator owns all
commands below and runs them only after packet49d releases the cards and host
memory. Preserve `p49d-chain-cards01-a` and its entire output tree. No command
here stops, edits or reseals a parent.

## Head K windows on card 0

Run in two separate coordinator-owned `packet56-*` systemd user units with
graceful SIGTERM and `SendSIGKILL=no`. `REVIEWED_THROUGH` is the coordinator's
actual reviewed UTC fault boundary for this boot, not an automatic waiver of
new faults. Keep the approved `LD_LIBRARY_PATH`; no runtime debug overrides.
Release all other visible Xe clients first. The wrapper checks ownership,
memory, free space, source/binary seal, journal and graceful teardown.

From the repository root, inside the first admitted unit:

```bash
P=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
nice -n 19 taskset -c 4-15,20-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/p56_head_window.py" --authorized-device-window --card 0 \
  --faults-reviewed-through "$REVIEWED_THROUGH" --output "$P/evidence/head-k-a"
```

After it exits successfully and at least 90 seconds have passed, use a fresh
admitted unit and the second new output path:

```bash
P=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
nice -n 19 taskset -c 4-15,20-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/p56_head_window.py" --authorized-device-window --card 0 \
  --faults-reviewed-through "$REVIEWED_THROUGH" --output "$P/evidence/head-k-b"
```

Each window measures **32,768;65,536;98,304;91,392;248,320 rows** using the
same production p33 expanded-Q6 head and round2 argmax. It uses one synthetic
839,321,600-byte head allocation, 108 changed-input passes (8 warmup plus 100
timed), and compares every prefix logit and proposal to the full-head result.
The two fresh owners must have identical exact output identities. The warmup
is operator initialization only; this is a diagnostic microbenchmark and
cannot become a model performance claim. N never depends on these timings.
Raw event times and separate head/argmax medians are retained for all sizes.

## Full chain on cards 0+1

In an admitted nice 0 systemd user unit on cores 0–3,16–19, with
`OMP_NUM_THREADS=2` and the approved `LD_LIBRARY_PATH`, from the repo root:

```bash
P=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
OUT=/home/steve/own-xpu-runtime-results/packet56-draft-prefix/build/device-cards01-a
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/storage_precheck.py"
bash "$P/coordinator_windows.sh" --phase all --output-root "$OUT" --wait-oracle \
  --prefix-windows "$P/evidence/head-k-a/window.json" "$P/evidence/head-k-b/window.json"
```

The exact inherited order is **K0→K1a→K1b→K2→W0p→KD→W2m→WS→WSs→WS128x→WS128**.
The existing oracle remains
`/home/steve/own-xpu-runtime-results/packet49-integrate/oracle/results`.
KD recomputes only the draft reference on the existing target captures;
no new target-oracle job is launched. All 12 prompts must equal the same
packet49 oracle; target split 23/25, draft rank 1, capacity 4096 and full BF16 KV
are fixed. No target/draft prompt reuse is introduced.

The runner retains 90-second K and 305-second W cooldowns, fault checks,
cooperative teardown and no retries or output overwrites. Two distinct path
names alone do not establish freshness: both owner PID/start identities and
the exact output identity are verified. A failing device check stops the chain.
CPU-only command inspection executes nothing:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/queue_runner.py" \
  --phase all --output-root "$OUT" --plan
```

Keep all failed evidence. Do not use a fresh name to automatically retry a
fault. The coordinator applies the lab's evidence-first recovery rules.
After completion, use [the submission tooling](SUBMISSION.md), which reads
the latest pinned submitted-record floor. A speed result needs the exactness
companions and same 12-prompt 128-token scope; the strict 512-token gate is false.
