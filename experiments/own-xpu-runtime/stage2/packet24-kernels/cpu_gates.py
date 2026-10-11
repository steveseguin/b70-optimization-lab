"""Bounded CPU gates; no device executable is ever invoked."""
import argparse,hashlib,json,os,subprocess,time,resource
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build';PY='/home/steve/.venvs/vllm-xpu/bin/python'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def read(p):return json.loads(p.read_text())
def run(cmd,log,env=None):
 with (P/log).open('w') as f:r=subprocess.run(list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT,env=env)
 assert r.returncode==0,(cmd,log,r.returncode)
def host(binary):
 elf=subprocess.check_output(['readelf','-d',str(binary)],text=True).lower();assert not any(x in elf for x in ['libsycl','libze_loader','libur_loader','libopencl'])
def main():
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['cheap','sanitizer']);a=parser.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 host(B/'host/own-rt-iq3')
 if a.mode=='cheap':
  resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,resource.RLIM_INFINITY))
  units={}
  for name in ['authority-tests','owner-retirement-tests','chain-tests','queue-tests','lifetime-tests']:
   binary=B/'host'/name;host(binary);units[name]=subprocess.check_output([str(binary)],text=True)
  save('unit-tests.json',dict(passed=True,device_executed=False,units=units))
  failures=[]
  for mode in ['jit','borrower','parameters']:
   out=B/('failure-'+mode+'-'+str(time.time_ns()));cmd=[B/'host/failure-tests',mode,out]
   r=subprocess.run(list(map(str,cmd)),capture_output=True,text=True);assert r.returncode==(0 if mode=='parameters' else 1)
   failures.append(dict(mode=mode,returncode=r.returncode,stderr=r.stderr))
  save('failure-tests.json',dict(passed=True,cases=2,parameter_cache_event_order_controls=1,rows=failures,device_executed=False))
  cases=[]
  for kernels in ['v1','v2']:
   for fusion in ['on','off']:
    for timing in ['token','drain','launch']:
     for ng in ['core','parallel']:
      name=f'{kernels}-{fusion}-{timing}-{ng}';out=B/('integration-'+name+'-'+str(time.time_ns()));receipt=P/('cpu-'+name+'.json')
      env=dict(os.environ,PACKET24_KERNELS=kernels,PACKET21_FUSION=fusion,PACKET23_TIMING=timing)
      run([PY,'-B',P/'test.py','--binary',B/'host/own-rt-iq3','--scratch',out,'--input',B/'input','--receipt',receipt,'--nongemv',ng],'integration-current.log',env)
      r=read(receipt);assert r['passed'];cases.append(dict(kernels=kernels,fusion=fusion,timing=timing,nongemv=ng,receipt=receipt.name,cases=len(r['tests']),sha256=sha(receipt)))
      print(name,'PASS',flush=True)
  save('integration-gates.json',dict(passed=True,device_executed=False,binary_sha256=sha(B/'host/own-rt-iq3'),rows=cases,cases=sum(x['cases'] for x in cases)))
  run([B/'host/k2-fixtures','--validate-only','--input',B/'k2-input','--output',B/'k2-manifest-final'],'k2-manifest.log')
  run([PY,'-B',P/'test_mismatch.py'],'mismatch-tests.log')
 else:
  binary=B/'asan/own-rt-iq3';host(binary);rows=[];baselines={}
  for kernels in ['v1','v2']:
   for ng in ['core','parallel']:
    for cards in [1,2]:
     for seed in [0,1,17,73]:
      out=B/f'asan-{kernels}-{ng}-{cards}-{seed}-{time.time_ns()}'
      env=dict(os.environ,PACKET24_ORDER_SEED=str(seed),ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
      cmd=[binary,'--mini','--card','0','--kernels',kernels,'--nongemv',ng,'--cards',str(cards),'--memory','resident' if cards==2 else 'layer-streaming','--max-new','3','--output',out]
      run(cmd,'asan-current.log',env);r=read(out/'receipt.json');assert r['passed'] and not r['device_executed']
      identity=[r['tokens'],sha(out/'buffers.json')]
      baseline=baselines.setdefault(ng,identity);assert identity==baseline
      rows.append(dict(kernels=kernels,nongemv=ng,cards=cards,seed=seed,returncode=0,tokens=r['tokens'],buffers_sha256=identity[1]))
      print(kernels,ng,cards,seed,'ASAN PASS',flush=True)
  save('sanitizer-mini.json',dict(passed=True,device_executed=False,sanitizers=['address','undefined','float-cast-overflow'],randomization='per-stage v2 work-item traversal in mock; v1 unchanged control',seeds=[0,1,17,73],runs=len(rows),rows=rows,binary_sha256=sha(binary)))
if __name__=='__main__':main()
