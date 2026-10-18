"""CPU-only readiness seal, independent of later diagnostic analysis."""
import json,resource,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits

def main():
 limits();sys.path.insert(0,str(P.parent/'screen/v4-lanes'))
 from cpu_seal import verify as verify_wrapper
 from shared_oracle import completed_binding
 verify_wrapper();save(P/'evidence/oracle-gate.json',completed_binding())
 sources={};artifacts={}
 for path in (P/'build-receipt.json',P/'evidence/full-shape.json'):
  row=json.loads(path.read_text());assert row['passed'] and row['device_executed'] is False
  sources.update(row['sources']);artifacts.update(row.get('artifacts',{}));sources[str(path.relative_to(ROOT))]=sha(path)
 for name,digest in sources.items():assert sha(ROOT/name)==digest,name
 for name,digest in artifacts.items():assert sha(P/name)==digest,name
 args=json.loads((P/'evidence/arguments.json').read_text());assert args['passed'] and len(args['rank_execs'])==2 and not args['device_executed']
 native=json.loads((P/'evidence/repair141b/native-entry.json').read_text())
 assert native['passed'] and not native['device_executed'] and not native['model_read']
 assert native['binary_sha256']==sha(B/'device/own-rt-iq3') and native['build_receipt_sha256']==sha(P/'build-receipt.json')
 assert len(native['rank_execs'])==2 and all(len(r['negatives'])==3 for r in native['rank_execs'])
 with (P/'evidence/python-tests.log').open('w') as log:subprocess.run([sys.executable,'-B',str(P/'test_probe.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
 save(P/'evidence/python-tests.json',dict(passed=True,device_executed=False,tests=15,log_sha256=sha(P/'evidence/python-tests.log')))
 with (P/'evidence/repair141b/analyzer-tests.log').open('w') as log:subprocess.run([sys.executable,'-B',str(P/'test_analyze.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
 save(P/'evidence/repair141b/analyzer-tests.json',dict(passed=True,device_executed=False,synthetic_only=True,tests=13,log_sha256=sha(P/'evidence/repair141b/analyzer-tests.log')))
 names=['build_engine.py','full_shape.py','probe.hpp','probe_touch.hpp','capture_worker.py','capture_identity.py','run_capture.py','exec_limits.py','launch_guard.py','shared_oracle.py','input_gate.py','argument_gate.py','queue_plan.py','seal.py','test_probe.py','preserve_links.py','memory_gate.py','memory-plan.json','selection.json','dispatch-speed6.json','suite.snapshot.json','oracle-binding.json','copy-provenance.json','symlinks.json','capture-binding.json','routes.bin','probe-plan.json','README.md','RETENTION.md','native-delta.patch','DO-NOT-REPEAT.md','preregistration.json']
 names+=['cpu_entry.hpp','native_entry_gate.py','analyze.py','test_analyze.py','localize_pins.py','compiled-source-snapshots.json','proposal.snapshot.txt']
 for name in names:sources[str((P/name).relative_to(ROOT))]=sha(P/name)
 for f in sorted((P/'evidence/repair141b').iterdir()):
  if f.is_file() and f.suffix in ('.json','.log','.strace','.gz') and not f.name.startswith(('analysis-', 'seal-')):sources[str(f.relative_to(ROOT))]=sha(f)
 for f in (P/'inputs').glob('*/*'):
  if f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
 for name in ('arguments.json','arguments.log','oracle-gate.json','python-tests.json','python-tests.log'):
  f=P/'evidence'/name;sources[str(f.relative_to(ROOT))]=sha(f)
 proposal=P.parents[1]/'ops/lane-queue/proposed-p141-probe-B.txt'
 assert proposal.read_bytes()==(P/'proposal.snapshot.txt').read_bytes(),'proposal differs from packet-local snapshot'
 for name in sources:assert (ROOT/name).resolve().is_relative_to(ROOT),'external path must use oracle binding: '+name
 limits();size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file() and not f.is_symlink())
 save(P/'packet-seal.json',dict(schema='packet141.cpu-preparation.v1',passed=True,device_executed=False,diagnostic_only=True,sources=sources,artifacts=artifacts,build_bytes=size,wrapper_seal_sha256=sha(P.parent/'screen/v4-lanes/wrapper-seal.json'),output_limit_bytes=200000000,arithmetic='iq3-p49-split32-v1',device_evidence='pending'))
 print('CPU preparation seal PASS; physical build bytes',size)
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
