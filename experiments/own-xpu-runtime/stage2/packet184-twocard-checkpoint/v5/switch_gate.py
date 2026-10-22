"""Actual Engine C/X/C/X/C switching and reset, both compilers; tiny weights."""
import json,resource,subprocess,os
from p184_v5_build_engine import P,LOCAL,ROOT,B,CHECKED,sha,save,run,limits

def main():
 limits();out=B/'switch';out.mkdir(exist_ok=True);prior=json.loads((P/'engine-commands.json').read_text())
 args=list(next(r['command'] for r in prior if r['name']=='gnu-host-entry-main'));args=args[1:args.index('-o')];i=args.index('-c');del args[i:i+2]
 for mode in ('production','static'):
  row=json.loads((P/'lineage'/mode/'selection.json').read_text());row['choices'].update(head='production',experts='production');save(out/(mode+'.json'),row)
 rows=[]
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  obj=out/(compiler+'.o');binary=out/('fixture-'+compiler)
  run([cxx,*args,'-c',P/'native/switch_bytes.cpp','-o',obj],'switch-'+compiler+'-compile')
  link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'));link=[str(obj) if x.endswith('/entry-main.o') else x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')];link[0]=cxx;link[link.index('-o')+1]=str(binary);link+=['-no-pie','-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib'];run(link,'switch-'+compiler+'-link')
  for repeat in (1,2):
   a=out/'production.json';b=out/'static.json';dest=out/f'{compiler}-{repeat}';env=dict(os.environ,OMP_NUM_THREADS='2',LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.0/lib')
   cp=subprocess.run([str(binary),str(a),sha(a),str(dest),'switch',str(b),sha(b)],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120);assert cp.returncode==0,cp.stderr
   rows.append(dict(json.loads(cp.stdout),compiler=compiler,repeat=repeat))
 save(P/'evidence/switch.json',dict(passed=True,device_executed=False,model_read=False,full_shape_read=False,sequence=['production','static','production','static','production'],runs=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'switch_gate.py',P/'native/switch_bytes.cpp',P/'native/engine_bracket.hpp',CHECKED/'strict_snapshot.hpp',CHECKED/'request_reset.hpp')}))
 print('Real Engine five-view switch/reset table and state bytes GNU/Intel PASS')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
