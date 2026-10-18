"""Run CPU-only drain, refusal, and timing-join regressions and bind their sources."""
import importlib.util,json,resource,subprocess,sys
from common import HERE,ROOT,save,sha

def main():
 jobs=[(HERE.parent/'test_drain_fix.py',4),(HERE/'test_refusal.py',4),(HERE/'test_timing_report.py',1)]
 rows=[]
 for script,count in jobs:
  r=subprocess.run([sys.executable,'-B',str(script)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60)
  log=HERE/'evidence'/('safety-'+script.stem+'.log');log.write_text(r.stdout+r.stderr)
  assert r.returncode==0 and ('Ran '+str(count)+' test') in log.read_text(),str(script)+': '+log.read_text()
  rows.append(dict(test=str(script.relative_to(ROOT)),tests=count,log=str(log.relative_to(ROOT)),log_sha256=sha(log)))
 paths=[*HERE.glob('*.py'),HERE.parent/'test_drain_fix.py',HERE.parent/'drain_gate.py']
 # This receipt is bound before the CPU seal; generated evidence is never imported.
 sources={str(f.relative_to(ROOT)):sha(f) for f in paths}
 manifest=json.loads((HERE.parent/'parent-manifest.json').read_text())
 for name,digest in manifest['sources'].items():assert sha(ROOT/name)==digest,'frozen parent changed: '+name
 for name,target in manifest['symlinks'].items():
  link=HERE.parent/name;assert link.is_symlink() and str(link.readlink())==target,'source symlink changed: '+name
 spec=importlib.util.spec_from_file_location('p130_math_audit',HERE.parent/'math_gate.py');math=importlib.util.module_from_spec(spec);spec.loader.exec_module(math)
 checked=math.check()
 sources.update(manifest['sources'])
 sources.update({name:sha(ROOT/name) for name in checked['files']})
 sources[str((HERE.parent/'parent-manifest.json').relative_to(ROOT))]=sha(HERE.parent/'parent-manifest.json')
 save(HERE/'evidence/safety.json',dict(passed=True,device_executed=False,runs=rows,sources=sources,frozen_sources=len(manifest['sources']),symlinks_preserved=len(manifest['symlinks']),deterministic_math=checked))
 print(json.dumps(dict(passed=True,device_executed=False,tests=sum(r['tests'] for r in rows))))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
