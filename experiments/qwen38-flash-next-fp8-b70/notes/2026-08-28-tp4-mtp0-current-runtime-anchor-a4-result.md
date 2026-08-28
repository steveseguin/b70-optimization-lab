# Qwen3.8 Flash-Next TP4 MTP0 current-runtime anchor attempt 4 result

Date: 2026-08-28

Attempt 4 passed its complete preregistered sequence. It adds two measured
current-runtime website cells—TP4 eager MTP0 at short context and exact active
4K—without replacing or lowering any retained result.

The exact identity was model revision `bcd9f01d`, vLLM `1372c62d`, XPU-kernel
source `ad25aa9f`, staged runtime build `2f829747`, TP4/EP4, eager graph-off,
MTP0, a 4,352-token maximum, a 201,326,592-byte cache, disabled prefix cache,
and the existing selective UVA PLE/input-embedding placement. The fresh
four-rank collective passed. TP0's weight loader reported 84.56 seconds; the
per-rank model-loading lines reported 92.410582–93.650635 seconds. The server
exposed 7,121 cache tokens.

The recovery canary returned exact `OK` with 17/2/19 usage, a normal stop, and
zero cached or created-cache tokens. Direct quality then passed 6/7 semantic
cases with only the known `code_execution=30` miss, repeated one output hash
16/16 times, and passed the exact cache-zero 4,096-token needle.

## Measured rows

- The established p146/o256/c1 after-first-text rows measured
  `5.315577824`, `5.223788770`, and `5.219404722 tok/s`; median
  **`5.223788770 tok/s`**. Each returned exact 146/256/402 usage and one output
  hash. Row one followed the harness's one conditioning request; rows two and
  three had no warmup. This older short harness does not retain per-row cache
  detail or finish reason, so neither is claimed.
- Two exact p4096/o128 rows measured **`4.720311370`** and
  **`4.795324835 tok/s`** under conventional 100-event/99-interval accounting;
  median **`4.757818102 tok/s`**. TTFT was `149.329680 s` and `145.606991 s`.
  Both returned exact 4096/128/4224 usage, zero cached tokens, length stops, 128
  token IDs, and one output-token hash. The hash also matches the retained
  legacy target-only authority.

The client and supervisor both exited zero. Controlled teardown left no
listener, owned process, scratch path, or B70-addressed event; all four cards
were discoverable at 42.875–42.883 MiB. This is a card-clean postflight, not a
clean-host storage qualification.

The tracked structured receipt is
[`20260828-tp4-mtp0-current-runtime-anchor-attempt4-result.json`](../data/20260828-tp4-mtp0-current-runtime-anchor-attempt4-result.json).
Its external summary is retained at
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4/current-anchor-summary.json`
with SHA-256
`c557f2a6bd2113ebfcb98bc655c7d83490b48f85091007181abd9352f54569a0`.
The 67-file run-plus-supervisor primary-evidence manifest is alongside it as
`qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4-primary-evidence.sha256`;
all 67 entries verify, and the manifest SHA-256 is
`2d1188a349843a3764f0f1f874aed42e7d72368bff8b515f8f55033ecc7e9b59`.
A byte-identical tracked copy is
[`20260828-tp4-mtp0-current-runtime-anchor-attempt4-primary-evidence.sha256`](../data/20260828-tp4-mtp0-current-runtime-anchor-attempt4-primary-evidence.sha256).

Attempt 3 remains a no-request harness negative. Its relative-path check failed
before the recovery canary, then controlled cleanup succeeded. Attempt 4
changed only that check and used fresh paths and a fresh port.

## Interpretation

These two cells are Grade-C `lab-screened` same-boot evidence. They do not
prove clean-host or fresh-server stability, production deployment, graph mode,
other tensor-parallel topologies, MTP1-4 transfer, or any unmeasured context.
No LocalMaxxing submission is authorized. All legacy-runtime measurements and
all faster MTP measurements remain intact.
