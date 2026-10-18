# Packet137: exact token-input preparation

Final CPU qualification passed. Device quality and speed remain pending.
The supported entry is `v5/bracket_job.py`; copied historical root launchers
are not a packet137 device admission path. No live queue is modified.

The base is packet136 bundle8 (`3dfcff0ca`), with fixed banked rollback in all
views. It committed during this task, after the initial packet124c copy.
`parent136-binding.json` records the adopted inputs. All 182 original symlinks
remain verbatim on this host and in the `parent-manifest.json` inventory.
The final seal checks every link target. Source links are tracked; inherited
build-cache links and generated caches stay outside Git. Frozen trees were
not edited.

## Exact mechanism

`token_input=original|draft_table|target_buffers|both` is the sole switch.
All resources exist before the first control and remain across every view.
The table holds every one of the 248,320 vocabulary IDs, each 2,560 BF16
values. The original single-row normalization and projection produce it.
GNU and Intel replay all rows byte for byte; no GEMM substitution is used.
A 5,120-byte pinned row uploads directly to the existing private projection
buffer instead of uploading the raw embedding. Thirty-two vocabulary-wide
rows must match the original device path before the runtime reports ready.

Rank0 retains `warm_lookups()` and uses pre-resolved descriptors, fixed
decode buffers and exact block decoding. Signed PLE remainder, EOS history
and device rollback are retained. No 29 GB PLE table is added. The draft
never calls target `prepare_token()`. KV remains BF16.

Each boundary retains and resets the old request before canonicalizing bank
roles. It rebuilds all six existing captures without allocating banks. The
bank reserve replaces equal-sized backup bytes, so its net arena change is
zero. Host admission adds the table, pinned row and 32,768-byte conservative
target-buffer reserve to the inherited 97 GiB.

## Table identity and restoration

Path: `/home/steve/own-xpu-runtime-results/packet137-token-input/draft-embedding.bf16`

SHA-256: `72260c77f4fec1174caead915453e0647e7b18d487255a114a8f96ae1e2709c9`

Bytes: **1,271,398,400**; file mode read-only. `evidence/table.json` records
the original weight pins, compiler commands and all-row checks. Generation
streams to disk and peaked at 287,220 KiB RSS. This model-derived file is
outside Git. If absent, restore it with the following CPU-only command;
the builder refuses to overwrite an existing complete or partial artifact.

```sh
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet137-token-input/table_build.py </dev/null
```

The copied RoPE bytes (4 MiB), generated fusion RoPE header (12.6 MB) and
composition identity JSON (2.0 MB) remain because the frozen source and
identity closure consume them. They are exact inherited bytes recoverable
from packet124c and its recorded source map. Build caches are ignored.

## CPU qualification and proposed device work

```sh
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet137-token-input/v5/qualify_cpu.py </dev/null
```

Compilers use the shared `ops/compile_turn.py` gate. CPU processes have a
4 GiB address-space cap; production imports never impose a cap. The gate
checks all 65,536 half-scale bit patterns for both quant blocks, signed PLE,
full-size startup, all six bank bindings, poisoned reset bytes, host/device
history rollback, miniature native CPU proposal/state parity, and 491 cancellation/redo
cases under both compilers. Original oracle authority is verified through
`oracle-binding.json` and `shared_oracle.py --require-complete`, separately
from source maps.

The legacy all-window checks cover 44 token-input/window constructions plus
the frozen real Python argument and queue paths. K0/K1a/K1b ran locally.
The unchanged K2 numerical fixture exceeded the 4 GiB cap; its failure is
retained and is not labeled a pass. Its exact frozen startup archive and unchanged binaries are hash-checked.
Its real argument path and retained measurement-validator replay remain required.
The queue rehearsal uses a local copy of the inherited probe, checks this
packet's actual build budget, and accounts for synthetic queue writes in
scratch. The older build-budget refusal is retained; its build and allowance
are unchanged. The real input, oracle, storage and queue checks still run.

After all CPU gates passed, the runner wrote three **proposed** files:
`proposed-p137-smoke-B.txt`, `proposed-p137-v5-B.txt`, and the unqueued
`proposed-p137-v5-A.txt`. Temporary queue copies exercise their real `--plan`
paths. Smoke is twelve 64-token requests with `both`, plus incident64.
The bracket is original/both/original/both/original in one load, twelve
128-token requests plus incident64 per view. It requires unchanged target
outputs, exact per-prompt draft proposal sequences and acceptance, full reset,
fixed allocations and no prompt reuse. This is a 128-token diagnostic scope,
not a promoted 512-token final gate or a fresh-load determinism claim.

Expected smoke duration: 240–360 seconds. Bracket: 720–1,200 seconds. The
4,800-second watchdog is at least four times either upper estimate. Bracket
launch waits for the exact smoke and coordinator admission. The two candidate
views must both beat every control by at least 0.5%, with control drift at most
3%, to qualify this screening comparison. No gain is claimed in preparation.

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md) records the outcome,
limitations and conditions for continuing through device checks.
