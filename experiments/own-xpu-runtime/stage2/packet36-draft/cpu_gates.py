"""Owner/lifetime CPU suites; rejects accelerator-linked binaries."""
import hashlib,json,os,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def host(binary):
 d=subprocess.check_output(['readelf','-d',str(binary)],text=True).lower()
 assert not any(x in d for x in ('libsycl','libze_loader','libur_loader','libopencl'))
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 rows=[]
 for compiler in ('gnu-host','icpx-host'):
  for name in ('authority-tests','owner-retirement-tests','chain-tests','queue-tests','lifetime-tests'):
   binary=B/compiler/name;host(binary)
   r=subprocess.run([str(binary)],text=True,capture_output=True,timeout=120)
   assert r.returncode==0,r.stdout+r.stderr
   rows.append(dict(compiler=compiler,name=name,binary_sha256=sha(binary),stdout=r.stdout,stderr=r.stderr))
 (P/'owner-gates.json').write_text(json.dumps(dict(passed=True,device_executed=False,suites=len(rows),rows=rows),indent=2)+'\n')
 print(len(rows),'owner/lifetime suites pass')
if __name__=='__main__':main()
