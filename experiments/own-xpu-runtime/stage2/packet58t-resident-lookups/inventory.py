"""Metadata/source-only census of the prepared one-card host file reads."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    census=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json'
    tensors=json.loads(census.read_text())['tensors']
    rows=[]
    for t in tensors:
        if t['component'] not in ('embedding','ple_lookup'):continue
        count=1 if t['component']=='embedding' else 16
        rows.append(dict(t,rows_per_token=count,row_bytes=t['bytes']//t['shape'][0],
            packed_bytes_per_token=count*t['bytes']//t['shape'][0],bf16_output_bytes_per_token=count*t['shape'][1]*2,
            access='token ID' if count==1 else 'two history hashes, eight head vocabularies each; 16 scattered rows'))
    total=sum(r['bytes'] for r in rows);assert total==29_321_610_240
    sources=[census,P.parent/'packet58j-onecard-port/main.cpp',P.parent/'packet2/loader/gguf.cpp',P.parent/'packet2/kernels/math.hpp',P.parent/'packet58q-onecard-variance/ANALYSIS.md',P.parent/'packet58p-onecard-record/parent-build-device-receipt.json']
    row=dict(passed=True,device_executed=False,model_payload_reads=False,tensors=rows,
        resident_bytes=total,packed_bytes_per_token=sum(r['packed_bytes_per_token'] for r in rows),
        bf16_output_bytes_per_token=sum(r['bf16_output_bytes_per_token'] for r in rows),
        ple_metadata_bytes=35*8,host_id_bytes=4+16*8,scale_bytes_per_token=10*(16+2)+16*5*2,
        production_and_tile16_same_lookup_path=True,lookup_sidecars=False,
        expert_pinned_bytes=48_627_712_000,
        sources={str(f.relative_to(ROOT)):sha(f) for f in sources})
    (P/'evidence/lookup-inventory.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps({k:row[k] for k in ('resident_bytes','packed_bytes_per_token','bf16_output_bytes_per_token')}))
if __name__=='__main__':main()
