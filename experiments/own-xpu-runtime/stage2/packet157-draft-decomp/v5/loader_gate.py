"""Run the actual shared loader check without executing either native binary."""
import subprocess,sys
from p157_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

def main():
 limits();ops=LOCAL.parents[1]/'ops/launch_env.py';vendor=P/'p157_ops_launch_env.py'
 assert sha(ops)==sha(vendor),'shared environment authority changed'
 binaries=[P/'build'/mode/'own-rt-iq3' for mode in ('gnu-host','device')]
 cp=subprocess.run([sys.executable,'-B',str(ops),*map(str,binaries)],stdin=subprocess.DEVNULL,capture_output=True,text=True)
 log=P/'evidence/launch-env.log';log.write_text(cp.stdout+cp.stderr);assert cp.returncode==0,log.read_text()
 save(P/'evidence/loader.json',dict(passed=True,device_executed=False,ops_launch_env_sha256=sha(ops),log_sha256=sha(log),binaries={str(f.relative_to(ROOT)):sha(f) for f in binaries},sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'loader_gate.py',vendor)}))
 print('Actual ops/launch_env.py: both binaries PASS')
if __name__=='__main__':main()
