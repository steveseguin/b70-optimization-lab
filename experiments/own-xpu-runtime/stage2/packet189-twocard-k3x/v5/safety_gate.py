"""Local drain, cooperative-stop and source-closure checks; no device calls."""
import json,resource,subprocess,sys,re
from p189_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

def main():
 limits();rows=[]
 for script in (LOCAL/'test_drain_fix.py',P/'test_refusal.py',P/'test_timing_report.py'):
  r=subprocess.run([sys.executable,'-B',str(script)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=90)
  log=P/'evidence'/('safety-'+script.stem+'.log');log.write_text(r.stdout+r.stderr)
  assert r.returncode==0,log.read_text();rows.append(dict(test=str(script.relative_to(ROOT)),log=str(log.relative_to(ROOT)),sha256=sha(log)))
 # The by-value checked mirror is retained in-repository, not rebuilt from siblings.
 roots=[LOCAL/'native-base',P/'native',P/'native-src']
 paths=[f for root in roots for f in root.rglob('*') if f.is_file() and f.suffix in ('.hpp','.cpp','.inc')]
 pattern=r'(std::|sycl::(native::|half_precision::)?|__builtin_)(exp|log|pow|sin|cos)(2|10|1p|m1)?f?\s*\('
 for f in paths:
  assert not re.search(pattern,f.read_text()),'forbidden platform math: '+str(f)
  for inc in re.findall(r'^\s*#include\s*"([^"\n]+)"',f.read_text(),re.M):
   if inc.startswith('/'):
    target=__import__('pathlib').Path(inc);assert target.resolve().is_relative_to(LOCAL),'external native include: '+inc
 source={str(f.relative_to(ROOT)):sha(f) for f in [P/'safety_gate.py',LOCAL/'test_drain_fix.py',LOCAL/'drain_gate.py',P/'p189_v5_drain_gate.py',P/'test_refusal.py',P/'test_timing_report.py',*paths]}
 save(P/'evidence/safety.json',dict(passed=True,device_executed=False,runs=rows,sources=source,native_files=len(paths),external_native_includes=0))
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
