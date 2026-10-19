import freeze_safe
freeze_safe.install()
import json,resource,subprocess,sys
from p151_v5_build_engine import P,ROOT,B,save,sha,limits
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
def compiler_turn():
 import importlib.util,sys
 if str(P.parent) not in sys.path:sys.path.append(str(P.parent))
 spec=importlib.util.spec_from_file_location('p151_ops_turn',P.parents[2]/'ops/compile_turn.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 module.time=freeze_safe.ActiveClock()
 return module.turn()
def main():
 limits();out=B/'state';out.mkdir(exist_ok=True);prior=json.loads((P/'engine-commands.json').read_text());cmd=list(next(r['command'] for r in prior if r['name']=='gnu-host-entry-main'));cmd[cmd.index('-c')+1]=str(P/'native/state_fixture.cpp');cmd[cmd.index('-o')+1]=str(out/'state.o')
 link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'));link=[str(out/'state.o') if x.endswith('/entry-main.o') else x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')];link[link.index('-o')+1]=str(out/'fixture')
 with compiler_turn(),(out/'compile.log').open('w') as log:
  for args in (cmd,link):freeze_safe.run(args,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
 rows=[]
 for i in (1,2):
  r=freeze_safe.run([str(out/'fixture'),str(out/('run'+str(i)))],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180);(out/('run'+str(i)+'.log')).write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr;rows.append(json.loads(r.stdout))
 assert rows[0]==rows[1]
 save(P/'evidence/sibling-state.json',dict(passed=True,device_executed=False,runs=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'state_gate.py',P/'native/state_fixture.cpp',P/'native/sibling.hpp')}))
if __name__=='__main__':main()
