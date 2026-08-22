# Qwen3.8 MTP `fc` INT4 eager-operator screen (Q1) result

Date: 2026-08-22

Classification: **`qualified-only-for-default-off-integration-design` — PASS.**
The eager W4A16 `mtp.fc` operator is numerically valid, cross-process stable,
and far above the timing hurdle on both output-row shards. This qualifies only
the **idea** of preparing a separately reviewed, default-off integration
patch; it is not an endpoint tok/s result and does not authorize integration.

Preregistration:
[`2026-08-21-qwen38-mtp-fc-int4-operator-prereg.md`](2026-08-21-qwen38-mtp-fc-int4-operator-prereg.md)
(Q1 authorized by explicit user go-ahead 2026-08-22). Structured comparison:
[`../data/2026-08-22-qwen38-mtp-fc-int4-abba-r2-comparison.json`](../data/2026-08-22-qwen38-mtp-fc-int4-abba-r2-comparison.json)
(SHA-256 `b02d3aa038e63c22783706c1b37abdcaec5b7f265b776bb19cff402eaf06a2ed`).

## Execution

The authorized eight-arm campaign ran to `complete` on physical GPU2 under the
bounded per-arm watchdog: no timeout, no invalid arm, no wedge. The first
attempt (root `...-r1`) was a clean pre-arm health-reader catch (schema
pointer mismatch, no GPU work, preserved); r2 is the valid campaign. Result
root `/home/steve/qwen38-mtp-fc-int4-abba-20260822-r2`, aggregate
`1342d72df9d4e1597ef3875744ddbec98d10dc7374c32c3b680ca71f1278e651`.

All correctness, mutation, 32-replay bit-stability, M6/serial-M1
row-equivalence, marker, mapping, and cross-process identity gates passed on
every arm (`passed=true` throughout).

## Timing (paired A-B-B-A, 10,000-iteration hierarchical bootstrap)

Control = eager `F.linear` on the live FP16 shard; candidate = eager
`int4_gemm_w4a16` on the packed shard. Strict M6 hurdle `17.092 us/call`.

| Rank | Shape | Control us/call | Candidate us/call | Central saving | Combined 95% CI lower |
|---|---|---:|---:|---:|---:|
| 0 | M1 | 92.99 | 32.94 | `60.04` | 59.91 |
| 0 | M6 | 91.79 | 33.06 | `58.73` | 58.66 |
| 1 | M1 | 92.96 | 32.77 | `60.19` | 60.08 |
| 1 | M6 | 91.76 | 33.32 | `58.44` | 58.01 |

Every conjunctive gate cleared with wide margin: both M1 pairs nonnegative,
both M6 pairs and their combined CI lowers strictly above `17.092`. The
operator is ~2.8x faster in W4A16 (~33 vs ~92 us/call).

## Interpretation — this is not 105 tok/s

`mtp.fc` is one bias-free linear called once per MTP layer. Even at ~58 us/call
saved, and even multiplied across the five MTP draft calls per target step
(~290 us/step), this is an **operator-isolated eager** measurement, not an
endpoint rate: the real decode step is hundreds of ops, the live path is
compiled/graph-captured (not eager), and cross-rank TP2 gather, MTP
acceptance, and quality are untested here. The prereg is explicit that a pass
"cannot by itself establish or plausibly account for" 101 -> 105. The endpoint
effect is unknown and must be measured, not extrapolated.

## Disposition — integration is a separate decision

A qualified operator is not a deployed one. Building the default-off
integration patch is a **new experiment** requiring its own preregistration
and, per the campaign standard for device-risk/quality-affecting work, its own
explicit authorization. Its minimum gates (from the prereg): bind the packed
buffers to this exact `mtp.fc` only (not global linears); retain the live
BF16->FP16 load semantics; preserve `input_dependency=True` and completion
publication before the TP2 gather; register the selector in vLLM `envs.py`
compile factors; use a fresh compile-cache identity (not the sealed b991/f358
artifacts); account for FP16 + packed VRAM; and pass separately preregistered
eager, compile, graph, real-TP2, MTP-acceptance, target-token, quality, and
endpoint-throughput gates. None of that is authorized by this screen.

Preserve r1 and r2 roots; run no same-root retry.
