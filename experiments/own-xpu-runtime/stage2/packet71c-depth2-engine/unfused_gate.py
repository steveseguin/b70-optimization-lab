"""Compare production tuple and standalone outputs for both shared expert formats."""
import json,os,resource,subprocess
from build_engine import P,B,ROOT,sha,save

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 commands=json.loads((P/'engine-commands.json').read_text());rows=[]
 for mode in ('gnu-host','intel-host'):
  base=next(r['command'] for r in commands if r['name']==mode+'-fixture-compile')
  source=next(x for x in base if x.endswith('/batch_fixture.cpp'))
  cmd=[str(P/'unfused_fixture.cpp') if x==source else x for x in base]
  binary=B/(mode+'-unfused');cmd[cmd.index('-o')+1]=str(binary)
  with (B/(mode+'-unfused-build.log')).open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True)
  prefix=P/'fixture'/(mode+'-unfused')
  env=dict(os.environ,LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.0/lib')
  r=subprocess.run([str(binary),str(prefix)],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=env)
  (P/'evidence'/(mode+'-unfused.log')).write_text(r.stdout+r.stderr);r.check_returncode()
  result=json.loads(r.stdout);assert result['passed'] and result['byte_checks']==80
  files={suffix:sha(prefix.with_name(prefix.name+'-'+suffix+'.bin')) for suffix in ('expected','actual')};assert files['expected']==files['actual']
  rows.append(dict(compiler=mode,result=result,hashes=files,compile_command=cmd,binary_sha256=sha(binary)));print(mode,'unfused 80 byte checks PASS',flush=True)
 assert rows[0]['hashes']==rows[1]['hashes']
 save(P/'evidence/unfused.json',dict(passed=True,device_executed=False,model_executed=False,results=rows,sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('unfused_fixture.cpp','unfused_gate.py','p30_small.hpp','arithmetic.hpp','dispatch-speed6.json')}))
if __name__=='__main__':main()
