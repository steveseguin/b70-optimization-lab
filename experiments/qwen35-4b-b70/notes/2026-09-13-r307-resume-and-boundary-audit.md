# R307 continuation: boundary evidence and remaining gates

Resumed the saved Fable work on 2026-09-13. The final saved change is
`19c7604be`: it also flags handoffs when the entire next step has no drafts.
The earlier R307 attempts are not equivalent to this revision.

## Completed diagnostic evidence

The final debug run (`r307-debug7`, completed 15:57 EDT) passes:

- tail offsets 236 through 241, two repeats: **12/12 exact**;
- sequential boundary requests: **36/36 exact**, no errors;
- four-request concurrency boundary requests: **72/72 exact**, no errors.

The boundary harness prints 38 and 74 rows because each includes two skipped
prompt lengths. Those are not successful requests. Copies of the original
results and their no-speculation oracles are in
[`../data/2026-09-13-r307-boundary-debug7/summary.json`](../data/2026-09-13-r307-boundary-debug7/summary.json),
with source paths and SHA256 hashes. Comparisons in the boundary harness are
completion-text hashes; the tail harness compares token strings.

The debug image tag inspected after the run resolves to
`sha256:081e349f620ffbec2959b2c94a000a8446cfc1ee37ea5b507fbd36a9e3d3bd62`.
This is an after-run observation, not a launch-time immutable pin. The
non-debug R307 candidate used by the running regression chain is
`sha256:9be49c62baabf4611ecf08419d836a2e2f171adba5d2a28509b6fd796e7d28c3`.
Debug success does not certify that candidate.

## Probe correction

`boundary-tail-probe.py` now rejects offsets outside the oracle continuation
and reconstructed prefixes whose token count differs from `L+n`. It reports
the shorter length as `first_diff` when the outputs differ only in length.
Five mocked-response checks passed: equal output, unequal token, truncated
output, changed prefix length, and invalid offset.

The old dump contains token strings, so equal prefix length still does not
prove token-ID identity. Future strict tail qualification should capture
oracle token IDs and submit token-ID prefixes. Draft acceptance also affects
the final step width; offset alone does not prove the runtime schedule.

## Source audit

For the current fixed-depth `FULL_DECODE_ONLY` configuration, the runner marks
a batch uniform only when every request has width `1+num_spec_tokens`.
One-token handoff, partial-width, and mixed-width steps therefore fall outside
full-graph replay. The debug launcher does use `FULL_DECODE_ONLY`; describing
its whole run as eager would be incorrect. A dynamic-width capture overlay
would need a separate review.

The mixed-width branch groups all requests of the same width into one call,
bypassing the ordinary `VLLM_XPU_GDN_SPEC_GROUP` grouping limit. The c4 result
does not establish its behavior above that limit. The patch is XPU-specific:
shared metadata resets accepted counts, but the matching state move is in
`_xpu_ops.py`; it must not be applied as a CUDA fix unchanged.

## Already running when resumed

Preserved both existing runners:

- `run-20260913-r307-regression-chain.sh`: 4B and 9B fresh strict pairs,
  2K–32K ladder, c64 identity, and short-prompt alias checks. Wrapper:
  `/mnt/fast-ai/bench-results/r307-regression-20260913-wrapper.log`.
- `/mnt/fast-ai/bench-results/rebase-v0290-20260912/stock-boundary/run.sh`:
  stock v0.29.0 target-only oracle followed by MTP boundary checks on card 1.

The strict chain runs on card 0. Concurrent stock work may affect host timing;
these runs must not support a new speed claim without isolated replication.
The wrappers can emit DONE after failed stages; inspect result JSON, stage
exit codes, and postflights before declaring success. No R307 promotion is
established by this note.
