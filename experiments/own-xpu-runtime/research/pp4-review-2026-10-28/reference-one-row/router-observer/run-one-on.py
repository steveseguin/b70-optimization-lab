"""One authorized ON model case; no retry, rebuild, or baseline re-execution."""
from pathlib import Path
import json,hashlib,subprocess,os,time,struct,math,shutil
R=Path('/dev/shm/sc117-router-observer-model-20261028-r1')
assert not R.exists();R.mkdir()
O=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/pp4-review-2026-10-28/reference-one-row/router-observer')
build=json.loads((O/'build-result.json').read_text())
B=Path(build['binary']);assert hashlib.sha256(B.read_bytes()).hexdigest()==build['binary_sha256']
for p,h in build['compiled_sources'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
assert hashlib.sha256((O/'router-capture.hpp').read_bytes()).hexdigest()==build['observer_header_sha256']
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
env.update(GGML_CPU_EXACT_F64='1',EXACT_KV='f32',OMP_NUM_THREADS='8',EXACT_CAPTURE_ROUTERS='1')
cmd=['nice','-n','19','taskset','-c','8-15',str(B),'/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf',str(D/'input.json'),str(out),'8']
rec=dict(argv=cmd,binary_sha256=hashlib.sha256(B.read_bytes()).hexdigest(),source_sha256=hashlib.sha256((O/'exact-logits-router.cpp').read_bytes()).hexdigest(),environment={k:v for k,v in env.items() if k.startswith(('GGML_CPU_EXACT','EXACT_','OMP_'))},started=time.time())
(R/'run.json').write_text(json.dumps(rec,indent=2)+'\n');print('START one router ON',flush=True)
with (out/'log.txt').open('w') as log:rc=subprocess.call(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
rec.update(returncode=rc,finished=time.time());(R/'run.json').write_text(json.dumps(rec,indent=2)+'\n');print('END',rc,flush=True)
assert rc==0,'model/capture failed; no comparison'
actual=out/'logits-243.f32';assert actual.read_bytes()==baseline.read_bytes(),'ON full logits differ; no router comparison'
files=list(out.glob('layer-*'));assert len(files)==240
hashes={}
for layer in range(48):
 for field,count,kind in [('input',2560,'f'),('logits',512,'f'),('probabilities',512,'f'),('ids',10,'i'),('weights',10,'f')]:
  path=out/f'layer-{layer:02d}-{field}.{"i32" if kind=="i" else "f32"}'
  data=path.read_bytes();assert len(data)==count*4
  values=struct.unpack('<'+str(count)+kind,data)
  assert all(0<=x<512 for x in values) if kind=='i' else all(math.isfinite(x) for x in values)
  hashes[path.name]=hashlib.sha256(data).hexdigest()
layouts=[json.loads(line) for line in (out/'router-layouts.jsonl').read_text().splitlines()]
assert len(layouts)==240
result=dict(passed_full_logit_neutrality=True,logits_sha256=hashlib.sha256(actual.read_bytes()).hexdigest(),capture_hashes=hashes,scope='All48 committed-row router chains. Earlier token history not captured; no causal quality conclusion.')
(R/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS original/OFF full-logit equality and240 capture extents',flush=True)
