# Qwen3.8 Q4_K_M + Q4_0 MTP2 TP2 screen R1 preregistration

Date: 2026-08-30
Status: preregistered; no model request run

## Question

Does the qualified one-B70 Q4_0 MTP2 draft improve the qualified two-B70
Q4_K_M target while retaining complete target output on this local host?

This fills a missing deployment cell. It does not transfer the one-B70 MTP2
gain or the two-B70 target-only speed into a fabricated estimate.

## Frozen identity and order

The structured preregistration is
[`../data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-screen-r1-prereg.json`](../data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-screen-r1-prereg.json).
It binds the already-qualified target, draft, llama-server, SYCL backend, and
fixed 12-prompt/six-class realistic suite by SHA-256.

Run exactly:

1. one fresh TP2/MTP0 oracle;
2. only if it passes, one fresh TP2/MTP2 candidate;
3. compare all complete returned token arrays.

The target is split equally across `SYCL0,SYCL1`; the small draft stays on
`SYCL0`. Both arms use F16 KV, 8K configured context, one slot, cache disabled,
reasoning off, batch 1024, ubatch 256, and the conventional 99-interval metric.

## Gate and boundary

Both arms must pass the complete varied suite, cache-zero gate, objective
canaries, clean shutdown, and GPU postflight. MTP2 must match the MTP0 oracle
on 12/12 complete arrays. Any boot, quality, parity, cache, or GPU fault stops
the campaign. A printed speed from a failed arm is not a result.

One passing MTP2 arm remains diagnostic. It authorizes only a separately
preregistered fresh-server replication; it does not authorize publication,
long-context values, concurrency values, deeper MTP, or LocalMaxxing.

Runner:
[`../scripts/run-20260827-qwen38-q4km-q4mtp-tp1-screen-attempt.sh`](../scripts/run-20260827-qwen38-q4km-q4mtp-tp1-screen-attempt.sh),
using its default-preserving `TP_SIZE=2` mode.
