"""One authorized ON model case; no retry, rebuild, or baseline re-execution."""
from pathlib import Path
import json,hashlib,subprocess,os,time,struct,math,shutil
R=Path('/dev/shm/sc117-l4-observer-model-20261028-r1')
assert not R.exists();R.mkdir()
O=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/pp4-review-2026-10-28/reference-one-row/l4-localization')
build=json.loads((O/'build-result.json').read_text())
B=Path(build['binary']);assert hashlib.sha256(B.read_bytes()).hexdigest()==build['binary_sha256']
for p,h in build['compiled_sources'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
assert hashlib.sha256((O/'l4-capture.hpp').read_bytes()).hexdigest()==build['observer_header_sha256']
mem={k:int(v.split()[0])*1024 for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())}
assert mem['MemAvailable']>=80*1024**3,'RAM floor before model launch'
D=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/pp4-review-2026-10-28/reference-one-row')
pins=json.loads((D/'capture-source-identity.json').read_text())
for group in ('static_library_sha256','source_hashes'):
 for p,h in pins[group].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
baseline=D/'cpu-r1/original/logits-243.f32';assert hashlib.sha256(baseline.read_bytes()).hexdigest()=='9dae567c488c22e87c3212d8d408d0a0dd42fad62b666768caa3d06fc39a01d4'
out=R/'on';out.mkdir()
env=os.environ.copy()
for k in ('GGML_CPU_EXACT_ACC','GGML_CPU_EXACT_ROPE','GGML_CPU_EXACT_ROUND'):env.pop(k,None)
env.update(GGML_CPU_EXACT_F64='1',EXACT_KV='f32',OMP_NUM_THREADS='8',EXACT_CAPTURE_L4='1')
cmd=['nice','-n','19','taskset','-c','8-15',str(B),'/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf',str(D/'input.json'),str(out),'8']
rec=dict(argv=cmd,binary_sha256=hashlib.sha256(B.read_bytes()).hexdigest(),source_sha256=hashlib.sha256((O/'exact-logits-l4.cpp').read_bytes()).hexdigest(),environment={k:v for k,v in env.items() if k.startswith(('GGML_CPU_EXACT','EXACT_','OMP_'))},started=time.time())
(R/'run.json').write_text(json.dumps(rec,indent=2)+'\n');print('START one L4 ON',flush=True)
with (out/'log.txt').open('w') as log:rc=subprocess.call(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
rec.update(returncode=rc,finished=time.time());(R/'run.json').write_text(json.dumps(rec,indent=2)+'\n');print('END',rc,flush=True)
assert rc==0,'model/capture failed; no comparison'
actual=out/'logits-243.f32';assert actual.read_bytes()==baseline.read_bytes(),'ON full logits differ; no router comparison'
layouts=[json.loads(line) for line in (out/'layouts.jsonl').read_text().splitlines()]
assert len(layouts)==23 and len({x['name'] for x in layouts})==23
assert len(list(out.glob('*.f32')))==24 # 23captures plus full logits
hashes={}
for item in layouts:
 path=out/(item['name']+'.f32');data=path.read_bytes();assert len(data)==item['bytes']
 values=struct.unpack('<'+str(len(data)//4)+'f',data);assert all(math.isfinite(x) for x in values)
 hashes[path.name]=hashlib.sha256(data).hexdigest()
for name in ['q_conv_predelta-4','k_conv_predelta-4','v_conv_predelta-4','beta_sigmoid-4','gate-4','state_predelta-4','conv_state_at-4']:
 item=next(x for x in layouts if x['name']==name);assert item['full']
result=dict(passed_full_logit_neutrality=True,logits_sha256=hashlib.sha256(actual.read_bytes()).hexdigest(),capture_hashes=hashes,scope='L4 selected row243 plus whole244 recurrent inputs and initial pre-whole-batch state; not a pre-row243 state claim.')
(R/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS original/OFF full-logit equality and23 L4 capture extents',flush=True)
