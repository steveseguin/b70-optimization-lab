# First exact AVX2 expert path — closeout

<!-- campaign-closeout -->

## Question and identity

Can an independently written AVX2 implementation of the current IQ3-release
expert arithmetic supply the one-card cache's misses? Tested October 17, 2026
after 02:55 UTC on the Threadripper PRO 5955WX, nice 19 and CPUs 4–15,20–31.
The unchanged packet45 CPU oracle and existing synthetic fixture definitions
are the reference; no checkpoint payload or GPU was accessed. The release's
ordinary experts use IQ2_S gate/up and IQ4_NL down, with IQ3_S gate/up in layer 2.

## Outcome

Finite CPU exactness passes: 27,587 raw checks in each of two equal fresh
processes, including 18 complete expert comparisons and 30 down edge cases.
The path is retained as a reference implementation and CPU prerequisite.

Throughput is inadequate for the budget's hypothetical uniform misses at
60 target positions/s. Fresh-process medians were 1,957.456 and 2,691.348
experts/s, processing 3.873152 and 5.325281 decimal GB/s of packed bytes.
That scenario requires 18,157 experts/s and 35.9268 GB/s. Both full sample
sets are retained; no best-process selection or engine speed is claimed.

## What worked

Eight independent logical lanes per AVX2 vector preserve the original lane
accumulation and reduction tree. The unchanged BF16 materialization points
and deterministic activation agree with the existing finite oracle. The
284,928,000-byte packed bank exceeds aggregate L3, uses 144 distinct experts
and changes inputs every sweep. Every worker's affinity and FP environment
is checked. Five samples of at least two seconds ran in each fresh process.

## What failed or remains uncertain

The current implementation cannot supply the uniform-miss scenario, even
with unrestricted independent expert parallelism. There was substantial
sample drift; its cause is unmeasured. This does not reject CPU misses with
high route locality, or establish actual dependent layer latency. Nonfinite
device-oracle parity, real-weight admission, route hit rates, CPU/GPU overlap
and exact slot-order integration remain open. Processed GB/s is not measured
DRAM bandwidth.

## Evidence and patches

- [Arithmetic specification](cpu-expert/SPECIFICATION.md),
  [implementation](cpu-expert/expert_avx2.hpp),
  [reproduction commands and results](cpu-expert/README.md).
- [Build receipt](cpu-expert/evidence/build/receipt.json),
  [fresh exactness](cpu-expert/evidence/test/receipt.json),
  [both throughput sample sets](cpu-expert/evidence/bench/receipt.json).
- [Cache requirements](CACHE-BUDGET.md) and
  [opt-in route census adapter](diagnostics/README.md).

All raw text receipts are retained. Ignored local binaries can be restored
from the pinned source closure and recorded compiler command. No rejected
implementation or original evidence was removed.

## When to revisit

Collect the opt-in IQ3 route census through a coordinator-owned diagnostic
window. Revisit CPU arithmetic throughput with a substantive exact kernel
change or a measured miss distribution; rerunning the same bank to select a
luckier score does not answer the open question. Keep GPU work in the
coordinator's admitted window and retain the existing host settings.
