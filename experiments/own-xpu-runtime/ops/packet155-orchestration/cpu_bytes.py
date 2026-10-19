"""Fresh runs of hash-bound GNU/Intel state and production-extent fixtures."""
import concurrent.futures,hashlib,json,os,resource,shutil,subprocess,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet155-record-bundle9'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert shutil.disk_usage('/').free>=30_000_000_000
 pins=json.loads((O/'inputs/packet153-native.json').read_text())
 for name,row in pins['binaries'].items():assert sha(P/name)==row['sha256']
 out=P/'build/cpu/results';out.mkdir(exist_ok=True);rows=[]
 for compiler in ('GNU','Intel'):
  for repeat in (1,2):
   cp=subprocess.run([str(P/'build/cpu/real-shape'/('fixture-'+compiler))],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
   row=json.loads(cp.stdout);assert row['passed'] and row['extents']==984 and row['copy_bytes']==19025640
   rows.append(dict(row,compiler=compiler,repeat=repeat))
 (O/'evidence/real-shape.json').write_text(json.dumps(dict(passed=True,device_executed=False,runs=rows),indent=2)+'\n')
 def run(job):
  compiler,repeat,mode=job
  assert shutil.disk_usage('/').free>=30_000_000_000
  dest=out/f'{compiler}-{repeat}-{mode}';dest.mkdir()
  binary=P/'build/cpu/state'/('fixture-'+compiler);selection=P/'build/cpu/state'/(mode+'.json')
  log=O/'evidence'/f'state-{compiler}-{repeat}-{mode}.log'
  with log.open('w') as f:
   cp=subprocess.run([sys.executable,'-B',str(O/'cpu_bytes.py'),'--worker',str(binary),str(selection),sha(selection),str(dest),mode,'sequence-only'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.0/lib'))
  assert cp.returncode==0,log.read_text()[-1500:]
  result=json.loads((dest/'result.json').read_text());result.update(compiler=compiler,repeat=repeat,mode=mode)
  print(compiler,repeat,mode,'PASS',flush=True);return result
 jobs=[(c,r,m) for c in ('GNU','Intel') for r in (1,2) for m in ('production','static')]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(run,jobs))
 assert len({r['canonical_sha256'] for r in rows})==1
 (O/'evidence/composition-bytes.json').write_text(json.dumps(dict(passed=True,device_executed=False,runs=rows,peak_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),indent=2)+'\n')
if __name__=='__main__':
 if '--worker' in sys.argv:
  resource.setrlimit(resource.RLIMIT_AS,(1280*1024**2,1280*1024**2));os.execv(sys.argv[2],sys.argv[2:])
 else:resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
