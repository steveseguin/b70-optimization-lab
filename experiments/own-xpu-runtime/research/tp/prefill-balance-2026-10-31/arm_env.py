#!/usr/bin/env python3
"""Environment of each arm of research/tp/service-ready-2026-10-29. Prints KEY=VALUE lines for `arm_env.py ARM`.

All arms: the B19 service flags (unit at commit eb61e0d71: F32, split 23, context 65536, QSA raw ring, shadow packing,
256-row batched prefill) without sessions/keeper/continuation, OWNRT_NO_DRAFT_TIMING=1 (as the e2e suite's arm B; TP
cannot time the draft), and the multi-card launch keys NEOReadDebugKeys=1 EnableDeferBacking=0. The engine receipt
comes from SC117_ENGINE_RECEIPT in the caller's environment.
  two   two cards: rank 0 on 23:00.0, rank 1 on 47:00.0 (the control).
  tp    four cards: rank 0 on 23:00.0+27:00.0, rank 1 on 43:00.0+47:00.0, exact TP (Stage 2b layout).
  tps   tp with the rank-0 draft head split by vocabulary rows across 23:00.0+27:00.0 (OWNRT_DRAFT_HEAD_SPLIT=1).
  tpt   tp with the rank-1 target head split by vocabulary rows across 43:00.0+47:00.0 (OWNRT_TARGET_HEAD_SPLIT=1).
  tpts  tpt plus the rank-0 draft head split (OWNRT_DRAFT_HEAD_SPLIT=1).
Overrides: ARM_CONTEXT, ARM_PREFILL_ROWS (CPU plan probes only), ARM_SPLIT (SC117_TARGET_SPLIT; default 23).
Copy for research/tp/draft-split-2026-10-29 (from service-ready-2026-10-29): adds the tps arm and ARM_SPLIT.
Copy for research/tp/target-head-split-2026-10-29: adds the tpt and tpts arms.
Copy for research/tp/rank0-trims-2026-10-29: adds tptsx, tpts plus the three opt-in rank-0 trims
(OWNRT_SNAPSHOT_NOWAIT=1, OWNRT_DRAFT_GEMV_SPLIT=1 (qsa.qgate), OWNRT_ROLLBACK_NOWAIT=1).
Copy for research/tp/qsa-split-2026-10-29: adds tptsxq, tptsx plus the QSA split by KV group (OWNRT_TP_QSA_SPLIT=1) on both TP ranks.
Copy for research/tp/persistent-thread-2026-10-29: adds tptsxqp, tptsxq plus one persistent card-1 submission thread per TP
process (OWNRT_TP_PERSISTENT_THREAD=1) on both TP ranks.
Copy for research/tp/fault-ladder-2026-10-29: adds tptsxqc, tptsxq plus one SYCL context per card over the shared native
Level Zero context (OWNRT_TP_CARD_CONTEXT=1) on both TP ranks.
Copy for research/tp/ctx131072-2026-10-29: adds tptsxqcp, tptsxqc plus the persistent card-1 submission thread
(OWNRT_TP_PERSISTENT_THREAD=1) on both TP ranks (the re-test of persistent-thread-2026-10-29 on the per-card-context path).
ARM_CONTEXT=131072 runs any four-card arm at 131072 (the engine admits it for --tp-replicate ranks only).
Copy for research/tp/prefill-tp-overhead-2026-10-30: adds tptsxqckf (fixed-cost-2026-10-30: tptsxqck + OWNRT_TP_EXPERT_PAIR=1
OWNRT_RETIRE_DEFERRED=1) and tptsxqckh (tptsxqckf + OWNRT_PREFILL_SPECIAL_ROWS=1, OWNRT_PREFILL_LOOKUP_THREADS=4,
OWNRT_DRAFT_CHUNK_STAGE_THREAD=1, OWNRT_DRAFT_CHUNK_GUARD_ROW=1, OWNRT_DRAFT_CHUNK_ROW_COPY=1).
Copy for research/tp/prefill-tp-overhead-2026-10-30: adds tptsxqckhb (tptsxqckh + OWNRT_DRAFT_CHUNK_BATCH=1), tptsxqckhc (tptsxqckh + OWNRT_HC_KERNELS=1) and
tptsxqckhcb (tptsxqckhc + OWNRT_DRAFT_CHUNK_BATCH=1).
Copy for research/tp/prefill-tp-overhead-2026-10-30: adds tptsxqckhcbx (tptsxqckhcb + OWNRT_PREFILL_EXPERT_PARITY=1) and
tptsxqckhcbv (tptsxqckhcb + OWNRT_PREFILL_CONV_ROWS=1).
Copy for research/tp/prefill-speed-2026-10-29: adds tptsxqcf, tptsxqc plus the four opt-in prefill changes on both TP ranks
(OWNRT_PREFILL_LOOKUP_BATCH=1, OWNRT_PREFILL_MOE_NATIVE=1, OWNRT_PREFILL_XZERO_ONCE=1, OWNRT_DRAFT_CHUNK_REPLAY=1), and
tptsxqck, tptsxqcf plus OWNRT_DRAFT_CHUNK_KV_ONLY=1 (head-off prompt rows issue only the draft's KV-append sites)."""
import os, sys
E = '/home/steve/llm-optimizations/experiments/own-xpu-runtime'
COMMON = dict(
    SC117_ACTIVATIONS='f32', SC117_CONTEXT=os.environ.get('ARM_CONTEXT', '65536'), SC117_ADAPTER='adapter6_tp.py',
    SC117_ENGINE_RECEIPT=os.environ.get('SC117_ENGINE_RECEIPT', f'{E}/engine/receipts/16ed1ff1a203.json'),
    SC117_PREFILL_ROWS=os.environ.get('ARM_PREFILL_ROWS', '256'),
    SC117_DISPATCH=f'{E}/gsq-rco-iq3s/serving/lan/dispatch-f32-select-gdn2.json', SC117_TARGET_SPLIT=os.environ.get('ARM_SPLIT', '23'),
    SC117_SESSIONS='0', SC117_KEEPER='0', SC117_CONTINUE='0',
    OWNRT_DRAFT_PREFIX_ROWS='91392', OWNRT_MISS='banks-batch', OWNRT_SNAPSHOT_HOST='static',
    OWNRT_DRAFT_KERNELS='qsa_attention,attention_output,fuse_attention_combine,hc_a_low,hc_f_low,hc_final_low,fuse_hc_a_low,fuse_hc_f_low,fuse_hc_final_low,hc_final_gate,fuse_hc_final_mix,hc_a_inject,hc_f_inject,embedding_norm,hidden_norm,hc_a_norm,hc_f_norm,final_norm,hidden_projection,embedding_projection,fuse_hidden_merge,qsa_k,qsa_v,qsa_iq,qsa_ik,router,shared_gate,shared_up,shared_down,shared_router,fuse_shared_activation',
    OWNRT_MERGE_CHECKS='1', OWNRT_SELECT_TOPK='1', OWNRT_SELECT_FAST='1', OWNRT_RESET_DEVICE_ZERO='1',
    OWNRT_ATTN_HEADS='1', OWNRT_ATTN_COMBINE2='1', OWNRT_PREFILL_REUSE2='1', OWNRT_EXPERTS_V2='1',
    OWNRT_DENSE_DECODE_V2='1', OWNRT_PREFILL_EXPERTS='1', OWNRT_DENSE_RAW='1', OWNRT_QSA_RAW_RING='1',
    OWNRT_PREFILL_SHADOW_PACK='1', OWNRT_DECODE_NEXT='1', OWNRT_DECODE_NEXT2='1', OWNRT_DRAFT_HEAD_RAW='1',
    OWNRT_DRAFT_ATTN='1', OWNRT_DRAFT_EXPERTS_V2='1', OWNRT_DRAFT_MERGE='1', OWNRT_GDN_PREP='1',
    OWNRT_NO_DRAFT_TIMING='1', NEOReadDebugKeys='1', EnableDeferBacking='0')
TP = dict(OWNRT_TP_EXCHANGE='direct', OWNRT_TP_THREADS='1', OWNRT_TP_EXPERTS='compact', OWNRT_TP_GDN='heads',
          OWNRT_TP_SPLIT='.attention,.gdn.qkv')
ARMS = {
    'two': dict(SC117_RANK_BDFS='0000:23:00.0,0000:47:00.0'),
    'tp': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', **TP),
    'tps': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_DRAFT_HEAD_SPLIT='1', **TP),
    'tpt': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', **TP),
    'tpts': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', OWNRT_DRAFT_HEAD_SPLIT='1', **TP),
    'tptsx': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', OWNRT_DRAFT_HEAD_SPLIT='1',
                  OWNRT_SNAPSHOT_NOWAIT='1', OWNRT_DRAFT_GEMV_SPLIT='1', OWNRT_ROLLBACK_NOWAIT='1', **TP),
    'tptsxq': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', OWNRT_DRAFT_HEAD_SPLIT='1',
                   OWNRT_SNAPSHOT_NOWAIT='1', OWNRT_DRAFT_GEMV_SPLIT='1', OWNRT_ROLLBACK_NOWAIT='1', OWNRT_TP_QSA_SPLIT='1', **TP),
    'tptsxqp': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', OWNRT_DRAFT_HEAD_SPLIT='1',
                    OWNRT_SNAPSHOT_NOWAIT='1', OWNRT_DRAFT_GEMV_SPLIT='1', OWNRT_ROLLBACK_NOWAIT='1', OWNRT_TP_QSA_SPLIT='1',
                    OWNRT_TP_PERSISTENT_THREAD='1', **TP),
    'tptsxqc': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', OWNRT_DRAFT_HEAD_SPLIT='1',
                    OWNRT_SNAPSHOT_NOWAIT='1', OWNRT_DRAFT_GEMV_SPLIT='1', OWNRT_ROLLBACK_NOWAIT='1', OWNRT_TP_QSA_SPLIT='1',
                    OWNRT_TP_CARD_CONTEXT='1', **TP),
    'tptsxqcf': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', OWNRT_DRAFT_HEAD_SPLIT='1',
                     OWNRT_SNAPSHOT_NOWAIT='1', OWNRT_DRAFT_GEMV_SPLIT='1', OWNRT_ROLLBACK_NOWAIT='1', OWNRT_TP_QSA_SPLIT='1',
                     OWNRT_TP_CARD_CONTEXT='1', OWNRT_PREFILL_LOOKUP_BATCH='1', OWNRT_PREFILL_MOE_NATIVE='1',
                     OWNRT_PREFILL_XZERO_ONCE='1', OWNRT_DRAFT_CHUNK_REPLAY='1', **TP),
    'tptsxqck': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', OWNRT_DRAFT_HEAD_SPLIT='1',
                     OWNRT_SNAPSHOT_NOWAIT='1', OWNRT_DRAFT_GEMV_SPLIT='1', OWNRT_ROLLBACK_NOWAIT='1', OWNRT_TP_QSA_SPLIT='1',
                     OWNRT_TP_CARD_CONTEXT='1', OWNRT_PREFILL_LOOKUP_BATCH='1', OWNRT_PREFILL_MOE_NATIVE='1',
                     OWNRT_PREFILL_XZERO_ONCE='1', OWNRT_DRAFT_CHUNK_REPLAY='1', OWNRT_DRAFT_CHUNK_KV_ONLY='1', **TP),
    'tptsxqckf': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', OWNRT_DRAFT_HEAD_SPLIT='1',
                      OWNRT_SNAPSHOT_NOWAIT='1', OWNRT_DRAFT_GEMV_SPLIT='1', OWNRT_ROLLBACK_NOWAIT='1', OWNRT_TP_QSA_SPLIT='1',
                      OWNRT_TP_CARD_CONTEXT='1', OWNRT_PREFILL_LOOKUP_BATCH='1', OWNRT_PREFILL_MOE_NATIVE='1',
                      OWNRT_PREFILL_XZERO_ONCE='1', OWNRT_DRAFT_CHUNK_REPLAY='1', OWNRT_DRAFT_CHUNK_KV_ONLY='1',
                      OWNRT_TP_EXPERT_PAIR='1', OWNRT_RETIRE_DEFERRED='1', **TP),
    'tptsxqckh': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', OWNRT_DRAFT_HEAD_SPLIT='1',
                      OWNRT_SNAPSHOT_NOWAIT='1', OWNRT_DRAFT_GEMV_SPLIT='1', OWNRT_ROLLBACK_NOWAIT='1', OWNRT_TP_QSA_SPLIT='1',
                      OWNRT_TP_CARD_CONTEXT='1', OWNRT_PREFILL_LOOKUP_BATCH='1', OWNRT_PREFILL_MOE_NATIVE='1',
                      OWNRT_PREFILL_XZERO_ONCE='1', OWNRT_DRAFT_CHUNK_REPLAY='1', OWNRT_DRAFT_CHUNK_KV_ONLY='1',
                      OWNRT_TP_EXPERT_PAIR='1', OWNRT_RETIRE_DEFERRED='1', OWNRT_PREFILL_SPECIAL_ROWS='1',
                      OWNRT_PREFILL_LOOKUP_THREADS='4', OWNRT_DRAFT_CHUNK_STAGE_THREAD='1', OWNRT_DRAFT_CHUNK_GUARD_ROW='1',
                      OWNRT_DRAFT_CHUNK_ROW_COPY='1', **TP),
    'tptsxqckhb': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', OWNRT_DRAFT_HEAD_SPLIT='1',
                      OWNRT_SNAPSHOT_NOWAIT='1', OWNRT_DRAFT_GEMV_SPLIT='1', OWNRT_ROLLBACK_NOWAIT='1', OWNRT_TP_QSA_SPLIT='1',
                      OWNRT_TP_CARD_CONTEXT='1', OWNRT_PREFILL_LOOKUP_BATCH='1', OWNRT_PREFILL_MOE_NATIVE='1',
                      OWNRT_PREFILL_XZERO_ONCE='1', OWNRT_DRAFT_CHUNK_REPLAY='1', OWNRT_DRAFT_CHUNK_KV_ONLY='1',
                      OWNRT_TP_EXPERT_PAIR='1', OWNRT_RETIRE_DEFERRED='1', OWNRT_PREFILL_SPECIAL_ROWS='1',
                      OWNRT_PREFILL_LOOKUP_THREADS='4', OWNRT_DRAFT_CHUNK_STAGE_THREAD='1', OWNRT_DRAFT_CHUNK_GUARD_ROW='1',
                      OWNRT_DRAFT_CHUNK_ROW_COPY='1', OWNRT_DRAFT_CHUNK_BATCH='1', **TP),
    'tptsxqckhc': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', OWNRT_DRAFT_HEAD_SPLIT='1',
                      OWNRT_SNAPSHOT_NOWAIT='1', OWNRT_DRAFT_GEMV_SPLIT='1', OWNRT_ROLLBACK_NOWAIT='1', OWNRT_TP_QSA_SPLIT='1',
                      OWNRT_TP_CARD_CONTEXT='1', OWNRT_PREFILL_LOOKUP_BATCH='1', OWNRT_PREFILL_MOE_NATIVE='1',
                      OWNRT_PREFILL_XZERO_ONCE='1', OWNRT_DRAFT_CHUNK_REPLAY='1', OWNRT_DRAFT_CHUNK_KV_ONLY='1',
                      OWNRT_TP_EXPERT_PAIR='1', OWNRT_RETIRE_DEFERRED='1', OWNRT_PREFILL_SPECIAL_ROWS='1',
                      OWNRT_PREFILL_LOOKUP_THREADS='4', OWNRT_DRAFT_CHUNK_STAGE_THREAD='1', OWNRT_DRAFT_CHUNK_GUARD_ROW='1',
                      OWNRT_DRAFT_CHUNK_ROW_COPY='1', OWNRT_HC_KERNELS='1', **TP),
    'tptsxqckhcb': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', OWNRT_DRAFT_HEAD_SPLIT='1',
                      OWNRT_SNAPSHOT_NOWAIT='1', OWNRT_DRAFT_GEMV_SPLIT='1', OWNRT_ROLLBACK_NOWAIT='1', OWNRT_TP_QSA_SPLIT='1',
                      OWNRT_TP_CARD_CONTEXT='1', OWNRT_PREFILL_LOOKUP_BATCH='1', OWNRT_PREFILL_MOE_NATIVE='1',
                      OWNRT_PREFILL_XZERO_ONCE='1', OWNRT_DRAFT_CHUNK_REPLAY='1', OWNRT_DRAFT_CHUNK_KV_ONLY='1',
                      OWNRT_TP_EXPERT_PAIR='1', OWNRT_RETIRE_DEFERRED='1', OWNRT_PREFILL_SPECIAL_ROWS='1',
                      OWNRT_PREFILL_LOOKUP_THREADS='4', OWNRT_DRAFT_CHUNK_STAGE_THREAD='1', OWNRT_DRAFT_CHUNK_GUARD_ROW='1',
                      OWNRT_DRAFT_CHUNK_ROW_COPY='1', OWNRT_DRAFT_CHUNK_BATCH='1', OWNRT_HC_KERNELS='1', **TP),
    'tptsxqckhcbx': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', OWNRT_DRAFT_HEAD_SPLIT='1',
                      OWNRT_SNAPSHOT_NOWAIT='1', OWNRT_DRAFT_GEMV_SPLIT='1', OWNRT_ROLLBACK_NOWAIT='1', OWNRT_TP_QSA_SPLIT='1',
                      OWNRT_TP_CARD_CONTEXT='1', OWNRT_PREFILL_LOOKUP_BATCH='1', OWNRT_PREFILL_MOE_NATIVE='1',
                      OWNRT_PREFILL_XZERO_ONCE='1', OWNRT_DRAFT_CHUNK_REPLAY='1', OWNRT_DRAFT_CHUNK_KV_ONLY='1',
                      OWNRT_TP_EXPERT_PAIR='1', OWNRT_RETIRE_DEFERRED='1', OWNRT_PREFILL_SPECIAL_ROWS='1',
                      OWNRT_PREFILL_LOOKUP_THREADS='4', OWNRT_DRAFT_CHUNK_STAGE_THREAD='1', OWNRT_DRAFT_CHUNK_GUARD_ROW='1',
                      OWNRT_DRAFT_CHUNK_ROW_COPY='1', OWNRT_DRAFT_CHUNK_BATCH='1', OWNRT_HC_KERNELS='1', OWNRT_PREFILL_EXPERT_PARITY='1', **TP),
    'tptsxqcp': dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', OWNRT_DRAFT_HEAD_SPLIT='1',
                     OWNRT_SNAPSHOT_NOWAIT='1', OWNRT_DRAFT_GEMV_SPLIT='1', OWNRT_ROLLBACK_NOWAIT='1', OWNRT_TP_QSA_SPLIT='1',
                     OWNRT_TP_CARD_CONTEXT='1', OWNRT_TP_PERSISTENT_THREAD='1', **TP),
}
# prefill-tp-overhead (2026-10-31): tptsxqckhcbv = tptsxqckhcb + the row-parallel batched conv (OWNRT_PREFILL_CONV_ROWS=1, build r4).
ARMS['tptsxqckhcbv'] = dict(ARMS['tptsxqckhcb'], OWNRT_PREFILL_CONV_ROWS='1')
# tptsxqckhcbg = tptsxqckhcb + the GDN state rows in registers across batched rows (OWNRT_PREFILL_GDN_REGS=1, build r5).
ARMS['tptsxqckhcbg'] = dict(ARMS['tptsxqckhcb'], OWNRT_PREFILL_GDN_REGS='1')
# prefill-balance-2026-10-31: tptsxqckhcbgl = tptsxqckhcbg + the rank-0 lookup prefetch (OWNRT_PREFILL_LOOKUP_PREFETCH=1) and
# balanced expert ownership on rank 1 (OWNRT_PREFILL_EXPERT_BALANCE=rank1).
ARMS['tptsxqckhcbgl'] = dict(ARMS['tptsxqckhcbg'], OWNRT_PREFILL_LOOKUP_PREFETCH='1', OWNRT_PREFILL_EXPERT_BALANCE='rank1')
def env(arm):
    return {**COMMON, **ARMS[arm]}
if __name__ == '__main__':
    for k, v in env(sys.argv[1]).items():
        print(f'{k}={v}')
