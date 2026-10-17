# Packet56w coordinator chain

The coordinator owns device admission, exclusive host scheduling and the
durable systemd user unit. This preparation starts no unit or device job.
The runner requires a nice-0 parent on cores **0–3,16–19**, `OMP_NUM_THREADS=2`,
and the already approved `LD_LIBRARY_PATH`. It preserves 90-second K and
305-second W gaps, cooperative teardown, fault checks and no automatic retries.

From the repository root, first run the CPU-only storage check:

```bash
P=experiments/own-xpu-runtime/stage2/packet56w-chain
OUT=/home/steve/own-xpu-runtime-results/packet56w-spin/build/device-cards01-a
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/storage_precheck.py"
```

**Storage currently refuses admission.** The unchanged packet56 budget requires
15,446,804,480 free bytes before this new chain; about 11.96 GB was available
during preparation, a shortfall of about 3.48 GB. The 8 GB free floor, 1.5 GB
build reserve and complete chain reserve are retained. Recheck at launch;
do not bypass the check or delete other jobs' evidence.

After storage passes, inside the admitted coordinator unit:

```bash
P=experiments/own-xpu-runtime/stage2/packet56w-chain
HEAD=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
OUT=/home/steve/own-xpu-runtime-results/packet56w-spin/build/device-cards01-a
bash "$P/coordinator_windows.sh" --phase all --output-root "$OUT" --wait-oracle \
  --prefix-windows "$HEAD/evidence/head-k-a/window.json" "$HEAD/evidence/head-k-b/window.json"
```

Order: **K0 → K1a → K1b → K2 → W0p → KD → W2m → WS → WSs → WS128x → WS128**.
The two parent head windows are reused because the prefix and its arithmetic
are unchanged. Their raw native rows, hashes, two fresh process identities and
boot identity are checked. They verified on the preparation boot; a later boot
does not silently waive this gate. All eleven chain windows are fresh packet56w
outputs. Nothing is taken from the screen as qualifying chain evidence.

The unchanged shared oracle is
`/home/steve/own-xpu-runtime-results/packet49-integrate/oracle/results`.
KD recomputes only the unchanged prefix draft reference from its target
captures. No new target-oracle job is started. WS128 is paired with retained
WS128x exactness and must exceed the current pinned record before submission
preparation can succeed.

CPU-only checks, safe outside the coordinator unit:

```bash
P=experiments/own-xpu-runtime/stage2/packet56w-chain
OUT=/home/steve/own-xpu-runtime-results/packet56w-spin/build/device-cards01-a
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/chain_seal.py" --verify
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/queue_runner.py" \
  --phase all --output-root "$OUT" --plan
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/plan_gate.py"
```

`plan_gate.py` reports identity/wiring and storage separately: a successful
plan never overrides a failed storage admission. It launches no binary,
queries no device and creates no chain output. To restore missing local build
links before a chain starts, use `nice -n 19 taskset -c 8-15,24-31 python3 -B
"$P/prepare_chain.py"`. Seals are never overwritten.
