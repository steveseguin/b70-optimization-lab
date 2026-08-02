# Laguna long-context scheduler-budget alignment

Date registered: 2026-08-02 America/Toronto

Status at registration: host-only harness support is implemented; no service,
device probe, recovery action, or candidate run has started.

## Premise

The q12 long-context launcher requests `max_num_batched_tokens=8192`, but vLLM
reserves ten additional DFlash slots for a depth-11, one-request service. The
actual scheduler budget is therefore 8,182. Exact 8,192-, 16,384-, and
24,576-token prefills end with 10-, 20-, and 30-token chunks. In contrast, the
32,640-token case ends with a still-wide 8,094-token chunk.

This matches a strong prefill sawtooth in the frozen q12 artifacts:

| prompt tokens | median prefill tok/s | median TTFT s |
| ---: | ---: | ---: |
| 8,192 | 4,129.894 | 1.993 |
| 16,384 | 5,111.214 | 3.228 |
| 24,576 | 5,053.233 | 4.883 |
| 32,640 | 7,345.070 | 4.478 |

The target-only q1 service, which retains a full 8,192-token budget, is smooth
at about 7,089--7,505 prefill tok/s over the same ladder. This is evidence for
a scheduler-tail problem, not a claim that prompt placement or the exact-
prefill source selector causes the sawtooth.

The existing exact-prefill selector can accelerate the 20- and 30-token tails,
but its authenticated range begins at 13 tokens. It cannot activate on the
decisive 10-token 8K tail. The candidate therefore changes no source or model
arithmetic: allocate 8,202 total token slots and explicitly retain 8,192
schedulable tokens.

## Frozen arms

Both arms use:

- main harness support following `d69593cd5`;
- exact-prefill vLLM `4ddb915284d4442885f72bed48311fd04640977c`;
- XPU kernels `99886d783372e621941228250091dc8ebdc1595d`;
- q12 target / DFlash depth 11, TP4/EP4, BF16 KV, exact-prefill selector on;
- `max_model_len=32768`, GPU utilization 0.80, temporary 24 GiB total swap,
  the 8 GiB available-RAM guard, and the normal 4 GiB free-swap guard;
- the unchanged prompt suite, one 1,024-token warmup, cache-zero policy,
  repeat-oracle hashes, retrieval checks, graph topology, and teardown gates.

Control A uses `max_num_batched_tokens=8192` with automatic scheduling, which
must log an effective budget of 8,182. Candidate B uses
`max_num_batched_tokens=8202` and explicit `max_num_scheduled_tokens=8192`.
The harness rejects 8,202 unless it is paired with the explicit 8,192 budget,
q12, and the exact-prefill selector.

Run a fresh A service before B. Select all 8K placements, representative
16K/24K rows, all 32,640 placements, and the automatic post-32K sentinels. No
request retry is allowed. The device must first be freshly recovered from the
separately recorded `0000:47:00.0` reset-loop failure; this preregistration does
not authorize a reboot, reset, driver reload, FLR, or probe in the current bad
device state.

## Gates

Correctness and identity require:

- every intrinsic, retrieval, cache-zero, and repeat-oracle check passes;
- candidate output hashes and accepted/drafted/cycle counters equal control
  for every matched row;
- control and candidate logs prove their respective 8,182 and 8,192 effective
  budgets;
- all four ranks retain target 146/145 and draft 14/13 capture/replay topology;
- no memory guard, service error, device error, residual process, or teardown
  failure occurs.

Performance uses Prometheus prefill and client TTFT, with conventional decode
as the protected metric:

- the 8K median candidate prefill must be at least 1.35x control and median
  TTFT at most 0.75x control;
- 16K, 24K, and 32K candidate prefill medians must each be at least 0.98x
  control and TTFT at most 1.02x control;
- the 32K conventional decode median must be at least 0.98x control, with no
  matched long row below 0.95x; and
- the sentinel decode median must be at least 0.98x control.

The first complete valid A/B pair is the result. A failed identity, exactness,
memory, device, or cleanup gate stops the lane. This is a non-scored prompt-
processing experiment and cannot produce a LocalMaxxing submission.
