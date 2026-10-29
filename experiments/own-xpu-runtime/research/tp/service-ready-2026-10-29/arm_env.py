#!/usr/bin/env python3
"""Environment of each arm of research/tp/service-ready-2026-10-29. Prints KEY=VALUE lines for `arm_env.py ARM`.

All arms: the B19 service flags (unit at commit eb61e0d71: F32, split 23, context 65536, QSA raw ring, shadow packing,
256-row batched prefill) without sessions/keeper/continuation, OWNRT_NO_DRAFT_TIMING=1 (as the e2e suite's arm B; TP
cannot time the draft), and the multi-card launch keys NEOReadDebugKeys=1 EnableDeferBacking=0. The engine receipt
comes from SC117_ENGINE_RECEIPT in the caller's environment.
  two   two cards: rank 0 on 23:00.0, rank 1 on 47:00.0 (the control).
  tp    four cards: rank 0 on 23:00.0+27:00.0, rank 1 on 43:00.0+47:00.0, exact TP (Stage 2b layout).
Overrides: ARM_CONTEXT, ARM_PREFILL_ROWS (CPU plan probes only)."""
import os, sys
E = '/home/steve/llm-optimizations/experiments/own-xpu-runtime'
COMMON = dict(
    SC117_ACTIVATIONS='f32', SC117_CONTEXT=os.environ.get('ARM_CONTEXT', '65536'), SC117_ADAPTER='adapter6_tp.py',
    SC117_ENGINE_RECEIPT=os.environ.get('SC117_ENGINE_RECEIPT', f'{E}/engine/receipts/16ed1ff1a203.json'),
    SC117_PREFILL_ROWS=os.environ.get('ARM_PREFILL_ROWS', '256'),
    SC117_DISPATCH=f'{E}/gsq-rco-iq3s/serving/lan/dispatch-f32-select-gdn2.json', SC117_TARGET_SPLIT='23',
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
}
def env(arm):
    return {**COMMON, **ARMS[arm]}
if __name__ == '__main__':
    for k, v in env(sys.argv[1]).items():
        print(f'{k}={v}')
