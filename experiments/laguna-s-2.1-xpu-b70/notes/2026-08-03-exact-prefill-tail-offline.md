# Laguna exact pure-prefill tail decomposition

Date: 2026-08-03 America/Toronto

Status: **default-off offline implementation committed and host-tested; raw
XPU, model, endpoint, and performance evidence remain unmeasured**.

## Hypothesis

The incumbent long-context scheduler partition is not changed. With its
effective 8,182-token chunks, exact prompt lengths 8,192, 16,384, and 24,576
leave pure-prefill tails of 10, 20, and 30 rows. The first exact-prefill
treatment activates only for 13--512 rows and sends every non-M12 MoE tail
row through the scalar path.

The new treatment extends the existing authenticated marker to pure-prefill
widths 2--512. Linear layers retain their independent batched-M1 arithmetic.
Laguna MoE decomposes the row set into the combination of exact M12 and M8
chunks that leaves the fewest scalar rows, then concatenates the outputs in
original row order:

- 10 rows: `8 + 1 + 1`;
- 20 rows: `12 + 8`;
- 28 rows: `12 + 8 + 8`;
- 30 rows: `12 + 8 + 8 + 1 + 1`;
- 32 rows: `12 + 12 + 8`.

This does not alter `max_num_batched_tokens`, prompt construction, graph
topology, decode/verifier width, draft depth, KV precision, or scheduler
partition. The selector remains literal `0`/`1` and default off.

## Source identity

Worktree and branch:

```text
/home/steve/src/laguna-vllm-e2e-latency-integration-20260803
experiment/laguna-e2e-latency-integration-20260803
```

Commits:

- `f9e167ad0`: combine the measured exact-prefill treatment with the INT4
  tile-record integration;
- `015fee586`: plan and dispatch exact M12/M8/scalar prefill tails.

Changed source is limited to Laguna's model-side chunk planner and the
model-runner's already strict pure-prefill width bound. Existing guards still
reject selector-off, one row, more than 512 rows, padding, multiple requests,
cascade attention, ubatching, graph replay, speculation, encoder inputs,
LoRA, KV-scale calculation, and prompt-boundary crossing.

## Offline validation

The combined host run passed **56 tests**. It includes the tile-record
host/static/post-load suites, exact-prefill configuration and fail-closed
eligibility cases, representative M12/M8/scalar dispatch cases, and an
exhaustive planner invariant over every width from 2 through 512. Ruff lint,
test-file formatting, and whitespace checks pass.

An independent read-only source audit found no implementation blocker. It
confirmed that every plan uses only widths 12, 8, and 1; covers every input
row exactly once in order; minimizes scalar rows; and minimizes call count
among plans with the same scalar remainder. Existing Python and native router
guards admit only M8/M12, while the prefill contract still requires both M8
and M-wide authenticated router selectors.

This is not numerical proof. M8 and M12 use different expert execution paths,
and M8 under the M12 shared-elementwise selector intentionally uses generic
shared elementwise work. Host inspection cannot certify native arithmetic,
collective ordering, or end-to-end output.

## Required future gate

No run is authorized by this note. When the device/NVMe quarantine is
separately lifted, require:

1. raw bitwise linear, router, MoE, and final-logit equality against scalar
   execution for widths 8, 10, 11, 12, 16, 20, 24, 28, and 30;
2. fresh adjacent selector-off/on services for the existing 8K, 16K, and 24K
   prompt rows and their sentinels;
3. unchanged prompt hashes, retrieval, repeat-oracle output hashes,
   accepted/drafted/cycle counters, cache-zero status, and target/draft graph
   topology;
4. improved TTFT, request wall time, and Prometheus prefill rate; and
5. protected short-suite q1 exactness plus conventional decode at least 0.99x
   adjacent control, with no matched row below 0.95x.

The 8K baseline is the main sawtooth target: 4,129.894 prefill tok/s and
1.993 seconds TTFT, versus about 7.3K tok/s in the neighboring smooth lane.
These baseline values motivate the treatment; they are not a projected or
measured candidate win.

For 32K decode, the accepted-position diagnostic remains higher priority than
another short-context attention rewrite. Median acceptance is about 0.56%,
but the mixed-depth hypothesis is still unmeasured. Paired-row attention was
208/208 raw-BF16 exact yet slower at base contexts 89--962; a future long-only
screen would need separate 8K/16K/24K/32K component evidence before any port.

The NVMe/device quarantine remains controlling. No model, XPU probe, native
component, service, benchmark, swap change, reset, reboot, or recovery action
was performed.
