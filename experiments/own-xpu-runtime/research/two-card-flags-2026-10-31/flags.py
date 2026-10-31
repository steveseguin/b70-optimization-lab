#!/usr/bin/env python3
"""The non-TP flags of the four-card stack, as one set (research/two-card-flags-2026-10-31). Both the rank-harness gate
(run_phase.sh extra `B`) and the B servers (suite/arm_env.py arm twoB) take their keys from here, so the harness gates
exactly the environment the servers run. `flags.py` prints KEY=VALUE lines.

Included (each default off, each read by the engine on a one-card rank; the four-card servers pass all of them to both
ranks, and so does arm twoB):
  decode, 2026-10-30: OWNRT_RETIRE_DEFERRED (fixed-cost), OWNRT_HC_KERNELS (hc-kernels), OWNRT_DRAFT_FAST and
    OWNRT_TARGET_FAST (fixed-cost-2);
  rank-0 decode trims, 2026-10-29: OWNRT_SNAPSHOT_NOWAIT, OWNRT_ROLLBACK_NOWAIT (rank0-trims; exact on one card there);
  prompt reading, 2026-10-29/30: OWNRT_PREFILL_LOOKUP_BATCH, OWNRT_PREFILL_MOE_NATIVE, OWNRT_DRAFT_CHUNK_REPLAY,
    OWNRT_DRAFT_CHUNK_KV_ONLY (prefill-speed), OWNRT_PREFILL_SPECIAL_ROWS, OWNRT_PREFILL_LOOKUP_THREADS=4,
    OWNRT_DRAFT_CHUNK_STAGE_THREAD, OWNRT_DRAFT_CHUNK_GUARD_ROW, OWNRT_DRAFT_CHUNK_ROW_COPY (prefill-host),
    OWNRT_DRAFT_CHUNK_BATCH (prefill-draft-batch).
Left out as TP-only: OWNRT_PREFILL_XZERO_ONCE (zeroes TP prefill exchange slots; prefill_engine.hpp runs it only under
--tp-replicate), OWNRT_TP_* (exchange, experts, GDN, QSA split, HC split, expert pair, threads, card context),
OWNRT_TARGET_HEAD_SPLIT, OWNRT_DRAFT_HEAD_SPLIT, OWNRT_DRAFT_GEMV_SPLIT (split across a rank's two cards)."""
B = dict(
    OWNRT_RETIRE_DEFERRED='1', OWNRT_HC_KERNELS='1', OWNRT_DRAFT_FAST='1', OWNRT_TARGET_FAST='1',
    OWNRT_SNAPSHOT_NOWAIT='1', OWNRT_ROLLBACK_NOWAIT='1',
    OWNRT_PREFILL_LOOKUP_BATCH='1', OWNRT_PREFILL_MOE_NATIVE='1', OWNRT_DRAFT_CHUNK_REPLAY='1', OWNRT_DRAFT_CHUNK_KV_ONLY='1',
    OWNRT_PREFILL_SPECIAL_ROWS='1', OWNRT_PREFILL_LOOKUP_THREADS='4', OWNRT_DRAFT_CHUNK_STAGE_THREAD='1',
    OWNRT_DRAFT_CHUNK_GUARD_ROW='1', OWNRT_DRAFT_CHUNK_ROW_COPY='1', OWNRT_DRAFT_CHUNK_BATCH='1')
# The decode-only part (for a harness split of the timing; not a server arm).
DECODE = ('OWNRT_RETIRE_DEFERRED', 'OWNRT_HC_KERNELS', 'OWNRT_DRAFT_FAST', 'OWNRT_TARGET_FAST')
TRIMS = ('OWNRT_SNAPSHOT_NOWAIT', 'OWNRT_ROLLBACK_NOWAIT')
if __name__ == '__main__':
    import sys
    part = sys.argv[1] if len(sys.argv) > 1 else 'B'
    keys = {'B': tuple(B), 'decode': DECODE, 'nonw': tuple(k for k in B if k not in TRIMS)}[part]
    for k in keys:
        print(f'{k}={B[k]}')
