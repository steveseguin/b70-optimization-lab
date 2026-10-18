# Packet58t boundaries

- Do not modify packet58p, packet58r or any other frozen parent to adopt this
  change. Copy-forward source and byte identities are part of the evidence.
- Do not copy only benchmark-selected lookup rows. Every row of both exact
  packed tensors is copied at load; prompt/history selection is unchanged.
- Do not replace anonymous copies with page-cache advice, mlock, a whole-model
  pre-read, swap changes or dropped caches. No startup fallback to sparse
  lookup backing is allowed for the resident candidate.
- Do not count anonymous lookup reads as disk traffic. The inherited native
  model-payload byte field is logical reads, not physical I/O.
- Do not leave exactness admission at its old sparse-lookup budget. It requires
  an additional 29,321,610,240 bytes. Timing already reserved that amount; its
  accounting category changes. Keep all device/cache/KV bounds and 8 GiB reserve.
- Do not claim this one-load screen reproduces the old cold file state: its
  load necessarily reads the source pages before A0. All views retain copies.
- CPU synthetic equality and zero fault counters are not production device
  parity, a speed result, a fresh-process repeat or a 512-token final gate.
- Do not publish or queue the seven-window chain based on 58n's tile16 result.
  The candidate has new binaries and requires its own resident screen evidence.
- A failed copy must drain the initialized owner. Keep the shared teardown
  proof and fault/live-child refusals; never turn a clean failure into success.

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).
