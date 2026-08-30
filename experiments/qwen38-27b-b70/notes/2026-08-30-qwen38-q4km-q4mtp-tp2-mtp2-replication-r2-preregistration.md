# Qwen3.8 Q4_K_M + Q4_0 MTP2 TP2 replication R2 preregistration

Date: 2026-08-30
Status: preregistered; no R2 model request run

## Basis

The R1 screen passed its workload and canary gates at `64.18064352599666`
tok/s versus the fresh TP2/MTP0 oracle's `49.78736600126793` tok/s. All 12
complete candidate token arrays matched the oracle exactly. The R1 result is
still diagnostic and explicitly has `promotion_authorized=false`.

The structured R2 preregistration is
[`../data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-replication-r2-prereg.json`](../data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-replication-r2-prereg.json).
It binds the R1 result, both R1 performance artifacts, target, draft, runtime,
backend, and fixed realistic suite by SHA-256.

## Frozen replication

Run one new server process with the unchanged TP2/MTP2 contract: Q4_K_M target
split equally over `SYCL0,SYCL1`, Q4_0 draft on `SYCL0`, F16 KV, 8K configured
context, one slot, batch 1024, ubatch 256, eight CPU threads, cache disabled,
reasoning off, and the complete 12-prompt/six-class suite at a 512-token cap.

The replication passes only if it:

- passes the complete realistic final gate and all canaries;
- reports zero cached tokens on every prompt;
- exactly matches both the oracle and R1 candidate arrays on 12/12 prompts;
- remains at least 20% faster than the frozen oracle;
- stays within 5% of the R1 candidate rate; and
- exits without a new GPU fault.

Failure blocks promotion. Success permits preparation of a separate,
hash-bound promotion attestation and package update; it does not create 32K,
concurrency, or deeper-MTP evidence.
