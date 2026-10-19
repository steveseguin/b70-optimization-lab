"""Built help and actual device-path imports under the closed A/B environments."""
import importlib.util,json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,save,sha,limits
import native_env
def main():
    limits();ops=P.parents[1]/'ops';sys.path.append(str(ops))
    spec=importlib.util.spec_from_file_location('p168_entry_sandbox',ops/'rehearse_entry.py')
    R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
    parent=P.parent/'packet163-full-gate/two-card/evidence/preparation-probe.json'
    probes=json.loads(parent.read_text())['probes'];results=[]
    binary=P/'build/device/own-rt-iq3'
    for lane in ('A','B'):
        env=native_env.environment(lane)
        with tempfile.TemporaryDirectory(prefix='p168-help-')as temp:
            cp=subprocess.run([str(binary),'--help'],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,
              preexec_fn=lambda:R.prepare_restrict(binary,[],Path(temp)))
        assert cp.returncode==0,cp.stderr
        flags={s for probe in probes for s in probe['real_native_argv'][1:]if s.startswith('--')}|{'--census-probe'}
        assert flags<=set(cp.stdout.split()),flags-set(cp.stdout.split())
        code='import sys,resource;resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);sys.path.insert(0,'+repr(str(P))+');import entry,screen,pipeline,suite,oracle,native_env,readiness;print("PASS passive device-path imports")'
        imp=subprocess.run(['/usr/bin/python3','-B','-c',code],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True)
        assert imp.returncode==0,imp.stderr
        results.append(dict(lane=lane,passed=True,native_flags=sorted(flags),help_returncode=cp.returncode,
          native_help=cp.stdout,imports=imp.stdout.strip(),environment=env))
    save(P/'evidence/launch-checks.json',dict(passed=True,device_executed=False,model_reads=False,
      scope='prototype native argv/help and passive imports only; no complete launch path exists',binary_sha256=sha(binary),results=results))
    print('PASS private native flags/help and A/B imports')
if __name__=='__main__':main()
