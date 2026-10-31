#!/usr/bin/env python3
"""Environment of each arm of research/two-card-flags-2026-10-31/suite. Prints KEY=VALUE lines for `arm_env.py ARM`.
Copy of research/tp/hc-split-2026-10-30/suite/arm_env.py, two-card arms only. COMMON is unchanged: the B19 service flags
(unit at commit eb61e0d71: F32, split 23, context 65536, QSA raw ring, shadow packing, 256-row batched prefill) without
sessions/keeper/continuation, OWNRT_NO_DRAFT_TIMING=1 (as every lab arm since the e2e suite, including the two-card
control arm "two" of target-head-split-2026-10-29, 66.42 tok/s), and NEOReadDebugKeys=1 EnableDeferBacking=0. The engine
receipt comes from SC117_ENGINE_RECEIPT in the caller's environment.
  twoA  two cards, rank 0 on 23:00.0, rank 1 on 47:00.0: the "two" arm (B19-equivalent; every new flag off).
  twoB  twoA + every key of ../flags.py B (the non-TP flags of the four-card stack), passed to both ranks by this
        folder's lab adapter (lab/adapter6_tp.py ONE_CARD_KEYS)."""
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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flags import B as NEW
TWO = dict(SC117_RANK_BDFS='0000:23:00.0,0000:47:00.0')
ARMS = {'twoA': dict(TWO), 'twoB': dict(TWO, **NEW)}
def env(arm):
    return {**COMMON, **ARMS[arm]}
if __name__ == '__main__':
    for k, v in env(sys.argv[1]).items():
        print(f'{k}={v}')
