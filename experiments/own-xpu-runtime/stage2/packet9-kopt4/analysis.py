#!/usr/bin/env python3
"""CPU-only census corrections and explicitly unmeasured throughput scenarios."""
import json
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'tests'))
from common import plan, save, sha

def calculate():
    p=plan();receipt=HERE.parent/'packet8-kopt3/receipts-card3-20261011/timing.json'
    old=json.loads(receipt.read_text())
    groups=next(l for l in old['layers'] if l['phase']=='groups')['summary']['fused']
    previous={r['kind']:r['fused']['median_ms'] for r in groups if r['variant']=='decode_const_sg32_v1'}
    scenarios=[]
    for l in p['layers'][:4]:
        packed=l['expert_active_bytes']
        scenarios.append(dict(layer=l['layer'],kind=l['kind'],packed_bytes=packed,work_groups=l['expert_groups'],
            predicted_ms_range=[packed/(rate*1e6)+3*.017 for rate in (160,100)],
            assumptions='100–160 GB/s payload rate plus three conservative 17 us issue floors; hypothesis, not fitted or measured',
            bandwidth_only_590_floor_ms=packed/(590*1e6),native_layer_launches=l['native_launches']))
    return dict(schema='own-runtime.iq3.packet9.analysis.v1',measured=False,round3_receipt_sha256=sha(receipt),
        corrections=dict(total_layers=48,gdn_layers=36,qsa_layers=12,selected_expert_bytes_per_token=949760000,
            ordinary_block_bytes=19712000,gate_up_each_bytes=5248000,down_bytes=9216000,
            gate_up='IQ2_S, rows=640, K=2560',down='IQ4_NL, rows=2560, K=640',
            round3_grouped_results_present=True,round3_constant_fused_stage_ms=previous),
        scenarios=scenarios,reference_tok_s=28.49,reference_ms=1000/28.49,
        total_payload_bytes=4951240940,bandwidth_590_floor_ms=4951240940/590e6,
        bandwidth_590_ceiling_tok_s=590e9/4951240940,
        scope='CPU preparation only; no device execution or full-model quality claim')

if __name__=='__main__':
    d=calculate();save(HERE/'analysis.json',d)
    print('unmeasured expert hypotheses:',[r['predicted_ms_range'] for r in d['scenarios']])
