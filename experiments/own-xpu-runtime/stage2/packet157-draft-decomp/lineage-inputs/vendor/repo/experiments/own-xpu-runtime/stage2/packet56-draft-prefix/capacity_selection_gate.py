#!/usr/bin/env python3
"""Independent arithmetic-v2 QSA gates; only native CPU compilers/binaries."""
import gzip,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent
B=P/'build'/'capacity-selection'
PREFIX=['nice','-n','19','ionice','-c','3']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd):
 r=subprocess.run(PREFIX+list(map(str,cmd)),text=True,capture_output=True,env={**os.environ,'OMP_NUM_THREADS':'2'})
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
 return r.stdout,r.stderr
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 rows=[]
 for name,compiler in [('gnu','/usr/bin/g++'),('icpx','/opt/intel/oneapi/compiler/latest/bin/icpx')]:
  run(['df','-B1','/'])
  if shutil.disk_usage('/').free<8_000_000_000:raise RuntimeError('root below 8 GB; stopped before compiler write')
  B.mkdir(parents=True,exist_ok=True)
  binary=B/('selection-'+name)
  flags=['-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-fno-associative-math']
  dependencies={name:sha(P/name) for name in ('capacity_selection_gate.cpp','core_v2.hpp','kernels.hpp','round2.hpp','specialised.hpp','p30_attention.hpp','detmath.hpp','rope.hpp')}
  command=[compiler,*flags,P/'capacity_selection_gate.cpp','-o',binary]
  out,err=run(command)
  dynamic,_=run(['readelf','-d',binary]);assert not any(x in dynamic.lower() for x in ('libsycl','libze_loader','libur_loader','libopencl'))
  started=time.monotonic();out,err=run([binary]);result=json.loads(out)
  version,_=run([compiler,'--version'])
  row=dict(compiler=name,compiler_version=version.splitlines()[0],source_sha256=dependencies,command=list(map(str,command)),binary_sha256=sha(binary),seconds=time.monotonic()-started,result=result,stdout_sha256=hashlib.sha256(out.encode()).hexdigest(),stderr=err)
  evidence=P/('capacity-selection-'+name+'.jsonl.gz');evidence.write_bytes(gzip.compress(out.encode(),mtime=0));row['raw_output']=str(evidence.relative_to(P))
  rows.append(row)
  receipt=dict(passed=len(rows)==2 and all(r['result']['passed'] for r in rows),device_executed=False,rows=rows,source_sha256=sha(P/'capacity_selection_gate.cpp'))
  (P/'capacity-selection-gates.json').write_text(json.dumps(receipt,indent=2)+'\n')
  binary.unlink()
  row.update(binary_retention='deleted_after_hashed_receipt',deleted_after_hashed_receipt=True)
  (P/'capacity-selection-gates.json').write_text(json.dumps(receipt,indent=2)+'\n')
  print(name,json.dumps(result),flush=True)
 if rows[0]['result']!=rows[1]['result']:raise RuntimeError('compiler gate receipts differ')
 shutil.rmtree(B)
if __name__=='__main__':main()
