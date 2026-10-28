"""One authorized ON model case; no retry, rebuild, or baseline re-execution."""
from pathlib import Path
import json,hashlib,subprocess,os,time,struct,math,shutil
R=Path('/dev/shm/sc117-reference-norm-cpu-20261028-r1')
D=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/pp4-review-2026-10-28/reference-one-row')
pins=json.loads((D/'capture-source-identity.json').read_text())
for group in ('static_library_sha256','source_hashes'):
 for p,h in pins[group].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
baseline=D/'cpu-r1/original/logits-243.f32';assert hashlib.sha256(baseline.read_bytes()).hexdigest()=='9dae567c488c22e87c3212d8d408d0a0dd42fad62b666768caa3d06fc39a01d4'
out=R/'on';out.mkdir()
env=os.environ.copy()
for k in ('GGML_CPU_EXACT_ACC','GGML_CPU_EXACT_ROPE','GGML_CPU_EXACT_ROUND'):env.pop(k,None)
env.update(GGML_CPU_EXACT_F64='1',EXACT_KV='f32',OMP_NUM_THREADS='8',EXACT_CAPTURE_NORM='1')
cmd=['nice','-n','19','taskset','-c','8-15',str(R/'exact-logits-norm'),'/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf',str(D/'input.json'),str(out),'8']
rec=dict(argv=cmd,binary_sha256=hashlib.sha256((R/'exact-logits-norm').read_bytes()).hexdigest(),source_sha256=hashlib.sha256((D/'exact-logits-norm.cpp').read_bytes()).hexdigest(),environment={k:v for k,v in env.items() if k.startswith(('GGML_CPU_EXACT','EXACT_','OMP_'))},started=time.time())
(R/'run.json').write_text(json.dumps(rec,indent=2)+'\n');print('START one norm ON',flush=True)
with (out/'log.txt').open('w') as log:rc=subprocess.call(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
rec.update(returncode=rc,finished=time.time());(R/'run.json').write_text(json.dumps(rec,indent=2)+'\n');print('END',rc,flush=True)
assert rc==0,'model/capture failed; no comparison'
actual=out/'logits-243.f32';assert actual.read_bytes()==baseline.read_bytes(),'ON full logits differ; no layer comparison'

for name in ('input','gain','output'):
 p=out/f'hc-a-{name}.f32';assert p.stat().st_size==40960
meta=json.loads((out/'norm-capture.json').read_text());assert meta['position']==243 and meta['occurrence']==1
result=dict(passed_observer_gate=True,logits_sha256=hashlib.sha256(actual.read_bytes()).hexdigest(),arrays={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('hc-a-*.f32')},scope='Captured same-input HC attention norm arrays only; no arithmetic cause established.')
(R/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS full logits and three norm arrays',flush=True)
