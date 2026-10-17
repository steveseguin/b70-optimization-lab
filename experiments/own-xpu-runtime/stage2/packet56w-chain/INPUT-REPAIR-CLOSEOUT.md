# packet56w-chain: full-chain input repair — closeout

<!-- campaign-closeout -->

## Question and identity

October 17, 2026, CPU-only repair on steve-b70s. Packet61 stopped at K1a with
`fixture list missing`; K0 had passed. The packet56 fixture link resolved to
packet45's directory, but its files had been archived during cleanup. The
copied chain also omitted a local fixture link and relied on the binary's
compiled default path. Screen plans did not exercise those inputs.

The target remains the IQ3 quantized compressed model, packet49 split32
arithmetic, BF16 intermediates/KV, full target head, 91,392-row draft prefix,
and the existing packet49 oracle. Device windows remain coordinator-owned.

## Outcome

CPU preparation passes. The checker resolves **10,578 static file paths** across
all **11 windows**, with no missing files or hash errors. All **35 focused tests**
pass. The original engine artifact map and screen seal are unchanged.

The existing registered `device-cards01-a` output remains fresh and absent.
This repair stays inside this packet; it does not modify another candidate's
engine or screen seal.

No GPU, model payload read, service, sudo, host setting change, process kill or
reboot was used. Work ran with nice 19, cores 8–15/24–31 and Python `-B`.

## What worked

- Restored `cases.txt`, all 72 non-GEMV fixtures and their original manifest:
  74 files, 211,592,427 logical bytes. Every byte matches the cleanup archive's
  original hash. Packet61 owns the restored copy; 61x and 56w hardlink those
  exact files. The archived parent directory stays untouched.
- K1a/K1b/K2 now pass explicit `--fixtures build/fusion-fixtures`. K2 uses the
  same fixture inputs. KD's input bundle, capture table, all captured target
  streams and host/device binaries are already present and were verified.
- `check_inputs.py` checks fixture members, sealed source/build files,
  input bundles, model files (stat only), tensor extents, draft files,
  dispatch inputs, oracle source/completion/12 prompt outputs and all retained
  layers, prefix-head raw evidence, current boot and distinct prefix owners.
- `--plan` and the queue's launch path run the checker. Earlier-window receipts
  and measured dispatch are explicit producer dependencies; they need not exist
  before the chain starts, but must exist before their consumer launches.
  Compressed or hash-only retained evidence follows its recorded physical files.
- The chain wrapper seal now binds fixture inputs. Wrapper-only resealing
  rejects any change to engine bytes, arithmetic, target oracle or screen
  identity and preserves previous seals. Storage counts local builds as well
  as external outputs, keeping the original reserves.

The screened engine changes waits, not target arithmetic. Its K1/K2 operator
programs and fixture bytes remain packet56's. Full-model target quality and
fresh-process checks still require the coordinator's complete chain.

## What failed or remains uncertain

The original failure is preserved, not retried. System Python lacked pytest;
the existing `/home/steve/.venvs/vllm-xpu/bin/python3 -B` ran the tests instead.
No new package was installed. CPU preflight proves file readiness, not device
quality or speed. Dynamic loader checks and fault/host admission still run in
the existing coordinator window.

Storage passed with **3,760,622,827 bytes** above its required
reserve at the recorded check. This is a snapshot, not permission to bypass
storage checks or run these chains concurrently.

## Evidence and patches

- [Exact input manifest and archive identity](input-fixtures.json).
- [Input-check output](evidence/input-check-summary.json),
  [full path inventory, gzip JSON](evidence/input-check.json.gz).
- [Seal/build/STOP verification and tests](evidence/input-repair-verification.json),
  [test output](evidence/input-repair-tests.txt),
  [full queue plan](evidence/input-repair-queue-plan.txt),
  [prefix/oracle/storage plan](evidence/input-repair-plan.json).
- [Original chain seal](evidence/input-repair-original-build-receipt.json) and
  [original submission pins](evidence/input-repair-original-submission-pins.json)
  preserve the admission identity used before this repair. Additional digest-named
  pre-reseal snapshots preserve intermediate CPU-only wrapper revisions.
- [Checker](check_inputs.py), [exact-byte restoration](prepare_inputs.py),
  [queue](queue_runner.py), [window](window.py), [seal](chain_seal.py).

To restore missing local fixture inputs before this registered chain starts:

```bash
P=experiments/own-xpu-runtime/stage2/packet56w-chain
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/prepare_inputs.py"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/check_inputs.py"
```

The original archive is local and retained, not embedded in Git. Its exact
absolute path, hash and every member hash are in `input-fixtures.json`.
The path inventory is gzip-compressed only for repository size; decompress
with any gzip reader to inspect every resolved file and window mapping.

## When to revisit

The coordinator can run the following inside its admitted nice-0 user unit on
cores 0–3,16–19, with OMP_NUM_THREADS=2 and the approved library path:

```bash
P=experiments/own-xpu-runtime/stage2/packet56w-chain
HEAD=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
OUT=/home/steve/own-xpu-runtime-results/packet56w-spin/build/device-cards01-a
bash "$P/coordinator_windows.sh" --phase all --output-root "$OUT" --wait-oracle \
  --prefix-windows "$HEAD/evidence/head-k-a/window.json" "$HEAD/evidence/head-k-b/window.json"
```

For CPU-only command admission, replace the `bash` line and its arguments with:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/queue_runner.py" \
  --phase all --output-root "$OUT" --plan
```

Order: K0 → K1a → K1b → K2 → W0p → KD → W2m → WS → WSs → WS128x → WS128.
There is no automatic retry and no reuse of a stopped output. Re-run input
and storage checks after any input relocation, cleanup or boot change.
