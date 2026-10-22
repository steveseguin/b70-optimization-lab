"""One serialized CPU compile turn; unchanged parent kernel objects retained."""
import contextlib,hashlib,importlib.util,json,os,resource,shutil,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
BASE=P/'frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port'
held=False
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=27_000_000_000,'CPU STOP 27 GB'
def compiler_turn():
 if held:return contextlib.nullcontext()
 s=importlib.util.spec_from_file_location('compile_turn',P.parents[1]/'ops/compile_turn.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m.turn()
def run(cmd,name):
 limits()
 with (B/(name+'.log')).open('w') as log:subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3)))
 print(name,'PASS',flush=True)
def main():
 global held
 limits();shutil.copytree(P/'native/generated',B/'native',dirs_exist_ok=True)
 old=str(P.parent/'packet58ag-onecard-ports');original=json.loads((P/'lineage/58ag-build-commands.json').read_text());commands=[]
 with compiler_turn():
  held=True
  for mode in ('gnu-host','device','intel-host'):
   (B/mode).mkdir(parents=True,exist_ok=True)
   source_mode='gnu-host' if mode=='intel-host' else mode
   names=[source_mode+'-entry-main']+(['device-single_device'] if mode=='device' else [])+[source_mode+'-own-rt-iq3']
   for name in names:
    row=next(r for r in original if r['name']==name);cmd=[x.replace(old,str(P)) for x in row['command']]
    if mode=='intel-host':
     cmd[0]='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
     for flag in ('-o','-MF'):
      if flag in cmd:cmd[cmd.index(flag)+1]=cmd[cmd.index(flag)+1].replace('/gnu-host/','/intel-host/')
     if '-c' not in cmd:cmd=[x.replace(str(B/'gnu-host/entry-main.o'),str(B/'intel-host/entry-main.o')) for x in cmd]
    run(cmd,name.replace(source_mode,mode));commands.append(dict(name=name.replace(source_mode,mode),command=cmd))
  for compiler,tag in [('/usr/bin/g++','gnu'),('/opt/intel/oneapi/compiler/2026.0/bin/icpx','intel')]:
   run([compiler,'-std=c++20','-O2',P/'native/wait_test.cpp','-o',B/(tag+'-wait-test')],tag+'-wait-build');run([B/(tag+'-wait-test')],tag+'-wait-test')
  run(['/usr/bin/g++','-O2',P/'native/k1_help.cpp','-o',B/'device/p58-cache-fixtures'],'k1-help')
  save(P/'evidence/build.json',dict(passed=True,device_executed=False,commands=commands,artifacts={str(f.relative_to(P)):sha(f) for f in B.glob('*/own-rt-iq3')},compile_turns=1,peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024))
  import preparation_gate
  preparation_gate.main()
  held=False
if __name__=='__main__':
 sys.modules['build_engine']=sys.modules[__name__];main()
