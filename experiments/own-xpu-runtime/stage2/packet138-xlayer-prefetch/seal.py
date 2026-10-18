"""Seal CPU capture preparation only; no parent orchestration is rewritten."""
import json,resource,subprocess,sys
from build_engine import P,ROOT,B,sha,save,limits

def main():
 limits()
 sys.path.insert(0,str(P.parent/'screen/v4-lanes'))
 from cpu_seal import verify as verify_wrapper
 verify_wrapper()
 from shared_oracle import completed_binding
 save(P/'evidence/oracle-gate.json',completed_binding())
 sources={};artifacts={}
 for path in (P/'build-receipt.json',P/'evidence/capture-cpu.json',P/'evidence/full-shape.json'):
  row=json.loads(path.read_text());assert row['passed'] and not row['device_executed']
  sources.update(row['sources']);artifacts.update(row.get('artifacts',{}))
  sources[str(path.relative_to(ROOT))]=sha(path)
 for name,digest in sources.items():assert sha(ROOT/name)==digest,name
 for name,digest in artifacts.items():assert sha(P/name)==digest,name
 with (P/'evidence/python-tests.log').open('w') as log:
  subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(P),'-p','test_capture.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
 args=json.loads((P/'evidence/arguments.json').read_text());assert args['passed'] and len(args['rank_execs'])==2 and not args['device_executed']
 save(P/'evidence/python-tests.json',dict(passed=True,device_executed=False,tests=12,log_sha256=sha(P/'evidence/python-tests.log')))
 local=[*P.glob('*.py'),*P.glob('*.hpp'),*P.glob('*.cpp'),P/'selection.json',P/'memory-plan.json',P/'dispatch-speed6.json',P/'suite.snapshot.json',P/'oracle-binding.json',P/'copy-provenance.json',P/'parent-commands.snapshot.json']
 local+=list((P/'inputs').glob('*/*'))
 local+=[P/'evidence'/n for n in ('arguments.json','arguments.log','oracle-gate.json','python-tests.json','python-tests.log')]
 sources.update({str(f.relative_to(ROOT)):sha(f) for f in local})
 # Do not flatten the external oracle symlink into the repository source map.
 for name in sources:assert (ROOT/name).resolve().is_relative_to(ROOT),name
 size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file());assert size<=300_000_000
 save(P/'packet-seal.json',dict(schema='packet138.cpu-preparation.v1',passed=True,device_executed=False,diagnostic_only=True,
  sources=sources,artifacts=artifacts,build_bytes=size,wrapper_seal_sha256=sha(P.parent/'screen/v4-lanes/wrapper-seal.json'),
  capture_output_limit=1_000_000_000,arithmetic='iq3-p49-split32-v1',real_capture='pending',phase2_decision='pending real capture, exact replay and causal traffic budget'))
 print('CPU capture seal PASS; build bytes',size)
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
