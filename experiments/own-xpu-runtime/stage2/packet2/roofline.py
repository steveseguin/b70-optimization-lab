"""Stored-byte bandwidth floors, not measured or forecast kernel latency."""
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
CENSUS=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json'

def calculate():
    c=json.loads(CENSUS.read_text());layers=[];rows=set()
    for t in c['tensors']:
        if len(t['dimensions'])>=2:
            k=t['dimensions'][0];row_count=1
            for n in t['dimensions'][1:]:row_count*=n
            rows.add((t['type'],k,t['bytes']//row_count,t['component']))
    for layer in range(48):
        selected=[t for t in c['tensors'] if t['layer']==layer and t['component'] not in ('embedding','ple_lookup')]
        experts=sum(t['bytes']//512*10 for t in selected if t['component']=='routed_experts')
        dense=sum(t['bytes'] for t in selected if t['component']!='routed_experts')
        total=dense+experts
        layers.append(dict(layer=layer,dense_bytes=dense,top10_expert_bytes=experts,packed_active_bytes=total,bandwidth_floor_ms={str(rate):total/(rate*1e9)*1000 for rate in (507,537)}))
    return dict(schema='own-runtime.iq3.packet2.bandwidth-floor.v1',measured=False,census_sha256=hashlib.sha256(CENSUS.read_bytes()).hexdigest(),definition='sum of layer stored dense bytes + ten of 512 experts; one logical HC copy',excluded=['extra HC replica traffic','activation traffic','KV/state','routing','dequantization/compute','launches','host lookup IO','collectives'],layers=layers,rows=[dict(type=t,columns=k,packed_bytes_per_row=b,component=comp) for t,k,b,comp in sorted(rows)])
if __name__=='__main__':
    (HERE/'roofline.json').write_text(json.dumps(calculate(),indent=2,sort_keys=True)+'\n')
