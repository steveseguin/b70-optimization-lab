# Packet 14 — two-card tensor-parallel decode

CPU preparation for the **separate Unsloth Flash-Next UD-IQ3_XXS quantized
compressed version**, October 11, 2026. No GPU binary ran. This packet extends
our [packet 13 CLI](../packet13-integrate/README.md), [packet 12 peer path](../packet12-peer/README.md#first-measurement--cards-2-and-3-2026-10-11-061x-utc-boot-13858eef)
and [two-card design](../TWO-CARD-TP.md). Both owners work in every layer;
this is not the earlier sequential 24/24 layer placement.

## Exact split rules

Arithmetic identity: **`iq3-p14-full-row-p13-tree-slot-order-v1`** in
[reference.hpp](reference.hpp). It preserves packet 13's original full-row
K reduction, intermediate BF16 stores and serial expert-slot FP32 sum.
Dense dispatch uses the **original full shape**, never the half-row shape.
The expanded representation uses packet 10's repaired exact decoder; the
SG32/split4 choice remains the packet-13 choice, including SG32 for the head.
All 25 production shape/grid keys have independent scalar-tree comparisons
and packed-versus-expanded checks. No weight, KV or state precision changed.

| Data/work | Card A | Card B |
| --- | --- | --- |
| Dense output rows (including router and head) | `[0, floor(rows/2))` | Remaining complete rows |
| One-row control projections, scalar/norm weights | Replicated | Replicated |
| Experts | IDs 0–255, full gate/up/down | IDs 256–511, full gate/up/down |
| GDN recurrence | Value heads 0–23 | Value heads 24–47 |
| Convolution history | First half of channels | Second half of channels |
| QSA attention/KV | Q heads 0–11, KV head 0 | Q heads 12–23, KV head 1 |
| HC streams, rounded activations, routing, index/pool controls | Replicated | Replicated |
| Embedding and PLE lookup tables | Host-backed requested rows | Same exact requested rows |

GDN keeps the original global head-to-key mapping (`h % 16` for real packed
heads), so Q/K inputs remain available to both ranks. QKV row halves are
**gathered before convolution/recurrence**; they are not mistaken for head
halves. QSA stores each token's local KV head contiguously and retains global
Q-head indexing. Small synthetic odd GDN head counts split 1+2; the original
one-KV-head mini-model replicates that head. A second fixture explicitly tests
two KV heads, packed GDN head mapping and four/eight-position pool boundaries.

Top-10 routing runs identically on both cards after gathering all logits.
Exact raw IDs/probabilities are compared before any expert-bank read. Each
rank streams only its selected expert bytes, retains original route-slot
indices, and uses one fused local gate/up launch plus one local down launch.
Zero local hits submit no expert kernel; all ten hits on one card are valid.
Compact results are copied once per nonempty rank/projection and scattered
into their original slots. Both ranks run the unchanged ordered mixture.

**Two local expert partial sums followed by FP32 A+B are deliberately rejected.**
They generally differ from the unchanged ten-slot sum; the retained CPU
cancellation test demonstrates this. Mirroring that different tree in a new
oracle would not meet `single-card == two-card == CPU`. Dense halves therefore
use byte gathers, and experts use original-slot gathers. There are several
dependency exchanges per layer, not one end-of-layer exchange. This implements
the design's exact candidate rather than silently changing arithmetic.

## Owners, execution and memory

[backend.hpp](backend.hpp) adapts packet 12's bidirectional peer memcpy to two
Arena/Device owners and two queues in one Level Zero context. Range lookup
supports offset copies; each rank retains its own event ledger. The new
bounded synchronous [peer bridge](peer_owner.cpp) validates both live Arena
rows, waits for drained producers, tracks the copy on its destination owner,
and returns only after completion. It never imports an allocation ID into the
other Arena. A copy timeout/failure poisons both owners, retaining endpoints.
The generated owner header adds only this method; shared owner sources and
packet 13's source/build are unchanged.

Both dense/expert shards are prepared before either compute submission, and
both queues receive their projection before either completion wait. State and
other scalar bring-up operators remain eagerly drained. There are no peer
atomics, polling kernels, floating atomics, server, automatic fallback or retry.
Shutdown releases each rank's allocations/events and retains the shared native
queues/context until **both** owners close. Census, teardown and raw timing
records are retained per run.

`--cards 2 --card 2 --memory tp2-streaming` is a bounded correctness mode:
one layer's dense/control weights plus selected owned experts, 4 MiB reads and
one 4 MiB pinned slab per card. Dense expansion happens in bounded row chunks;
experts remain packed. Every Arena enforces 30 GiB, but this is not a resident
speed configuration or measured fit claim. Actual allocations appear in
`census.json`; `plan.json` declares source ownership, expansion and compact
request buffers. Failure poisons the transaction; no failed request is reused.

## Exchange bytes and timing prediction

The [complete 1,224-tensor census](placement.json) is generated from checked
repository metadata, without model payload reads. Counts below are delivered
peer payload bytes **across both directions, per input token**:

| Layer | Peer bytes | Maximum peer copies |
| --- | ---: | ---: |
| Ordinary/upgraded GDN | **198,608** | 40 |
| GDN with layer-1 PLE | **244,688** | 46 |
| QSA | **173,072** | 40 |
| All 48 layers | **9,272,832** | 1,926 |

Expert gate/up/down gathers contribute 76,800 bytes per layer (down alone
51,200); dense and state activation gathers supply the rest. The final head
and mixer are outside this table. Counts exclude local scatters, staging,
route/hidden verification readbacks, and driver-internal traffic. Rank hit
imbalance changes copy counts, not the sum of selected-slot payload bytes.

Packet 12 measured 18.3/18.6 µs for a 10 KiB peer copy and 52 µs for its ordered
round trip. Those are **transport diagnostics**, not this layer's timings.
A sensitivity scenario borrows packet 10's expanded GEMV-only aggregates;
these are not measurements of this packet's mixed dispatch. An explicitly
assumed 80%-parallel compute model gives `0.78 × .6 = .468 ms`
GDN and `0.77 × .6 = .462 ms` QSA. Budgeting 40 copies at the assumed average
18.45 µs gives **1.206 ms GDN / 1.200 ms QSA**, excluding nonlinear work, local
scatters, streaming, verification and launch/arrival differences. This is a
conditional prediction, not a measured speed or a 1.5× claim. The optimistic
model with only two 52 µs phases gives .572/.566 ms but omits this implementation's
extra gathers and must not be used as its performance forecast.

Every run emits `rank_layer` rows (per-card GEMV and non-GEMV device ms),
`exchange_layer` rows (actual peer bytes and host wall ms), full layer/token
wall time and staging time in `timings.jsonl`. Native clocks are never
subtracted across cards. CPU device times are null. Comparing synchronized
layer wall time with a matched one-card run tests 1.5×; summing local kernel
times or borrowing packet 10's GEMV-only diagnostic cannot establish it.

## Tests and reproduction

[Build receipt](build-receipt.json), [CPU results](cpu-tests.json):

- 18 complete integration cases: 9 original mini-model cases, with independent
  NumPy comparison, and 9 two-KV-head cases against a separately built packet-13
  control whose only fixture changes are geometry and packed-head indexing.
  Each checks all 113 buffers; 71,208 values compared in total.
- Fresh-process TP repeat; 744 ownership/exchange/mixture checks, including 512
  expert IDs, 60 changed-payload bidirectional rounds, offset/bounds checks,
  cancellation, all-A/all-B/alternating/duplicate/boundary routes and teardown.
- 150 production-shape arithmetic checks; 4 owner/event retirement cases.
- 14 CPU window-receipt tests; actual CLI coverage of all 1,224 real tensor
  descriptors. Host executables have no accelerator-library dependency.
- Host and SYCL compilation/linking. **Native execution, real-model CPU/SYCL
  equality, fresh native repeats and performance qualification remain pending.**

```bash
P=experiments/own-xpu-runtime/stage2/packet14-tp2
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 \
  /home/steve/.venvs/vllm-xpu/bin/python -B "$P/build.py"
```

The builder uses two jobs, executes only host binaries and removes its ignored
`build/` by default. `--keep-build` prepares the coordinator's executable;
existing device windows/fault evidence prevent cleanup. [WINDOW.md](WINDOW.md)
gates layer 0 on packet 13's saved one-card bytes, and first-token execution
on that passing layer gate. No model or tokenizer download is involved.
[Closeout](CLOSEOUT.md), [negative index](DO-NOT-REPEAT.md).
