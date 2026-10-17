# Final source and evidence review

This is the implementer's review, not an independent agent review.

- Production controls: full normalized expert/HC bodies, exact compact row
  pitches820/360 and byte-identical SPEED6 small-FFN dispatch checked by
  `check_controls.py`; its source identity is part of the seal.
- Reduction mapping: V lower adjacent levels in registers, remaining levels
  in32/V physical lanes; no chain mixes its sum with another before the same
  original tree point. Down and dense split tails retain per-chain checks.
- Split-stream gate/up: each row/output is assigned exactly once; route/status
  and sticky error writes retain their independent stream destinations.
- HC: all work-items reach the Split4 barrier; partial indices are row*4+part;
  BF16 output and activation are captured. Both sides remain separate calls.
- Small FFN: all four members execute in one launch; padded scalar rows cannot
  skip a barrier. Its production control is p30.small.rows4.
- Exactness: actual production capture and independent CPU production bytes
  must both equal each candidate. A candidate's own mirror cannot pass alone.
- Timing: HC contributes four events; all other classes contribute one. M2
  sums both serial rows; selection uses M1 only, common across two owners,
  with the35 µs bar checked independently in each.
- Supervision: inherited PF_EXITING handling, past UTC review, source/binary/
  companion hash checks, foreign-client refusal and cooperative drain remain.
  All17 mocked tests pass without a device or kernel-journal invocation.
- Register qualification: final15-kernel offline census includes the HC low
  control. New split-stream gate V8/V16 have no spill metadata. Original V4
  and HC low scratch metadata are explicitly reported, never waived silently.
- Storage: cleanup removes only inventoried, regenerable scratch in this new
  packet. Final binaries, source mirrors, CPU results and native assembly stay.

Device equality, fresh-process device repeats and timing are pending. There
is no oracle regeneration, model result, engine integration or speed claim.
