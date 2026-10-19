"""Run the strict analyzer's positive and refusal cases; save their source pins."""
import resource,subprocess,sys
import freeze_safe
freeze_safe.install()
from p151_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);limits()
 r=freeze_safe.run([sys.executable,'-B',str(LOCAL/'test_analysis.py')],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
 log=P/'evidence/analysis.log';log.write_text(r.stdout+r.stderr);assert r.returncode==0,log.read_text()
 save(P/'evidence/analysis.json',dict(passed=True,device_executed=False,tests=10,log_sha256=sha(log),sources={str(f.relative_to(ROOT)):sha(f) for f in [LOCAL/'analyze.py',LOCAL/'test_analysis.py',P/'analysis_gate.py']}))
