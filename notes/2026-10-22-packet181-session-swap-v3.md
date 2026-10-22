# 2026-10-22: packet181 session checkpoint v3 prepared on CPU (qualified-one-card label, packet180 read compatibility, prompt-path record)

## What and why

packet180 passed its device window (row a 31.78 tok/s, identical to packet179; row b 36/36:
append == one-shot reference, restore-then-save chain == reference, repeat identical). Two follow-ups
were queued for the next relink: change the manifest label from `experimental`, and "batch the
appended tokens through the chunked prefill path" because the append ran at ~22.7 tok/s against
~29 tok/s cold. [packet181](../experiments/own-xpu-runtime/stage2/packet181-session-swap-v3/README.md)
does the first and shows why the second does not exist to be done. Entry TU only; all 41 kernel
objects relinked byte-identical from packet165.

- Binary `0bf0a17ac215a7dc552de9337a2d549172552a8641e0ec7334e83af5c67829fd` (three builds from the
  same source, identical). Delta vs packet180: main.cpp +8/−1, checkpoint.hpp +85/−15 (989 lines).
- Manifests: `label: "qualified-one-card"`, `contract: "v1.2+p181"`, `qualified_by` = packet179
  same-generation resume and packet180 append/restore-then-save, both 2026-10-22, scope "one card
  (tp1-full512 profile) only; TP2 checkpoints not implemented; no ctxkeeper adapter yet".
- The reader still accepts packet180's `v1.2+p180` `experimental` manifests; label and contract
  must pair. Restore is decided by the identity/semantic checks, never by the label.
- `result.json` records how each request's prompt positions were stepped (`checkpoint.prefill`,
  `append_prefill_tokens`, `append_prefill_path`). CLI unchanged.

## Correction: there is no chunked prefill; the append is not slower per position

packet180's note says the append ran "through the incremental path, below the chunked cold-prefill
rate". The engine has one prompt mechanism: a fresh request steps its prompt one position at a time
(`step(token, 0)`, final norm/logits/argmax skipped), and packet180's append calls the same lambda
for positions N.. — not the decode path. `prefill512` is a 512-token suite prompt, not a chunk
size. Batched prompt reading was designed in packet165's BATCHED-PREFILL.md and its first device
step (packet166, fully paired causal M=2 layer) was closed: layer M2/M1 > 1.5, expert gate/up
2.81×. It would need new M>1 kernels and reopen a closed lever, so packet181 does not build it.

The gap is the empty expert cache of a fresh process (every leg of row b is one). From packet180's
real per-position rows: the cold reference's first 64 prompt steps average 52.1 ms, the append's
first 64 average 53.9 ms; both fall to ~29–34 ms once warm; a warm process (row a `prefill512`)
runs 27–33 ms from its first position. At matched warmth the append's 126 prompt steps took
5549 ms vs the reference's first 126 at 5684 ms (×0.976). The reference ran the same positions
342–467 in 3839 ms because its cache was warm by then. Against the overall cold rate the append is
×1.29 per token; that bound (×1.25) is reported in row b, never gated. In a long-running server
the cache is warm and an append runs at the warm rate. A real lever for a fresh-process append
would be a cache-content prefetch at restore — a cache-policy change, not batching; not built.

Byte identity: the append is identical by construction and proven on device (packet180). A batched
prefill would also be identical only if every M>1 operator kept each row's reduction order and
BF16 rounding points and the GDN recurrence stayed sequential (packet166's device micro met this:
`finite_bytes_equal: true`); the restored state equals the one-shot state at N, so chunk
boundaries after a restore would not change bytes.

## CPU results (no GPU; the device binary ran only `--help`)

- Host-only C++ sessions (`checkpoint-probe.json`, 91 runs): every packet180 case (26
  refusal/boundary cases, 14 delete cases incl. concurrent delete-vs-restore, round trip, append,
  chain, repeat, fresh-save state identity) on v1.2+p181 manifests; append spans of 1, 28 and 25
  tokens incl. a restore at N=13 (not a multiple of 4) and spans crossing position 32, each equal
  to the one-shot reference with state byte-identical to a fresh save; an `experimental`
  checkpoint is inspected, resumed, appended, restore-then-saved (child labelled
  `qualified-one-card`, identical state) and deleted, and is refused only by the binary check;
  8 pairing refusals before model load.
- Production shape: packet179's real checkpoint converted to both contracts, and **packet180's
  real device S1/S2 verbatim**, pass this reader (metadata and full inspect, real control blobs;
  the device-rendered `fields.tsv` equals this reader's rendering); S1 passes the pre-load restore
  precheck with the real 469-token NEW.
- packet180's analyzers on packet180's real receipts reproduce its device receipt exactly (36
  gates) and 31.78 tok/s; the v3 analyzer passes them (missing path → `incremental`) and fails
  exactly the label and record gates when told to expect v1.2+p181 (`p180-receipt-replay.json`).
- Lifecycle worker arm at production shape (`lifecycle-test.json`): 20 cases, 43 gates on pass.

## Device rows (proposal only, `ops/lane-queue/proposed-p181-one-card-A.txt`; not queued)

| Row | Estimate | Gate |
| --- | --- | --- |
| `packet181-one-card-full512-A-a` | ~8.5 min (packet180: 500 s) | full512; every output equals packet179 row a (== packet180 row a) |
| `packet181-one-card-lifecycle-A-b` | ~20 min (packet180: 1167 s) | packet180's row b structure; 43 gates: its 36 with the label gates for v1.2+p181, append path == reference path == `incremental`, prefill records; append cost reported, not gated |

Admission is packet180's (lane A whole-host, fault review, 98.99 GB host memory, 25 GB floors,
7200 s watchdog, 400 MB planned writes).

## Packaging state

Seal (688 files) → proposal → flags → live planner + rehearsal on a private copy →
`final_checks.py` → `final_checks.py --ready`. Pin guard on the full closure after READY: 755 pins
= 747 in-packet + 7 packet49 oracle-binding targets + 1 own proposal; **0 cross-packet mutable
pins**, both rows (re-checked independently). Live planner after READY (private copy):

```
{"name": "packet181-one-card-full512-A-a", "plan": "passed", "storage_admission": {"planned_write_bytes": 400000000, "root_free_bytes": 36934078464, "required_free_bytes": 25400000000, "passed": true}, "host_required_available_bytes": 98990252032}
{"name": "packet181-one-card-lifecycle-A-b", "plan": "passed", "storage_admission": {"planned_write_bytes": 400000000, "root_free_bytes": 36934078464, "required_free_bytes": 25400000000, "passed": true}, "host_required_available_bytes": 98990252032}
```

Commit note: 21 sealed `.bin` copies (14 under `one-card/lineage/packet180-receipts/`, 7 under
`lineage/packet179-receipts/`) need `git add -f` (repository `*.bin` ignore rule). Packet on disk:
154 MB (build outputs included). Nothing committed or queued by this work.

## Not claimed

No device result for this binary. One card only; TP2 checkpoints not implemented; no ctxkeeper
adapter yet; no chunked prefill; the append timing is an observation of fresh processes, not a
performance claim.

## Device window result (2026-10-22 07:59–08:28 UTC rows, runner unit lanequeue-A36, driver unit window-p181-driver)

Pre-flight: live `lanequeue.py plan --lane A` passed both rows; endpoints stopped at 07:59:06Z (idle since
the 07:23Z restore validation; MemAvailable 120.6 GB ≥ 100.1 GB); PAUSE-A archived and re-armed; endpoints
restored afterwards as `*-20261022-restore6`. No GPU fault lines in the kernel journal during the window.

| row | outcome | duration | result |
|---|---|---|---|
| packet181-one-card-full512-A-a | DONE | 497 s | passed, oracle-128 exact, class-balanced 31.83 tok/s; all 12 outputs identical to packet179 row a (binary `0bf0a17a…`) |
| packet181-one-card-lifecycle-A-b | DONE | 1159 s | passed, 43/43 gates: same structure as packet180 row b (S1 save K=256; restore + 126-token appended turn + 128 == one-shot reference [0:128]; restore-then-save S2; resume S2 + 64 == reference [128:192]; repeat append identical; S2b blobs == S2 blobs); every device-written manifest carries `label: "qualified-one-card"`, `contract: "v1.2+p181"` and the `qualified_by` record (packet179 same-generation resume, packet180 append + restore-then-save, scope one card only / TP2 not implemented / no ctxkeeper adapter); append path recorded as `incremental` for both the append and the reference (the engine's only prefill mechanism); restore 0.44–0.47 s; append prefill 5.58–5.59 s vs 16.0 s cold prefill of 469 tokens (2.65×); save 1.07–1.08 s |

Checkpoint blobs stay outside Git; manifest sha256s are in `summary.json`. With this row the saved-state
label is no longer the string `experimental` for one-card checkpoints written by this engine; packet180's
`experimental` files are still accepted on restore (host probe, not a device row).
