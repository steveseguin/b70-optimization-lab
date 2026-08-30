# Qwen3.8-27B TP2 request-level MTP safety candidate — preregistration

This campaign is frozen before any candidate performance run. Earlier evidence
showed that global MTP2 was repeatably faster at low concurrency but failed the
second 64-way semantic-canary round, while the matched MTP0 service passed. The
failed MTP2 value remains ineligible. A non-performance API diagnostic showed
that the candidate accepts a request-level depth of zero, preserves default
MTP2, rejects values above the server maximum, and returns identical tokens for
one diagnostic prompt. That diagnostic cannot qualify speed or quality.

The candidate exposes only `speculative.n_max`. A request may reduce the server
maximum (including disabling drafting) but may never raise it. The server
default remains unchanged. The hypothesis is that one loaded service can retain
qualified MTP2 for interactive requests while forcing target-only decoding for
throughput-sized batches.

## Frozen arms and gates

- `strict-mtp0`: fresh 1-slot target-only server; twelve-category realistic
  suite with natural EOS, zero cached tokens, and all standard canaries.
- `strict-mtp2`: fresh 1-slot default-MTP2 server; the same gates plus exact
  equality of all twelve complete token arrays to the fresh MTP0 oracle.
- `hybrid-r1` and `hybrid-r2`: two fresh 64-slot MTP2 servers. Explicit MTP0 is
  measured at synchronized concurrency 4, 8, 16, 32, and 64; explicit MTP2 is
  measured at 1 and 2. Each response must contain exactly 128 tokens, report
  zero cached prompt tokens, preserve complete token-ID evidence, and pass the
  output-isolation gate.
- Each hybrid arm runs two rounds of 64 simultaneous semantic canaries with
  request depth zero: 128/128 must pass and all reported cache counts must be
  zero.
- The server draft-token counter must be unchanged throughout the entire MTP0
  performance and semantic phase, then increase after explicit-MTP2 requests.
- A failed arm contributes no speed. No interpolation or extrapolation is
  permitted. Replicated performance is summarized by the pointwise median only
  after every gate passes.

This candidate does not automatically infer workload intent. A public recipe
may describe separate interactive and batch request policies only if both
replications qualify; it must disclose the literal request field and the tested
64-slot, 32768-total-context boundary.
