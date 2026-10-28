import os,subprocess,pathlib,json,hashlib,time
r=pathlib.Path('/dev/shm/sc117-reference-capture-cpu-20261028-r1');D=pathlib.Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/pp4-review-2026-10-28/reference-one-row')
model='/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf'
env=os.environ.copy()
for k in ('GGML_CPU_EXACT_ACC','GGML_CPU_EXACT_ROPE','GGML_CPU_EXACT_ROUND','EXACT_CAPTURE_LAYERS'):env.pop(k,None)
env.update(GGML_CPU_EXACT_F64='1',EXACT_KV='f32',OMP_NUM_THREADS='8')
records=[]
for label,binary,on in [('original','/dev/shm/llref/build/exact-logits',False),('off',str(r/'exact-logits-capture'),False),('on',str(r/'exact-logits-capture'),True)]:
 out=r/label;out.mkdir();e=env.copy();e['EXACT_CAPTURE_LAYERS']='1' if on else '0';cmd=['nice','-n','19','taskset','-c','8-15',binary,model,str(D/'input.json'),str(out),'8']
 rec=dict(label=label,argv=cmd,binary_sha256=hashlib.sha256(pathlib.Path(binary).read_bytes()).hexdigest(),environment={k:v for k,v in e.items() if k.startswith(('GGML_CPU_EXACT','EXACT_','OMP_'))},started=time.time());print('START',label,flush=True)
 with (out/'log.txt').open('w') as log:rc=subprocess.call(cmd,env=e,stdout=log,stderr=subprocess.STDOUT)
 rec.update(returncode=rc,finished=time.time());records.append(rec);(r/'runs.json').write_text(json.dumps(records,indent=2)+'\n');print('END',label,rc,flush=True)
 if rc:raise SystemExit(rc)
 if label!='original':
  a=(r/'original/logits-243.f32').read_bytes();b=(out/'logits-243.f32').read_bytes();assert len(a)==248320*4;assert a==b,'full logits differ original versus '+label
print('PASS original/OFF/ON full logits bitwise identical',flush=True)
