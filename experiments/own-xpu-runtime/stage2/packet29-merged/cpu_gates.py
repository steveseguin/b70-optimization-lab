"""Cheap CPU integration gates; refuses accelerator-linked executables."""
import hashlib,json,os,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def host(binary):
 d=subprocess.check_output(['readelf','-d',str(binary)],text=True).lower()
 assert not any(x in d for x in ('libsycl','libze_loader','libur_loader','libopencl'))
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 import test
 binary=B/'host/own-rt-iq3';host(binary);root=B/f'integration-{time.time_ns()}';root.mkdir();rows=[]
 units={}
 for name in ('authority-tests','owner-retirement-tests','chain-tests','queue-tests','lifetime-tests'):
  host(B/'host'/name);r=subprocess.run([str(B/'host'/name)],text=True,capture_output=True);assert r.returncode==0,r.stderr;units[name]=r.stdout
 for dispatch in ('default','all-new','merged-example'):
  for mode in ('core','parallel'):
   for timing in ('token','launch','class'):
    result=test.run(binary,root/f'{dispatch}-{mode}-{timing}',B/'input',mode,['--timing',timing,'--dispatch',P/f'dispatch-{dispatch}.json'])
    rows.append(dict(dispatch=dispatch,mode=mode,timing=timing,result=result));print(dispatch,mode,timing,len(result['tests']),'PASS',flush=True)
 (P/'integration-gates.json').write_text(json.dumps(dict(passed=True,device_executed=False,binary_sha256=sha(binary),rows=rows,units=units,cases=sum(len(x['result']['tests']) for x in rows)),indent=2)+'\n')
if __name__=='__main__':main()
