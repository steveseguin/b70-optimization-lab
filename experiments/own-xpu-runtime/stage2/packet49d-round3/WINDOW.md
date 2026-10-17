# Packet49d coordinator runbook: cards 0+1

The preparer runs no GPU, service or health probe. The coordinator schedules
these windows after 49c and packet54 finish, with exclusive ownership of cards 0+1.
Leave `/home/steve/own-xpu-runtime-results/packet49c-round2/build/device-cards01-a`
and `p49c-model-cards01-e` untouched. This runbook never stops a parent chain.

## Selection and fast reseal

Run from the repository root after the packet54 T1/T2 windows in its sealed
coordinator runbook have completed.

```bash
P=experiments/own-xpu-runtime/stage2/packet49d-round3
P54=experiments/own-xpu-runtime/stage2/packet54-compute/evidence
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/selection_gate.py" \
  --windows "$P54/p54-a-t1/window.json" "$P54/p54-a-t2/window.json"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/p49_seal.py" --fast-reseal
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/p49_seal.py" --verify
```

The first command revalidates both owners, exactness companions, sealed
source/binary identities and raw timing rows, then writes
`selection-decision.json` and `selection.json`. It selects the same common
candidate as packet54, or production. Packet54's separate 25us bar is not a 49d
requirement: combined 40us in both owners is decisive. Missing or failed
receipts keep device admission closed.

Fast reseal checks the CPU gates and build bindings; it runs no compiler,
numerical fixture, device or model. Target: under 10 minutes. It binds the chosen
JSON bytes and timing decision into `build-receipt.json`, then pins 49d's own
runtime revision, seal and selection in `scripts/packet49_submission_pins.json`.
A final seal or started chain cannot be overwritten. Commit and push the
selection, decision, final seal and pin before launching windows. Every model
owner verifies the sealed selection hash over the same bytes it parses at init.

## Storage and early phase

The 49b reserve is retired; 49c will be complete and the oracle is already complete.
Precheck reserves this packet's own chain and 8GB root free floor with a 1.5GB
build cap. It does not reserve finished/superseded parent writes. Do not delete
parent evidence to make room.

In the coordinator's admitted nice 0 systemd user unit on cores 0–3,16–19,
with `OMP_NUM_THREADS=2` and the approved `LD_LIBRARY_PATH`:

```bash
P=experiments/own-xpu-runtime/stage2/packet49d-round3
OUT=/home/steve/own-xpu-runtime-results/packet49d-round3/build/device-cards01-a
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/storage_precheck.py"
bash "$P/coordinator_windows.sh" --phase early --output-root "$OUT"
```

Sequence: **K0 → K1a → K1b → K2 → W0p**. Each K1 runs six fresh fixture
processes, including all 49d choices. K2 measures all new selectable choices and
banked winners versus production in addition to inherited dispatch candidates.
The selected table is accepted only after complete byte/timing coverage.
The sealed two-owner decision controls selection; K2 cannot change it from one
owner's timing. Keep every measurement, including slower choices. Operator
measurements do not establish model speed.

CPU-only command inspection:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/queue_runner.py" \
  --phase early --output-root "$OUT" --plan
```

## Model phase

After the early unit exits successfully, use a new admitted coordinator unit
with the same affinity, priority and environment:

```bash
P=experiments/own-xpu-runtime/stage2/packet49d-round3
OUT=/home/steve/own-xpu-runtime-results/packet49d-round3/build/device-cards01-a
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/storage_precheck.py"
bash "$P/coordinator_windows.sh" --phase model --output-root "$OUT" --wait-oracle
```

Sequence: **KD → W2m → WS → WSs → WS128x → WS128**. The existing oracle is
`/home/steve/own-xpu-runtime-results/packet49-integrate/oracle/results`.
Every model window revalidates its completion and hashes; no new oracle runs.
Keep capacity 4096, target split 23/25, draft rank 1 and full BF16 KV. The queue
retains 90-second K and 305-second W cooldowns, fault checks, graceful teardown,
no retries and no output overwrites. Only this chain path is registered.

## Submission threshold

After the 49c decision, record a successful actual submission:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B scripts/packet49_submission.py \
  --update-record /absolute/path/to/49c/submission/prepared/result.json \
  --submission-id ACTUAL_SUBMITTED_RECORD_ID
```

If 49c is not submitted, leave the ledger unchanged. 49d preparation reads
`scripts/packet49_record_threshold.json`, snapshots its hash and requires a
strict improvement over its latest submitted result. The updater validates the
bound result and increasing ledger; it performs no network operation.

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B scripts/packet49_submission.py \
  --packet packet49d-round3 --chain "$OUT" \
  --output "$P/submission/prepared"
```

This creates reviewable submission evidence only. The coordinator retains
responsibility for real submission and the owner-authorized 128-token scope;
the strict 512-token final gate remains false.
