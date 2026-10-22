"""Both engine binaries resolve every shared library under the vendored launch environment.

The vendored p183_ops_launch_env.py must equal the ops/launch_env.py authority
byte for byte; each ELF is checked with ldd inside the shared entry sandbox.
"""
import json,resource,subprocess,sys
from p183_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

def main():
 limits();authority=LOCAL.parents[1]/'ops/launch_env.py';vendored=P/'p183_ops_launch_env.py'
 assert sha(authority)==sha(vendored),'vendored launch environment differs from ops/launch_env.py'
 binaries=[P/'build/gnu-host/own-rt-iq3',P/'build/device/own-rt-iq3'];log=P/'evidence/loader.log'
 r=subprocess.run([sys.executable,'-B',str(vendored),*map(str,binaries)],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120,env={'PATH':'/usr/bin:/bin','PYTHONPATH':str(LOCAL.parents[1]/'ops')})
 log.write_text(r.stdout+r.stderr);assert r.returncode==0 and r.stdout.count('PASS')==2,log.read_text()
 save(P/'evidence/loader.json',dict(passed=True,device_executed=False,authority='ops/launch_env.py',vendored_authority_equal=True,binaries=2,
  sources={str(f.relative_to(ROOT)):sha(f) for f in (vendored,P/'launch-environment.json',*binaries,log,P/'loader_gate.py')}))
 print('loader: both binaries PASS under the vendored launch environment')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
