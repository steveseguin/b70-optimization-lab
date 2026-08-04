# Retraction: there was no regression. It was cold-start measurement error

Date: 2026-08-04 America/Toronto

Status: **retraction. Supersedes the throughput claims in
[`2026-08-04-drafter-window-arm-and-the-allocator-confound.md`](2026-08-04-drafter-window-arm-and-the-allocator-confound.md),
[`2026-08-04-xpu-allocator-degraded-within-boot.md`](2026-08-04-xpu-allocator-degraded-within-boot.md),
and the premise of
[`2026-08-04-rescoped-targets-and-post-reboot-runbook.md`](2026-08-04-rescoped-targets-and-post-reboot-runbook.md).**

## The claim that was wrong

A long sequence of runs on 2026-08-04 measured ~7.5 tok/s decode and ~3,150
tok/s prefill at 32,640 tokens, against a recorded baseline of 39.589 / 7,345.
This was reported as a 5x degradation, variously attributed to
`PYTORCH_ALLOC_CONF=expandable_segments:True`, to driver reloads, and to host
state. A reboot was requested and performed on that basis.

**All of that was wrong.** The machine was healthy throughout.

## What actually happened

Every one of those runs used `LAGUNA_LONG_CASE_IDS` to serve a **single case**,
so the measured request was always the **first** request after server start. The
2026-08-02 baseline ran the full suite, where `laguna-lc-32640-early` was the
**seventh** request and the server was warm.

The 2026-08-02 run's own data shows this plainly. Its *first* row is a 1K case:

| case | 2026-08-02 | 2026-08-04 single-case |
| :--- | ---: | ---: |
| `laguna-lc-01024-early` (1st request in its run) | 8.897 | 8.833 |
| `sentinel-after-...` (late, warm) | 165.716 | 163.566 |

Identical. The 1K figure of 8.9 was never a slow machine; it is what any first
request measures.

## Confirmation

Re-running the 08-02 warm-up order on 2026-08-04, **post-reboot, with no
allocator flag**:

| case | 2026-08-04 warm | 2026-08-02 | delta |
| :--- | ---: | ---: | ---: |
| `laguna-lc-08192-early` (1st request) | 7.833 | -- | cold-start penalty |
| `laguna-lc-08192-middle` | 51.721 | 51.225 | +1.0% |
| `laguna-lc-16384-middle` | 40.115 | 40.391 | -0.7% |
| `laguna-lc-24576-middle` | 39.853 | 39.841 | +0.0% |
| **`laguna-lc-32640-early`** | **39.848** | **39.654** | **+0.5%** |
| prefill at 32,640 | **7,340.6** | 7,368.9 | -0.4% |
| sentinel (256 tok) | 163.566 | 165.716 | -1.3% |

Every case reproduces within ~1%.

## The first-request cost, quantified

Fitting prefill at two prompt lengths from cold:

```
 1,024 tokens ->  5.8 s
32,640 tokens -> 10.35 s
```

gives a **fixed first-request cost of ~5.5 s** plus a marginal rate of
**~6,947 tok/s**, essentially the warm 7,345. The cost is fixed per server, not
per token, which is why it looks catastrophic at 1K (29x) and mild at 32K
(2.3x).

This is a real property worth recording: the campaign's headline numbers are
**warm-server** measurements, and a production deployment pays ~5.5 s on its
first request. Nothing in the campaign's notes had recorded that.

## What survives, and what does not

**Retracted:**

- `expandable_segments` costing 2-5x. Cold single-case runs with and without it
  measure 7.632 and 7.484 -- the flag is roughly neutral, not a 5x penalty.
- The torch profiler costing 6x. Against the correct cold comparison (7.5), the
  profiled run at 5.469 costs about **1.4x**, not 6x. The profiler is far less
  distorting than claimed, though a trace taken on a first request still
  captures warmup behaviour and should be redone warm.
- Any claim that the host degraded within a boot, or that driver reloads harmed
  it.

**Still true:**

- The init-time XPU OOM was real: before the reboot, init refused 96 MiB with
  ~13 GiB free unless `expandable_segments` was set; after the reboot it
  initialises without it. The reboot fixed a genuine allocator-fragmentation
  problem, even though the throughput story attached to it was wrong.
- The drafter-window arm is unaffected: 7.648 (widened) vs 7.632 (stock) were
  both cold first requests, so the comparison was like-for-like and the
  conclusion stands -- widening the draft window does not help.
- The standalone collective floor (45.9 us, `provider: tcp`, 6.84 GB/s peak,
  nine config arms within 3%) used no server at all and is unaffected.
- Acceptance collapsing with context (73.3% / 53.1% / 7.4%) is unaffected; it is
  computed from counters that match across warm and cold runs.

## The lesson

The hardware evidence said "healthy" from the beginning -- 153 TFLOP/s per GPU,
587 GB/s device bandwidth, 28.7 GB/s PCIe, startup *faster* than 08-02 -- and it
was repeatedly explained away instead of being taken as a signal that the
**comparison**, not the machine, was at fault. When every subsystem benchmarks
healthy and the workload does not, suspect the measurement.

Concretely: **never compare a single-case run against a full-suite run.** Either
reproduce the baseline's case order, or explicitly report first-request numbers
as such.

## Boundaries

No quantisation change, no caching or speculation setting used to inflate any
number; prefix caching remained off in every run cited. The protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
