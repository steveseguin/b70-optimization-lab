"""Reproduce removed packet31 captures privately, using its CPU recipe at two threads.
No source under packet31 is edited. All output is in packet36/build/reference31.
"""
import hashlib,importlib.util,json,os,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;Q=P.parent/'packet31-mtp-acceptance';R=P/'build/reference31';B=R/'build'
PY='/home/steve/.venvs/vllm-xpu/bin/python'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def prepare():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 R.mkdir(parents=True,exist_ok=True);B.mkdir(exist_ok=True)
 # Packet31's harness used five CPU threads. Retain the unchanged arithmetic
 # and return its row-parallel host loops to the original two-thread setting.
 source=(Q/'prepare_target.py').read_text()
 source=source.replace('==\\\"5\\\",\\\"five numeric threads\\\"','==\\\"2\\\",\\\"two numeric threads\\\"')
 source=source.replace('.replace("num_threads(2)","num_threads(5)")','')
 source=source.replace('threads=5','threads=2')
 source=source.replace('        prepare(B/("input-"+name),','        if not (B/("input-"+name)).exists():prepare(B/("input-"+name),')
 source=source.replace('("incident-retrospective","code-review","customer-email","benchmark-analysis")','("benchmark-analysis",)')
 namespace={'__file__':str(Q/'prepare_target.py'),'__name__':'packet31_private_prepare'}
 exec(compile(source,str(Q/'prepare_target.py'),'exec'),namespace)
 namespace.update(P=R,B=B);namespace['main']()
 root=P.parents[3]
 cmd=['g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-shared','-fPIC',
      str(root/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/matmul.cpp'),'-o',str(B/'matmul.so')]
 subprocess.run(cmd,check=True,env={**os.environ,'TMPDIR':str(B)})
 save(P/'reference-reproduction-source.json',dict(passed=True,device_executed=False,source_sha256=sha(Q/'prepare_target.py'),
      adapted_sha256=hashlib.sha256(source.encode()).hexdigest(),threads=2,matmul_sha256=sha(B/'matmul.so'),
      target_binary_sha256=sha(B/'target-cpu'),scope='packet31 CPU recipe, private output directory and two numeric threads'))
def target(name):
 inp=B/('input-'+name);out=B/name;assert not out.exists()
 data=json.loads((inp/'input.json').read_text())
 env={**os.environ,'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','IQ3_MODEL_DIR':data['model_dir']}
 with (B/(name+'.log')).open('w') as log:
  subprocess.run([str(B/'target-cpu'),str(inp),str(out),'10800','64'],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
 evidence=json.loads((Q/'target-evidence.json').read_text())[name]
 observed=[json.loads(l) for l in (out/'predictions.jsonl').read_text().splitlines()]
 assert observed==evidence['predictions']
 expected=json.loads((Q/'target-gates.json').read_text())[name]['stream_hashes']
 assert all(sha(out/f)==digest for f,digest in expected.items())
 save(P/('reference-target-repeat-'+name+'.json'),dict(passed=True,device_executed=False,predictions=len(observed),stream_files=len(expected),stream_hashes=expected,binary_sha256=sha(B/'target-cpu')))
def reference(name):
 sys.path.insert(0,str(Q));import draft_reference as ref
 import torch
 torch.set_num_threads(1);torch.set_num_interop_threads(1);ref.P=R
 data=json.loads((P/'build'/('captured-'+name)/'input.json').read_text());n=len(data['tokens'])
 targetrows=json.loads((P/'build'/('captured-'+name)/'target-rows.json').read_text())
 records=[r for r in json.loads((Q/'acceptance.json').read_text())['positions'] if r['prompt']==name]
 assert len(records)==64
 store=ref.SafeStore();bindings=ref.Bindings(store)
 models={'mtp_fp8_iq3':ref.Draft(store),'mtp_int8_iq3':ref.Draft(store,True)}
 dest=B/name;dest.mkdir(exist_ok=True)
 with torch.inference_mode():
  for j in range(n+63):
   raw=(P/'build'/('captured-'+name)/f'streams-{j}.bf16').read_bytes()
   streams=torch.frombuffer(bytearray(raw),dtype=ref.BF).reshape(1,4,2560)
   token=targetrows[j+1]['input_token'];idx=j-(n-2)
   for variant,model in models.items():
    sample=model(streams,bindings.embedding(token),j)
    if 0<=idx<64:
     blob=sample.contiguous().view(torch.uint8).numpy().tobytes()
     assert hashlib.sha256(blob).hexdigest()==records[idx]['sources'][variant]['sample_bf16_sha256']
     (dest/f'sample-{idx}-{variant}.bf16').write_bytes(blob)
 (B/(name+'-draft.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in records))
 save(P/('reference-sample-repeat-'+name+'.json'),dict(passed=True,device_executed=False,sample_files=128,exact_packet31_sample_hashes=True,acceptance_sha256=sha(Q/'acceptance.json')))
 bindings.iq.close()
if __name__=='__main__':
 stage=sys.argv[1]
 if stage=='prepare':prepare()
 elif stage=='target':target(sys.argv[2])
 elif stage=='prepare-input':
  sys.path.insert(0,str(P.parent/'packet13-integrate'));from prepare import prepare as make_input
  destination=B/('input-'+sys.argv[2])
  if not destination.exists():make_input(destination,P.parents[3]/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle/prompts'/(sys.argv[2]+'.txt'))
  data=json.loads((destination/'input.json').read_text())
  expected=json.loads((Q/'target-evidence.json').read_text())[sys.argv[2]]['input']
  assert data['tokens']==expected['tokens']
  assert all(sha(destination/name)==digest for name,digest in data['files'].items())
 elif stage=='inputs':
  sys.path.insert(0,str(P));from capture_cpu import prepare as capture_inputs
  capture_inputs(sys.argv[2])
 elif stage=='reference':reference(sys.argv[2])
 else:raise ValueError(stage)
