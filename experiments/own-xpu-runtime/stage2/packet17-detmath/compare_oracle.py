"""CPU-only final coverage and informational v1/v2 comparison, never a quality waiver."""
import hashlib,json,math,struct
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
RUNS=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs'
V1=RUNS/'arithmetic-v1-parallel-20261011/incident-retrospective'
V2=RUNS/'arithmetic-v2-detmath-20261011/incident-retrospective'
def rows(p):return [json.loads(x) for x in (p/'tokens.jsonl').read_text().splitlines()]
a,b=rows(V1),rows(V2)
assert len(a)==len(b)==64,'require64completedtokens'
result=json.loads((V2/'result.json').read_text())
assert result['status']=='token-cap' and result['arithmetic']=='iq3-p17-detmath-v2'
assert len(json.loads((V2/'input.json').read_text())['tokens'])==87
assert len((V2/'positions.jsonl').read_text().splitlines())==150
assert json.loads((V2/'input.json').read_text())['tokens']==json.loads((V1/'input.json').read_text())['tokens']
layers=[]
for step in range(1,9):
 assert len(list((V2/f'step{step}').glob('layer-*.bf16')))==48
 for layer in range(48):
  name=f'step{step}/layer-{layer:02d}.bf16';x=(V1/name).read_bytes();y=(V2/name).read_bytes();assert len(x)==len(y)==20480
  ux=struct.unpack('<10240H',x);uy=struct.unpack('<10240H',y)
  fx=[struct.unpack('<f',struct.pack('<I',u<<16))[0] for u in ux];fy=[struct.unpack('<f',struct.pack('<I',u<<16))[0] for u in uy]
  squares=sum((i-j)**2 for i,j in zip(fx,fy));base=sum(i*i for i in fx)
  layers.append(dict(step=step,layer=layer,differing_bytes=sum(i!=j for i,j in zip(x,y)),differing_bf16=sum(i!=j for i,j in zip(ux,uy)),max_abs=max(abs(i-j) for i,j in zip(fx,fy)),relative_rms=math.sqrt(squares/base) if base else None,v1_sha256=hashlib.sha256(x).hexdigest(),v2_sha256=hashlib.sha256(y).hexdigest()))
comparison=dict(schema='packet17.oracle-comparison.v2',device_executed=False,coverage_passed=True,prompt_tokens=87,generated_tokens=64,fixture_steps=8,layers_per_step=48,tokens_equal=sum(x['token_id']==y['token_id'] for x,y in zip(a,b)),first_token_difference=next((i+1 for i,(x,y) in enumerate(zip(a,b)) if x['token_id']!=y['token_id']),None),v1_tokens=[r['token_id'] for r in a],v2_tokens=[r['token_id'] for r in b],all_logit_hashes_equal=all(x['logits_bf16_sha256']==y['logits_bf16_sha256'] for x,y in zip(a,b)),tokens=[dict(step=i+1,v1=x,v2=y) for i,(x,y) in enumerate(zip(a,b))],layers=layers)
(P/'oracle-comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
text='# V1 versus v2 CPU hidden states\n\nDifferences are informational for the new identity; all values compare the same prompt and steps before any token divergence.\n\n| Step | Layer | BF16 differences /10240 | Byte differences | Maximum absolute | Relative RMS |\n| ---: | ---: | ---: | ---: | ---: | ---: |\n'
for r in layers:text+=f"| {r['step']} | {r['layer']} | {r['differing_bf16']} | {r['differing_bytes']} | {r['max_abs']:.8g} | {r['relative_rms']:.8g} |\n"
(P/'oracle-layer-comparison.md').write_text(text)
print(json.dumps({k:v for k,v in comparison.items() if k not in ('layers','tokens','v1_tokens','v2_tokens')}))
