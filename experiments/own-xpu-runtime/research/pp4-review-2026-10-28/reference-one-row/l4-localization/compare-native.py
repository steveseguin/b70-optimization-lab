"""Bounded post-completion array comparison. Run ONLY after root clean capture confirmation."""
from pathlib import Path
import json,hashlib,struct,math
HERE=Path(__file__).resolve().parent
CPU=Path('/dev/shm/sc117-l4-observer-model-20261028-r1')
NATIVE=Path('/dev/shm/sc117-l4-target244-20261028-r1/output')
OUT=HERE/'native-comparison-r1.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert json.loads((CPU/'comparison.json').read_text())['passed_full_logit_neutrality']
assert not OUT.exists()
root=NATIVE/'l4-captures/layer4';record=json.loads((root/'extraction.json').read_text());assert record['full_seal_verified']
for name,h in record['selected'].items():assert sha(root/name)==h
pairs=[('hc.a.norm','hc_norm-4-1'),('hc.a.mix','hc_mixed-4-1'),('gdn.qkv','linear_attn_qkv_mixed-4'),('gdn.z','z-4'),('gdn.a','alpha-4'),('gdn.b','beta-4'),('gdn.conv','conv_output_silu-4'),('gdn.y','recurrent-output'),('gdn.gated','final_output-4'),('attention','linear_attn_out-4'),('hc.f.norm','hc_norm-4-2'),('hc.f.mix','hc_mixed-4-2')]
rows=[]
for field,cpu in pairs:
 a=root/f'blk.4.{field}.bin';b=CPU/'on'/(cpu+'.f32');ab=a.read_bytes();bb=b.read_bytes();assert len(ab)==len(bb) and len(ab)%4==0
 av=struct.unpack('<'+str(len(ab)//4)+'f',ab);bv=struct.unpack('<'+str(len(bb)//4)+'f',bb);assert all(math.isfinite(x) for x in av+bv)
 diffs=[abs(x-y) for x,y in zip(av,bv)]
 rows.append(dict(native=field,cpu=cpu,bytes=len(ab),bitwise_equal=ab==bb,unequal_floats=sum(x!=y for x,y in zip(av,bv)),max_abs=max(diffs),rms=math.sqrt(sum(x*x for x in diffs)/len(diffs)),native_rms=math.sqrt(sum(x*x for x in av)/len(av)),cpu_rms=math.sqrt(sum(x*x for x in bv)/len(bv)),native_sha256=sha(a),cpu_sha256=sha(b)))
result=dict(scope='Different actual input/history paths, committed row243. Boundary localization only; no causal same-input arithmetic conclusion. Initial CPU state is not compared with post-row native state.',native_result_token=json.loads((NATIVE/'result.json').read_text())['tokens'],cpu_neutral_logits_sha256=sha(CPU/'on/logits-243.f32'),rows=rows,native_bundle_seal=record['source_bundle_sha256'])
OUT.write_text(json.dumps(result,indent=2)+'\n')
for x in rows:print(x['native'], 'rms',x['rms'],'max',x['max_abs'])
