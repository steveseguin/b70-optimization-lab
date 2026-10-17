# Packet49b coordinator runbook: cards 0+1

The coordinator runs these commands inside its admitted nice-0 user unit on
cores **0–3,16–19**, with its approved `LD_LIBRARY_PATH`. The preparer runs no
GPU work, health probe or service command. Every window retains OMP threads2,
capacity4096, split23, draft rank1, BF16 KV, the 30 GiB arena cap and the memory
guards. Do not run another chain on these cards at the same time.

Use the new chain below for both phases. Never reuse packet49's chain. The
queue waits 90 seconds after K windows and 305 seconds after W windows. It
requires successful qualifying receipts, stops on the first failed window or
new fault signature, and never retries or overwrites a window. A STOP file
requires coordinator review. Existing windows own cooperative stop/teardown.

## Early phase: run now after coordinator admission

From `/home/steve/llm-optimizations`:

```bash
P=experiments/own-xpu-runtime/stage2/packet49b-gemv
OUT=/home/steve/own-xpu-runtime-results/packet49b-gemv/build/device-cards01-a
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/storage_precheck.py"
bash "$P/coordinator_windows.sh" --phase early --output-root "$OUT"
```

Stop if the storage check fails. This runs **K0 → K1a → K1b → K2 → W0p**.
K1a/b each run four sequential fresh fixture owners: non-GEMV, linked dense,
split32 QSA, and the new expert path. The expert fixture checks M=1 and both
separately scheduled M=2 rows against unchanged P39 arithmetic, including
routes, status, inactive rows and sticky errors. All output bytes must match
the sealed CPU output. K2 keeps its fresh recommendations separately and
preserves SPEED6 dispatch strings; explicit QSA/expert engine overrides are
qualified by the new K1 fixtures. W0p is the oracle-free transport canary.

Inspect argv without a device or service:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/queue_runner.py" \
  --phase early --output-root "$OUT" --plan
```

## Model phase: same chain, same packet49 oracle

```bash
P=experiments/own-xpu-runtime/stage2/packet49b-gemv
OUT=/home/steve/own-xpu-runtime-results/packet49b-gemv/build/device-cards01-a
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/shared_oracle.py" --require-complete
bash "$P/coordinator_windows.sh" --phase model --output-root "$OUT" --wait-oracle
```

The status command validates the original outputs of
`own-iq3-p49-oracle-20261017b.service`. It neither starts nor modifies the unit.
The queue can wait while the oracle is still running; it holds no device
owners while waiting. A failed oracle or broken hash binding stops the chain.
The sequence is **KD → W2m → WS → WSs → WS128x → WS128**.

Every model window records `shared_oracle`, including the exact completion,
suite-manifest, determinism and KD-capture hashes. W2m uses the first prompt's
64-token prefix. Suite windows use all twelve registered prompts with 128
generated-token capacity, context4096, repeat1. WS128x retains steps1–8 and
97–104. WS128 requires that exactness companion and retains no layer fixtures.
Its summary reports `class_balanced_tok_s_1_100_intervals_after_ttft.median`
and `submission100_statistics.median`. `submission_tok_s` is the class-balanced
99-interval primary; the legacy `decode_tok_s` remains the labeled reference64
rate, not the primary. Prompt/output hashes, timestamps and accounting remain
unchanged. The 39.422 record is preserved until a matching qualified result
exists. The separate 512-token publication gate stays false.

A single combined queue is also available:

```bash
bash "$P/coordinator_windows.sh" --phase all --output-root "$OUT" --wait-oracle
```

Choose combined or split, never both. The split phases preserve the cooldown
and require the same build/environment/boot. Rebooted prerequisites refuse.

## Storage admission

[The budget](ARTIFACT-RETENTION.md) reserves 8 GB free, 5.819 GB for packet49's
remaining model writes, and 0.500 GB for oracle growth. Packet49b budgets a
2.500 GB build plus a 5.947 GB peak chain. Early oversized fixture scratch is
hashed and discarded by the inherited verified retention policy; the queue
checks a 128 MB retained early-evidence cap, including root logs. Exceeding it
preserves evidence and stops rather than deleting more or silently growing
the budget. Each window rechecks actual free space before writes.

Packet49's sealed storage policy is unchanged and still requires its larger
11.486 GB reserve. This packet's fit does not promise that packet49's own
later admissions will pass after other work writes to root. Coordinate the
chains serially and recheck current space; a refusal needs regenerable
closed-packet scratch review, not alteration of the running oracle or seals.
