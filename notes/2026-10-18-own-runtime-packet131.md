# Packet131: preserve recurrent rollback state by rotating buffers

CPU preparation is complete and sealed. The candidate removes **29,601,792
of 48,627,432 capture bytes per cycle (60.87%)**, with **zero increase in owned
device allocation**. All eight full-state transcripts match byte for byte.
The new smoke and grid proposals are unlaunched. No device speed gain is claimed.

Work is on main, on steve-b70s. Initial `git pull --rebase` refused unrelated
dirty orchestration files; `git fetch` confirmed HEAD and origin/main at
`c7b59d9429e3c2b1c6c351f523203e36ec1327fa`. The new copy preserves symlinks.
All 809 pinned parent files and both original symlink targets remain intact.
No GPU, service, live queue, power setting or host memory setting was changed.

The measured question is capture on **every** speculative cycle, about
0.523 ms in packet128b. It differs from packet121's restore-on-miss question.
The original snapshot already submits one descriptor upload and one flat
copy kernel. Its 1,021 extents are not 1,021 device copy commands. The sampled
compute event does not separate bandwidth, descriptor searches and workgroup
overhead, and packet128b's budget remains diagnostic.

The candidate admits the dormant local packet62 `banks-batch` path against
packet124c bundle7. Committed A and previous spare B remain observable;
speculation writes private C. A hit commits by rotating bindings, while a miss
restores A/B by reversing the rotations. All six physical pairs have prepared
commands. Full-overwrite proofs cover 18 GDN recurrent matrices, 18 GDN
convolution histories and one PLE convolution history. QSA/KV rows, scratch
tails and other mutable outputs retain the original guarded flat capture.
No arithmetic, quantization, KV precision, target verifier, draft prefix or
controller scheduling changes.

The 24/24 production constructor census has 1,021 control extents and 984
candidate extents. The candidate copies 19,025,640 bytes. Its third bank costs
29,601,792 bytes, exactly offset by shrinking backup capacity from 373,633,560
to 344,031,768 bytes. Both choices allocate 28,144,182,388 bytes on rank0 and
31,425,985,242 on rank1. Remaining capacity inside the 30-GiB arena limit is
3.7887/0.7323 GiB. These are CPU allocation-ledger values, not driver residency.
Bank rotation drains the queue; the device comparison must measure that cost.

Completed gates:

- GNU host and Intel device-target builds, serialized through packet94.
- Production allocations, every capture extent and all six bank bindings,
  including QSA context changes.
- Eight full-state runs: 491 cases each, 43 position classes, forced hits,
  misses, partial cancellation, terminal fallback, a 98-step mixed sequence,
  and corruption negatives. All outputs, logical active/spare state and
  remaining live state have identical canonical hashes across both compilers,
  both choices and fresh repeats.
- Production recurrence: 72 raw bank/reference cases per run, twice under each
  compiler. Reset regression: original failure detected and 21 repaired cases
  pass twice under each compiler.
- Two miniature runs per choice match frozen packet124c target tokens,
  96 retained layer outputs and draft state/proposals.
- Both selections pass all eleven startup paths. The extended inherited
  Python argument gate, retained K2 replay, original K2/oracle negatives,
  real queue validators and actual pre-LATE oracle subprocess pass.
- Drain deadline and teardown-on-error tests pass. All six proposed windows
  reach both intercepted native argument boundaries. Actual smoke/grid launch
  guards preserve every inherited resource limit; finite-address-space
  negative controls refuse before a native launch.
- Two new screen seals and all source-bound readiness checks pass. Temporary
  queue plans and success/failure paths pass, including stop-without-retry.

GNU and Intel compile the changed Engine/snapshot fixture; unchanged arithmetic
dependencies remain pinned inherited objects. Separately compiled production
recurrence kernels differ only in the explicit NaN reference case: their
original kernels propagate different NaN payloads. Candidate/reference bytes
and repeats match raw under each compiler. Diagnostic normalization is applied
only to copied output after strict equality, never to runtime state or as an
acceptance tolerance. All eight full-Engine transcripts still match raw.

Retained harness failures include an interrupted sequential CPU attempt,
Intel PIE/library-path issues and K2 refusing an auxiliary 1.5-GiB cap.
The final state workers each use 1.5 GiB, four at once; K2 runs separately under
the allowed 8-GiB CPU cap. The inherited queue replay initially counted the
frozen parent's live chain against its retained-storage budget; its original
refusal is retained. The CPU replay instead accounts for this packet's actual
build and temporary queue. The frozen parent and device storage policy are
unchanged.

The allocation and prepared-pair layout is not switchable in the existing v5
wrapper. New lane-B proposals therefore specify the **12 × 64 exact smoke**
(expected 360 s, watchdog 1,800 s), then **C/X/C/X/C fresh loads**
(expected 480 s each, watchdog 3,600 s). The grid requires the exact sealed
smoke and passing, drained predecessors. Both candidates must match every
oracle token and acceptance count and beat the strongest control by at least
1%, with control drift no more than 3%. These 128-token screens are diagnostic,
not strict512 qualification or submission evidence.

[Packet and reproduction commands](../experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/README.md),
[complete census](../experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/CENSUS.md),
[exactness argument](../experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/EXACTNESS.md),
[readiness](../experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/evidence/ready131.json),
[closeout](../experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/CPU-PREPARATION-CLOSEOUT.md),
[smoke proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p131-smoke-B.txt),
[grid proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p131-grid-B.txt).
