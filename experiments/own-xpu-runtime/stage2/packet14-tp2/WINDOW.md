# Packet 14 — coordinator cards 2+3 window

Prepared only; no device command was executed here. The coordinator must
admit both physical unmasked Level Zero cards 2 and 3, wait for packet 13's
card-3 owner to exit cleanly, and resolve current host/fault restrictions.
Do not use packet 13's running build as scratch or overlap its owner. No server,
Docker, power change, driver reset, port 8188 or LTX operation is involved.
Use the coordinator's approved long-job supervision. These commands never
create a systemd unit themselves and do not authorize a device window.

## CPU preparation

From the repository root:

```bash
P=experiments/own-xpu-runtime/stage2/packet14-tp2
PY=/home/steve/.venvs/vllm-xpu/bin/python
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/build.py" --keep-build
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B \
  experiments/own-xpu-runtime/stage2/packet13-integrate/prepare.py \
  --output "$P/build/input"
```

The second command reads only existing admitted shard metadata/tokenizer
headers at idle I/O priority and creates a fresh **packet-14** input directory.
It downloads nothing and does not touch packet 13's build. It recreates the
same 87 prompt IDs, vocabulary and stat-bound read-only GGUF plan.

Set `BASE` to the **completed passing packet-13 card-3 first-token window.json**
selected by the coordinator. It must contain the same prompt hash, arithmetic
`iq3-p13-r234-sg32-split4-bf16-v1`, its saved `run/receipt.json`, all 48
`run/step1/layer-XX.bf16` files, the first token and clean one-owner teardown.
A running, failed, stale or modified result is refused before device discovery.
Use this same baseline for both commands below.

```bash
BASE=/absolute/path/to/completed-packet13-card3-window/window.json
```

## First device command: layer 0

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --card 2 --cards 2 --memory tp2-streaming \
  --stage layer --seconds 3600 --input "$P/build/input" \
  --baseline "$BASE" --output "$P/build/cards23-layer-a"
```

This runs the entire frozen prompt through layer 0, not a selected easy token.
It compares the final layer's 20,480 BF16 bytes with packet 13's saved one-card
result and requires both Arena teardown receipts. The watcher binds sources,
native binary, input files and baseline fixture hashes. It saves per-rank
allocation census and all timing rows. `oracle_exact=true` here means equality
to that packet-13 single-card result; it is **not a real-model CPU-oracle pass**.

Review that receipt and the independent coordinator idle/health check before
admitting the next command. Nothing queues the next stage automatically.

## Second device command: first token

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 "$PY" -B "$P/window.py" \
  --authorized-device-window --card 2 --cards 2 --memory tp2-streaming \
  --stage first-token --seconds 10800 --input "$P/build/input" \
  --baseline "$BASE" --layer-gate "$P/build/cards23-layer-a/window.json" \
  --output "$P/build/cards23-first-token-a"
```

Requires the passing layer gate on this boot, this binary, input and baseline.
Processes all 87 prompt positions through all 48 layers and emits **one** greedy
token. Compares all 48 final-position layer files plus that token against packet
13. No ignored mismatch, relaxed tolerance, CPU-oracle rewrite or automatic retry.

For a separately admitted fresh-owner repeat, use a new output directory and
`--repeat-of "$P/build/cards23-first-token-a/window.json"`. A later full
real-model CPU oracle comparison and complete quality/repeat suite remain open;
`real_model_qualified=false` is mandatory even after these diagnostic gates.

## Timing and admission limits

Timing is always on; no special speed flag relaxes exactness. Read
`run/timings.jsonl`:

- `rank_layer`: GEMV and non-GEMV device milliseconds per logical rank (0 is
  physical card 2, 1 is physical card 3).
- `exchange_layer`: actual peer payload bytes and wall milliseconds per layer.
- `layer`: complete synchronized wall time, summed device diagnostics and
  staging/readback wall time. Token rows include the head/final mixer.

Both projection kernels are submitted before waiting. Other eager scalar
operations, validation, local slot scatters and streamed weight uploads add
overhead. Never subtract card-2 timestamps from card-3 timestamps, or claim a
speedup from `max(sum(rank0),sum(rank1))`. The [README prediction](README.md#exchange-bytes-and-timing-prediction)
explicitly accounts for the extra gathers; the earlier 1.5× estimate is not an
acceptance result. Compare matched full layer wall times, separating GEMV-only
kernel evidence from actual prompt processing. No headline from one owner pair.

Per-card owned allocations are capped at 30 GiB, with 4 MiB pinned slabs and
bounded reads. This cap is not a measured-fit or host-memory admission receipt.
The coordinator must independently admit driver/file-cache overhead and retain
the host's free-memory/storage requirements. Weights stream one layer at a time.

## Failure and teardown

The watcher uses packet 2's specific kernel-fault signatures, a five-second
postflight tail and a boot-bound fault latch. Fault, journal loss, deadline or
interrupt sends **one SIGTERM to the captured PID**, never a group kill or
restart. Unsafe/missing teardown retains the latch. No power, memory/swap,
page-cache, driver, firmware or reboot changes occur.

The peer bridge drains both producers and keeps both Arena endpoints live
until its copy completes. A failed/expired copy poisons both owners. Any owner
that cannot drain stays alive for its supervisor; the timeout is not permission
to free busy GPU memory. The shared context outlives both owners' allocations,
events and queue wrappers. Preserve all device windows, latches and faults;
the CPU builder refuses to delete a tree containing those records.
