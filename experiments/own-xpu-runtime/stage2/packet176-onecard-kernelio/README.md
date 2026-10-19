# Packet176: one-card copy-engine-free foreground token I/O (d2)

CPU preparation only. No GPU, service, setting or live queue was touched.
Parent: a private `git archive` copy of packet58as at committed HEAD (native
sources identical to `dabfc958b`); scaffold tooling ported from packet174. See
`lineage/packet176-copy.json`.

## Why

On the spin line (28.80 ms/token, 34.573 tok/s) a token's foreground transfer
time is slow only on tokens whose position-start boundary submitted
maintenance fills, linear in those fill bytes: 0.035 ms/MB, intercept ~0.1 ms,
on every spin view of packet58as, packet171b and packet174
(`evidence/analyzer-real-parent.json`). The packet174 fill kick was neutral
(-0.02%), and packet171b's compute-queue `memcpy` was neutral: a memcpy on any
queue can still be carried by a copy engine.

Two facts from the source shape this packet:

- `transfer_wall_ms`, the field the law was fitted on, is **all** foreground
  transfer time of the token: the head `put(token)` and lookup-row uploads
  (right after the fill submission) plus the tail error/next_token readback.
  The "readback" attribution was never split.
- `SyclDevice` creates the foreground copy list (`native_copy_`) and the
  maintenance fill list (`maintenance_native_`) from the same
  `ze_command_queue_desc_t`: the first copy-only ordinal, index 0. They feed the
  same copy engine.

## Change (B arm, `--foreground-io kernel`)

- **Tail.** `p176::TailStore`, one compute-queue kernel enqueued right after
  the last launch (argmax), reads the device `error` and `next_token` buffers
  and stores them, with a per-token stamp, into `slab[0]` bytes 0-15. That is
  the same pinned (`sycl::malloc_host`) bytes the parent's copies fill. The
  same kernel stores the 48 route rows into the pinned `route_log`. The owner's
  existing compute drain (spin policy, 600 s deadline, `check_error`,
  `wait_and_throw`) is the only wait. The host then checks the stamp and reads
  host memory. The sticky-error `require(!status)` is unchanged.
- **Head.** While the token head is open, `put()` stages the token id and
  lookup rows in `slab[0]` + 4096. One `p176::HeadLoad` compute kernel then
  loads them into the unchanged device buffers, in queue order before the first
  launch. There is no host wait. A drain before staging keeps the parent's
  slab-reuse rule.
- **Why it cannot queue behind fills.** Both are kernels (`parallel_for`)
  submitted through `Device::compute` onto the in-order compute queue.
  Bindings are device allocations only; the pinned pointers are immutable
  kernel arguments, as in `p58v::Publish`. Neither op issues a memory-copy
  command, so runtime copy offload cannot route it to a copy engine. Neither
  depends on a copy-list event: `SyclDevice::dependencies` drops same-queue
  events. `single_device.cpp` (the backend: fill, copy, wait, maintenance list)
  is byte-identical to the parent.
- **Unchanged.** Fills (second BCS list) and which experts are planned, filled,
  evicted and published, and when. Also unchanged: every launch, arithmetic,
  selection, spin policy, resident lookups and captures.
- **Readout fields (host only, both arms).** `timings.jsonl` gains
  `head_transfer_ms`, `tail_transfer_ms`, `route_log_ms` and `foreground_io`.
- `apply_kernelio_delta.py` is the exact delta; `native-delta.patch` is its
  diff.

## Interface

- Process-wide `--foreground-io copy|kernel`, default `copy` (packet58as),
  listed in `--help`. It is accepted with every engine chain window argv (KD,
  W2m, WS, WS128x, WS128). K1a/K1b run the unchanged fixture binary.
- It is refused with a draft capture, a rank or more than one card.
- The bracket sets the same `p176::kernel_io` switch per view at the drained
  view boundary (A = `spin`, B = `spin-kio`). `--foreground-io` together with
  a bracket table is refused.

## Driver settings (documented, not changed)

- The closed native environment is `HOME LANG LC_ALL LC_CTYPE OMP_NUM_THREADS
  PATH TMPDIR LD_LIBRARY_PATH` plus the one-card mask: `NEOReadDebugKeys=1`,
  `FilterBdfPath`, `ZE_ENABLE_PCI_ID_DEVICE_ORDER=1`, `ZE_AFFINITY_MASK=0` and
  `ONEAPI_DEVICE_SELECTOR=level_zero:0` (`chain_devices.py`, `window.py`).
- Nothing sets `UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD`, `SYCL_PI_LEVEL_ZERO_*`
  copy-engine keys or NEO copy/blitter keys. Copy offload is therefore the UR
  Level Zero adapter's default for in-order queues.
- Packet176 changes no setting.

## Device contract (proposal only; not queued)

- Lane A, whole host, one load: K1a/K1b, then v5 A0/B0/A1/B1/A2 with 12 x
  128-token requests per view. There is no separate smoke.
- **Gate:** both B views >= +0.5% over every warm A, warm drift <= 3%, and
  60/60 exact vs `iq3-p49-split32-v1`.
- The mechanism readout (`summary.json` -> `mechanism_readout`) is kept on
  every outcome. It reports:
  - the engine per arm and the copy-engine commands per decode token;
  - the slow-transfer fraction;
  - the head/tail/route-log split and which one carries the fill slope in A;
  - transfer, wall and wait ms per same-token fill MB;
  - the next-token transfer slope.
- Proposal: `../../ops/lane-queue/proposed-p176-v5-A.txt` (job
  `packet176-v5-A`).

## Pricing (per token, base 28.80 ms)

| Item | ms/token | Label |
| --- | ---: | --- |
| Transfer excess removed if no copy engine is waited on | up to 1.07 (0.035 ms/MB x 30.63 MB) | measured law |
| Fixed foreground copy round trips removed (transfer intercept, every token) | ~0.10 | measured intercept, assumed fully removed |
| Fill now overlaps compute (H2D shares PCIe with zero-copy misses) | 0 to -0.9 | assumed |
| Net | **+0.1 to +1.17 (+0.4% to +4.2%)**; central +0.5 to +0.8 | |

- The wall slope is 0.0666 ms per same-token fill MB, about twice the
  transfer slope. Kernel I/O does not target the other ~0.032 ms/MB, which is
  outside the transfer window (fill submission host time or compute
  contention, unsplit). The B readout's wall slope shows whether it moves.
- Packet174's fill kick was neutral, so it is not composed here. Had it won,
  the fills would already overlap compute and d2 would keep only the ~0.1 ms
  intercept.
