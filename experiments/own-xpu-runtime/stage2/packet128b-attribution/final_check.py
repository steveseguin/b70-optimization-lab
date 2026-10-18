"""CPU-only sealed-input validation and temporary queue planning."""
import difflib,importlib.util,json,resource,shutil,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,B,BASE,sha,save,limits

def main():
 limits()
 parent=json.loads((P/'parent-manifest.json').read_text())
 for name,h in parent.items():assert sha(ROOT/name)==h, 'frozen parent changed: '+name
 for name in ('selection.json','memory-plan.json','dispatch-speed6.json','p49_dispatch.py','drain_gate.py'):
  assert sha(P/name)==sha(BASE/name),name
 assert sha(P/'compile_turn.py')==sha(P.parent/'packet94-hc-norm-fusion/compile_turn.py')
 # Bind the packet77 observation approach by source, not stale sample timings.
 save(P/'instrumentation-provenance.json',dict(parent='packet128-attribution',arithmetic_parent='packet124b-record-bundle',parent_manifest_sha256=sha(P/'parent-manifest.json'),
  recorder_sources={str(f.relative_to(ROOT)):sha(f) for f in [P.parent/'packet77-attribution/instrumentation.patch',P.parent/'packet77-attribution/attribution.hpp']},arithmetic='iq3-p49-split32-v1',arithmetic_changed=False))
 delta=''
 for name in ('main.cpp','rank.hpp','mtp.hpp','p105_runtime.hpp','strict_snapshot.hpp','attribution.hpp'):
  original=P.with_name('packet128-attribution')/name
  prior=original.read_text().splitlines(True) if original.exists() else []
  delta+=''.join(difflib.unified_diff(prior,(P/name).read_text().splitlines(True),fromfile='packet128/'+name,tofile='packet128b/'+name))
 (P/'instrumentation.patch').write_text(delta)
 # Every parent link survives; new links may be added by CPU fixtures.
 links=json.loads((P/'copy-symlinks.json').read_text())['links']
 for entry in links:
  name,target=entry.split(' -> ',1)
  assert (P/name).is_symlink() and (P/name).readlink().as_posix()==target, name
 for leaf in ('python-tests.json','queue-gate.json','launch-limits.json','recorder-gate.json'):
  proof=json.loads((P/'evidence'/leaf).read_text());assert proof['passed'] and not proof['device_executed']
  for name,digest in proof['sources'].items():assert sha(ROOT/name)==digest,(leaf,name)
 from run_screen import VIEW
 from common import sealed,verify_map
 from types import SimpleNamespace
 identity=sealed(SimpleNamespace(lineage=VIEW,seal=VIEW/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='attribution',placement='1'))
 gate=json.loads((P/'evidence/argument-gate.json').read_text());assert gate['passed'] and gate['native_exec_intercepted'] and not gate['device_executed'];verify_map(ROOT,gate['sources'])
 assert len(gate['startup'])==2 and all(x['result']['passed'] for x in gate['startup'])
 spec=importlib.util.spec_from_file_location('p128_queue_plan',P.parents[1]/'ops/lane-queue/lanequeue.py');q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
 env=q.closed_env(q.library_path());proposed=P.parents[1]/'ops/lane-queue/proposed-p128b-attr-B.txt'
 with tempfile.TemporaryDirectory(prefix='p128b-queue-plan-') as d:
  scratch=Path(d);shutil.copyfile(proposed,scratch/'queue-B.txt')
  cp=subprocess.run([sys.executable,'-B',str(Path(q.__file__)),'plan','--lane','B','--directory',str(scratch)],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=env,timeout=180,cwd=ROOT)
  (P/'evidence/queue-plan.log').write_text(cp.stdout+cp.stderr)
  assert cp.returncode==0,cp.stdout+cp.stderr
  plans=[json.loads(line) for line in cp.stdout.splitlines() if line.strip()];assert len(plans)==1 and plans[0]['plan']=='passed'
 cp=subprocess.run([sys.executable,'-B',str(P/'run_screen.py'),'--plan'],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=env,cwd=ROOT,timeout=180)
 (P/'evidence/screen-plan.log').write_text(cp.stdout+cp.stderr);assert cp.returncode==0,cp.stderr
 limits();size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file() and not f.is_symlink())
 save(P/'evidence/final-check.json',dict(passed=True,device_executed=False,parent_files_unchanged=len(parent),
  inherited_arithmetic_objects_unchanged=True,identity=identity,argument_gate_sha256=sha(P/'evidence/argument-gate.json'),
  proposal_sha256=sha(proposed),plan=plans,build_logical_bytes=size,root_free_bytes=shutil.disk_usage('/').free,
  sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'final_check.py',P/'analyze.py',P/'worker.py',P/'run_screen.py',P/'screen128.py',P/'teardown.py',P/'preregistration.json',P/'test_analysis.py',P/'test_worker.py',P/'queue_gate.py',P/'launch_limit_gate.py',P/'recorder_gate.py']}))
 print('parent unchanged; sealed sources, argument/startup gate, one temporary B queue plan PASS; build bytes',size)
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
