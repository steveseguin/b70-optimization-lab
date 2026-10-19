"""Reproducible pause and unchanged shared launch-environment CPU checks."""
import freeze_safe
freeze_safe.install()
import json,sys,subprocess,resource
from p151_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

def main():
 limits()
 assert sha(LOCAL/'ops/launch_env.py')==sha(LOCAL.parents[1]/'ops/launch_env.py'),'shared launch environment changed'
 rows=[('freeze-safe',[sys.executable,'-B',str(P/'test_freeze_safe.py')],[P/'freeze_safe.py',P/'test_freeze_safe.py']),
       ('launch-env',[sys.executable,'-B',str(P/'cpu_tool.py'),str(LOCAL.parents[1]/'ops/launch_env.py'),str(P/'build/device/own-rt-iq3'),str(P/'build/gnu-host/own-rt-iq3')],[P/'cpu_tool.py',LOCAL/'ops/entry_sandbox.py',LOCAL/'ops/launch_env.py'])]
 for name,cmd,paths in rows:
  r=freeze_safe.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
  log=P/'evidence'/(name+'.log');log.write_text(r.stdout+r.stderr);assert r.returncode==0,log.read_text()
  save(P/'evidence'/(name+'.json'),dict(passed=True,device_executed=False,command=cmd,log_sha256=sha(log),sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'aux_gates.py',*paths]}))
  print(name,'PASS',flush=True)
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
