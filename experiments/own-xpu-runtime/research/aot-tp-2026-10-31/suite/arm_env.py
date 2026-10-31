#!/usr/bin/env python3
"""Environment of each arm of research/aot-tp-2026-10-31/suite. Prints KEY=VALUE lines for `arm_env.py ARM`.
COMMON is copied unchanged from research/two-card-flags-2026-10-31/suite/arm_env.py (= hc-split-2026-10-30's): the B19
service flags (F32, split 23, context 65536, QSA raw ring, shadow packing, 256-row batched prefill) without
sessions/keeper/continuation, OWNRT_NO_DRAFT_TIMING=1, NEOReadDebugKeys=1 EnableDeferBacking=0. The engine receipt (the
binary) comes from SC117_ENGINE_RECEIPT in the caller's environment; the arm name only fixes the flags and which binary
run_arm_suite.sh admits (`arm_env.py ARM --binary` prints jit or aot).
  hspJ / hspA     four cards (rank 0 on 23:00.0+27:00.0, rank 1 on 43:00.0+47:00.0): hc-split-2026-10-30's arm hsp (fc2 +
                  OWNRT_TP_HC_SPLIT=low,gate,final,prefill), copied verbatim; J = JIT r1, A = AOT. Both pass
                  SC117_LAB_WAIT_SECONDS=300 (the ranks' --wait-seconds), so the A/B differs only in the binary.
  twoBJ / twoBA   two cards (rank 0 on 23:00.0, rank 1 on 47:00.0): two-card-flags-2026-10-31's arm twoB (the B19 flags +
                  research/two-card-flags-2026-10-31/flags.py B, forwarded to one-card ranks by the adapter's ONE_CARD_KEYS
                  fix, lab/adapter6_tp.py); wait 300 s as above.
  hspA60          hspA without SC117_LAB_WAIT_SECONDS: the ranks keep the default 60 s --wait-seconds."""
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
HSP = dict(SC117_RANK_BDFS='0000:23:00.0+0000:27:00.0,0000:43:00.0+0000:47:00.0', OWNRT_TARGET_HEAD_SPLIT='1', OWNRT_DRAFT_HEAD_SPLIT='1',
                OWNRT_SNAPSHOT_NOWAIT='1', OWNRT_DRAFT_GEMV_SPLIT='1', OWNRT_ROLLBACK_NOWAIT='1', OWNRT_TP_QSA_SPLIT='1',
                OWNRT_TP_CARD_CONTEXT='1', OWNRT_PREFILL_LOOKUP_BATCH='1', OWNRT_PREFILL_MOE_NATIVE='1',
                OWNRT_PREFILL_XZERO_ONCE='1', OWNRT_DRAFT_CHUNK_REPLAY='1', OWNRT_DRAFT_CHUNK_KV_ONLY='1',
                OWNRT_TP_EXPERT_PAIR='1', OWNRT_RETIRE_DEFERRED='1', OWNRT_PREFILL_SPECIAL_ROWS='1',
                OWNRT_PREFILL_LOOKUP_THREADS='4', OWNRT_DRAFT_CHUNK_STAGE_THREAD='1', OWNRT_DRAFT_CHUNK_GUARD_ROW='1',
                OWNRT_DRAFT_CHUNK_ROW_COPY='1', OWNRT_DRAFT_CHUNK_BATCH='1', OWNRT_HC_KERNELS='1',
                OWNRT_DRAFT_FAST='1', OWNRT_TARGET_FAST='1', OWNRT_TP_HC_SPLIT='low,gate,final,prefill', **TP)
sys.dont_write_bytecode = True  # never write a __pycache__ into the two-card-flags folder
sys.path.insert(0, f'{E}/research/two-card-flags-2026-10-31')  # flags.py B, read in place
from flags import B as TWOCARD_B
TWOB = dict(SC117_RANK_BDFS='0000:23:00.0,0000:47:00.0', **TWOCARD_B)
W300 = dict(SC117_LAB_WAIT_SECONDS='300')
ARMS = {'hspJ': (dict(HSP, **W300), 'jit'), 'hspA': (dict(HSP, **W300), 'aot'), 'hspA60': (dict(HSP), 'aot'),
        'twoBJ': (dict(TWOB, **W300), 'jit'), 'twoBA': (dict(TWOB, **W300), 'aot')}
def env(arm):
    return {**COMMON, **ARMS[arm][0]}
if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[2] == '--binary':
        print(ARMS[sys.argv[1]][1]); sys.exit(0)
    for k, v in env(sys.argv[1]).items():
        print(f'{k}={v}')
