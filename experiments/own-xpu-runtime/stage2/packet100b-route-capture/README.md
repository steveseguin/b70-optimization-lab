# Packet100b: real target expert routes

CPU preparation is complete. **No GPU ran. Real routes, device output equality,
micro timings and candidate qualification remain pending.** This packet removes
the need to recover packet77/86's missing raw bytes by preparing a new bounded
capture. Nothing here is model speed evidence.

The capture uses packet97's snapshotted record-line selection, with
`head=production`, native MTP, 24 target layers per rank, and full BF16 state.
The GNU and Intel builds replace only the entry translation unit. All kernel
objects are unchanged and hash-bound. Four generated COW files add route copies,
an explicit request-boundary flush, reset bookkeeping, and omission of large
full-state dumps. Only the new diagnostic allocation is excluded from speculative
backup; the original model-state snapshot remains unchanged.

## Prepared jobs

Use the new proposed jobs in this order through the existing lane coordinator:

1. [Capture B](../../ops/lane-queue/proposed-p100b-capture-B.txt): one TP2 load,
   incident-retrospective and code-review, 64 output tokens each, oracle equality
   for every output token, then graceful drain and release.
2. [Micro B](../../ops/lane-queue/proposed-p100b-micro-B.txt): packet100's unchanged
   micro binary, full 2560 × 640 DOWN, 512 experts, ten selected slots, 40
   alternating pairs per candidate and route, equal 512 MiB device scrub.
3. The existing proposed packet100
   [interleave B](../../ops/lane-queue/proposed-p100-down-interleave-B-grid.txt),
   [tile16 B](../../ops/lane-queue/proposed-p100-down-tile16-B-grid.txt),
   [interleave A](../../ops/lane-queue/proposed-p100-down-interleave-A-confirm.txt),
   and [tile16 A](../../ops/lane-queue/proposed-p100-down-tile16-A-confirm.txt)
   now enter through [run_grid.py](run_grid.py). That adapter verifies the new
   qualification and runs the frozen packet100 driver. Its candidate seals,
   13-request exactness checks, acceptance checks, fresh brackets, and B winner
   requirement before A are unchanged. No parent reseal is needed.

All six real queue plans passed on temporary copies. **No live queue was edited
or job enqueued.** An already copied/queued old command is unchanged; the
coordinator must use these updated proposed files. Records remain on A.

The capture reuses the v4 lane reservation, fault review, device masks, process
supervisor and shared worker teardown/drain implementation. Host memory admission
(97 GiB) occurs before the lease and is rechecked before launch. Both jobs require
the coordinator's existing authorization/review interface, prohibit retries,
and have a 600-second watchdog. Build or plan never opens a device. The current
record chain is not disturbed.

## Capture format and qualification

Each request writes `rank{0,1}/routes.bin` and `routes.json` under
`evidence/capture-B/run/<prompt>/`. Each binary is 184,320 bytes:
64 target output steps × 24 local layers × ten 12-byte routes. Each route is
three little-endian uint32 values: expert ID, row begin (zero), row count (2560).
The JSON binds its SHA256, rank, fixture index, absolute position and input token.
Step 1 is the target pass over the last prompt token that produces output token
1; steps 2–64 consume the preceding generated token. All 48 layers are covered.
Routing weights are not DOWN inputs; they belong to the subsequent ordered
mixture and are not captured.

Copies stay on the device inside HALF. There are no added host reads or waits
in the token/layer loop. A slot is marked valid only when the normal controller
accepts that target half. Rejected speculative work cannot qualify; confirmed
redo overwrites the same slot. Command 13 reads the complete buffer once, after
the request has returned and output tokens match the unchanged CPU oracle.
Graph execution is not added; normal prepared kernel commands remain intact.

[capture_inputs.py](capture_inputs.py) verifies both requests, all 6,144 route
vectors, model/input identity, startup/window receipts, device isolation, and
drain/release. It writes `evidence/route-inputs.json` and `evidence/routes.bin`.
All raw routes remain retained. The micro takes **predeclared fixtures 1, 16, 32,
64**, every layer, both ranks and both prompts: 384 vectors, with no route
deduplication or selection based on IDs/speed. This bounds the operator run;
the capture is a diagnostic sample, not a representative model benchmark.

The original [packet100 analyzer](../packet100-down-locality/micro_gate.py) is
used unchanged: a candidate must use at most 85% of production kernel time
overall, in **every route stratum and both order halves**, with exact
FP32/BF16/status bytes. Synthetic weight/activation values in that micro remain
explicitly diagnostic. Qualification is recomputed from raw samples and bound
to the capture manifest, route bytes, compiled binary, original kernel/analyzer
sources, new seal, window and drain receipts. Missing or changed evidence fails
closed. The old missing-route gate is not weakened or rewritten.

## CPU checks and rebuilding

- GNU and Intel each pass two runs of the actual capture header: 368,640 copied
  bytes, 64 steps × 24 layers × two ranks, unchanged source bytes, partial/rejected
  speculation, redo, duplicate refusals and no host read in the loop.
- Real full-size startup with payload/backend mocks passes both ranks, 1,536
  capture sites per rank and the unchanged 30 GiB arena / 1.5 GB reserve gates.
- 23 Python checks cover corrupt/truncated/wrong-rank/wrong-step routes,
  unsupported shape/IDs, missing evidence, the original 15% and ordering gates,
  and memory refusal before lease acquisition.
- Six temporary queue plans pass. No device result is inferred from these checks.

Run these entry points in order with
`nice -n 19 taskset -c 8-15,24-31 python3 -B <script> </dev/null`:
`build_engine.py`, `full_shape.py`, `cpu_gate.py`, `prepare_micro.py`, `seal.py`,
`queue_plan.py`, `final_check.py`. Compilation always takes packet94's shared
`compile_turn.py` lock. `prepare_micro.py` verifies and reuses the exact parent
binary; it does not compile a different kernel.

Snapshots of packet97's selection, ledger and compiler commands are owned here.
The new seal pins implementation headers/objects, never the parent's mutable
orchestration receipts or decisions. Parent source trees, seals and live queues
are unchanged. This is a local lab diagnostic, not a portable published recipe.

[Final verification](evidence/final-verification.json),
[CPU copy tests](evidence/capture-cpu.json), [startup](evidence/full-shape.json),
[queue plans](evidence/queue-plans.json), [retention](RETENTION.md),
[CPU closeout](CPU-PREPARATION-CLOSEOUT.md),
[task note](../../../../notes/2026-10-18-own-runtime-packet100b.md).
