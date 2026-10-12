"""ASan/UBSan CPU mini gate with four independent work-item orders."""
import hashlib,json,os,subprocess,time
from pathlib import Path
from cpu_gates import host
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 binary=B/'asan/own-rt-iq3';host(binary);root=B/f'sanitizer-mini-{time.time_ns()}';root.mkdir();rows=[];identities={}
 for dispatch in ('default','all-new'):
  for mode in ('core','parallel'):
   for cards in (1,2):
    for seed in (0,1,17,73):
     out=root/f'{dispatch}-{mode}-{cards}-{seed}'
     cmd=[str(binary),'--mini','--cards',str(cards),'--card','0','--memory','resident' if cards==2 else 'layer-streaming','--nongemv',mode,'--timing','token','--max-new','3','--dispatch',str(P/f'dispatch-{dispatch}.json'),'--output',str(out)]
     env=dict(os.environ,PACKET24_ORDER_SEED=str(seed),ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
     peak_kib=0
     with out.with_suffix('.log').open('w') as log:
      r=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env=env)
      while r.poll() is None:
       try:
        status=Path(f'/proc/{r.pid}/status').read_text()
        rss=next(int(line.split()[1]) for line in status.splitlines() if line.startswith('VmRSS:'))
        peak_kib=max(peak_kib,rss)
        if rss>8*1024**2:
         r.terminate();r.wait();raise RuntimeError('sanitizer process exceeded 8 GiB RSS')
       except (FileNotFoundError,StopIteration):pass
       time.sleep(.05)
      r.wait()
     assert r.returncode==0,out.with_suffix('.log').read_text()
     receipt=json.loads((out/'receipt.json').read_text());assert receipt['passed'] and not receipt['device_executed']
     fixtures={str(f.relative_to(out)):sha(f) for f in out.glob('step*/layer-*.bf16')};identity=(receipt['tokens'],fixtures,sha(out/'buffers.json'));key=(dispatch,mode)
     if key in identities:assert identities[key]==identity,(key,seed)
     else:identities[key]=identity
     rows.append(dict(dispatch=dispatch,mode=mode,cards=cards,seed=seed,max_rss_kib=peak_kib,tokens=receipt['tokens'],fixture_hashes=fixtures,buffers_sha256=identity[2],passed=True));print(dispatch,mode,cards,seed,'PASS',flush=True)
 (P/'sanitizer-mini.json').write_text(json.dumps(dict(passed=True,device_executed=False,binary_sha256=sha(binary),seeds=[0,1,17,73],runs=rows,violations=0),indent=2)+'\n')
if __name__=='__main__':main()
