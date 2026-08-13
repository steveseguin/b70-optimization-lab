# TP backend sampling / global argmax: integration negative

Date: 2026-08-13

## Decision

Close this as a verifier-tail integration negative, not a measured throughput
result.  The existing SYCL TP maxloc collective was reached, but the first
completion request still terminated immediately afterward and no token or
timing row was produced.  Further sampler-graph integration is not justified
against the small host-logit-transfer/sampling ceiling while the campaign
still needs at least `10.73 ms/round` of independent verifier savings.

No drafter training, weight change, reboot, or production deployment occurred.
All changes are default-off or require an explicit backend-sampling request.

## Why this was tested

TP mode unconditionally rejected target backend sampling even though the meta
backend now has a SYCL global ARGMAX/maxloc path.  CPU sampling therefore keeps
the raw-logit synchronization/copy path.  The experiment tried to replace it
with a device ARGMAX and a tiny token-ID copy.

## Source and request identity

- source `37cfef2dd`: default-off `LLAMA_TP_BACKEND_SAMPLING=1` gate;
- source `524e5ed5c`: preserve the vocabulary-axis split for the reserve-only
  padded `[vocab, 0] -> [vocab, 1]` sampling dummy;
- source `ec3eb6087`: express the explicit
  `temperature=0, samplers=[temperature]` chain as logit-bias plus direct
  greedy ARGMAX, avoiding an unnecessary distributed winning-logit fetch;
- candidate also set `GGML_SYCL_COMM_ARGMAX=1` and the retained verifier flags;
- control left both TP backend sampling and the communicator ARGMAX disabled;
- sweep identity:
  `sweeps/20260813-tp-backend-sampling-argmax-ab.json`.

## Failure progression

1. The initial candidate exposed an UNKNOWN split for the sampling reserve's
   zero-row `result_output` source under PAD.  The strict dummy-row rule in
   `524e5ed5c` resolved that allocation failure.
2. The ordinary temperature-zero backend path then attempted GET_ROWS from a
   vocabulary-axis-sharded tensor using the mirrored global winner index.  TP
   does not implement that distributed gather.  The explicit direct-greedy
   chain in `ec3eb6087` removes the semantically unnecessary logit fetch.
3. With both fixes, the log proves the intended fast path was entered:
   `argmax fast path: n_backends=4 n_rows=1
   shard_widths=50512,50512,50512,50512`.  The request nevertheless closed
   before the server produced a response or error row.  The harness then
   terminated the isolated server and released the GPU lock.

Because no candidate completed, the JSONL is intentionally empty and this is
not an A/B performance result.

## Evidence

- final server log:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-tp-backend-sampling-argmax-ab-20260813-tp-backend-argmax-on-a.log`;
- log SHA-256:
  `3874b940bcb4ad726fffa5d36652ca4c81c2d9722c3bb94ac8b1e19ca3efc613`;
- empty result file:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/tp-backend-sampling-argmax-ab-20260813.jsonl`;
- empty-file SHA-256:
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Production was restored after each bounded attempt without reboot.  The final
fleet restore passed the full cache-zero code/vision health gate in
`data/muse-health-20260813-tp-backend-sampling-final-restore.json`.

## Revisit gate

Only reopen if a broader target-sampling redesign already needs distributed
sampling graph support, or if a direct timing proves raw-logit transfer and CPU
sampling consume several milliseconds per verifier round.  Do not reopen just
to chase this crash: even a successful implementation does not have a credible
standalone path to the campaign's remaining `>100 tok/s` gap.

## Terminal-greedy retry

The route was retried once after source commit `35e462c5a` fixed terminal
backend-greedy semantics for the successful DFlash offload.  A three-class,
eight-token smoke again reached the four-rank maxloc fast path, completed the
first target decode, and closed the connection during the next target decode.
The result JSONL is empty.

This confirms the target route has a separate structural problem.  DFlash
verification consumes target-row logits after the decode to validate its
candidate chain; making target greedy terminal removes logits that this
verification path still needs.  A valid implementation would have to return
per-row target decisions while preserving the verifier dataflow, rather than
attaching an ordinary terminal sampler to the target context.  That redesign
is not justified by the one-sample-per-round ceiling.

Retry identity:
`sweeps/20260813-target-tp-greedy-fix-smoke.json`; server log:
`/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-target-tp-greedy-fix-smoke-20260813-target-device-greedy-terminal-fix.log`,
SHA256 `ba48f9a8201521a04fe4ec0d2470f39d4b5da5c37d4cebadaa58fbf1320acd32`.
The empty JSONL has the canonical empty-file SHA256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Production was restored without reboot and passed the full health gate in
`data/muse-health-20260813-target-tp-greedy-fix-smoke-restore.json`.
