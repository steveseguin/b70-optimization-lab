"""CPU-only compiler/byte gate; caps apply only to this CLI, never imports."""
import hashlib,json,os,resource,shutil,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P/'v5'))
import build_engine

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 build_engine.limits();b=P/'build/leaf';b.mkdir(parents=True,exist_ok=True);ev=P/'evidence/leaf';ev.mkdir(parents=True,exist_ok=True)
 checked=P.parent/'packet111-record-bundle/build/checked/experiments/own-xpu-runtime/stage2/packet111-record-bundle'
 flags=['-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-fno-associative-math','-DOWN_RT_HOST_ONLY','-I'+str(checked)]
 rows=[]
 for label,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=b/label;cmd=[cxx,*flags,str(P/'cpu_leaf.cpp'),'-o',str(binary)]
  with build_engine.compiler_turn(),(ev/(label+'-build.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
  runs=[]
  for owner in ('1','2'):
   raw=ev/(label+'-'+owner+'.bin');run=subprocess.run([str(binary),str(raw)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=600)
   (ev/(label+'-'+owner+'.log')).write_text(run.stdout+run.stderr)
   if run.returncode:raise RuntimeError(label+' '+owner+' '+run.stderr)
   row=json.loads(run.stdout);row.update(output_sha256=sha(raw),binary_sha256=sha(binary),command=[str(binary),str(raw)],owner=owner);runs.append(row)
  assert runs[0]['output_sha256']==runs[1]['output_sha256'];rows.append(dict(compiler=label,command=cmd,runs=runs))
 sources={str(x.relative_to(P)):sha(x) for x in [P/'cpu_gate.py',P/'cpu_leaf.cpp',*P.glob('p116*.hpp')]}
 receipt=dict(passed=True,device_executed=False,arithmetic='iq3-p49-split32-v1',source_sha256=sources,compilers=rows,output_format='FNV1a64 allocation digests AFTER complete memcmp; not cryptographic equality oracle',cross_compiler_identity_required=False,within_compiler_production_candidate_bytes=True)
 (P/'evidence/cpu-leaf.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'passed':True,'checks_per_process':rows[0]['runs'][0]['checks']}))
if __name__=='__main__':main()
