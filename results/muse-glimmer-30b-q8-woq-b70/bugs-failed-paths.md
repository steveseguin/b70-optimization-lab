# Important bugs, failed paths, and audit notes

- The historical `argmax-noprofile` filename is wrong. `LLAMA_SPEC_PROFILE=0`
  enabled profiling because the code tested environment-variable presence.
  The >100 result remains valid and was measured with that overhead active.
- The old canonical harness inherited arbitrary experimental flags, defaulted
  to another source tree unless `MUSE_SWEEP_BIN` was supplied, appended JSONL,
  and overwrote its fixed server log. Only run 2's log survived. The promoted
  runner sanitizes flags and uses unique directories/logs.
- The old realistic harness defaulted to TOP_K. The final record uses ARGMAX;
  the promoted runner sets that identity explicitly.
- The old realistic manifest hashed `server.log` before teardown appended its
  summary. The promoted runner stops the server before hashing.
- BF16 graph conversion caching changed proposal history and regressed the
  final packet; the record keeps it off.
- Functional DDTree reached 88.651 tok/s but could not close its remaining
  6.375 ms/round gap. Wider trees, repair forests, DSpark/dual-draft routes,
  target lookahead, custom exact GEMMs, attention redistribution, and Q/gate
  lending were measured or bounded as insufficient/regressive.
- The original BF16 exact/lossless target did not reach 100. The successful
  record changes the target arithmetic and is published as Q8/WOQ.

Chronological detail and negative artifacts remain under
[`experiments/muse-glimmer-30b-b70`](../../experiments/muse-glimmer-30b-b70/README.md).
