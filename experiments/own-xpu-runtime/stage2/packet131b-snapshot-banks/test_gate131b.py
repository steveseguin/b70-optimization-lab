"""Gate-build rejection and real run131 entry-to-native CPU regression.

Only operational predecessor receipts and the service wrapper are synthetic.
Readiness, source boundaries, static/complete oracle, selection, worker inputs
and both native argv paths are real. The inherited worker audit hook forbids
process execution, device opens and writes outside disposable scratch.
"""
import contextlib, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path
from unittest.mock import patch
from build131 import P, ROOT, sha, save, cpu_main


def gate_build_negative():
 import ready131
 with tempfile.TemporaryDirectory(prefix='p131b-external-',dir='/tmp') as outside, tempfile.TemporaryDirectory(dir=P/'build/tmp',prefix='source-gate-') as inside:
  out=Path(outside)/'identity.json';out.write_text('{}')
  local=Path(inside);link=local/'external';link.symlink_to(out)
  bad={str(link.relative_to(ROOT)):sha(out)}
  (local/'evidence').mkdir()
  save(local/'evidence/census131.json',dict(passed=True,device_executed=False,sources=bad))
  with patch.object(ready131,'P',local),patch.object(ready131,'verify_oracle'),patch.object(ready131,'save') as writer:
   try:ready131.main()
   except ValueError as error:
    assert 'unsafe identity path' in str(error);refusal=str(error)
   else:raise AssertionError('gate builder accepted an external source')
   writer.assert_not_called()
  assert not (local/'evidence/ready131.json').exists()
 return dict(passed=True,refusal=refusal,gate_written=False,device_executed=False)


def entry_probe(index):
 import run131
 from bootstrap import install
 install()
 import common, smoke_screen, run_screen, smoke_validation, compare131
 from arguments131 import probe
 screen=smoke_screen if index==-1 else run_screen.screen
 real_read=common.read;calls=[]
 def read(path):
  if Path(path) in [run131.output(i)/'window.json' for i in range(max(index,0))]:
   return dict(passed=True,device_complete=True,lease_released=True,stop_reasons=[])
  return real_read(path)
 def bridge(argv):
  args=screen.parser().parse_args(argv)
  assert args.authorized_device_window and not args.plan and args.lane=='B'
  assert args.output==run131.output(index)
  expected=run131.view('candidate' if index==-1 else run131.ORDER[index])
  assert args.lineage==expected and args.seal==expected/'screen-seal.json'
  identity=common.sealed(args)
  assert identity['lineage']==str(expected)
  calls.append(dict(argv=argv,seal_sha256=identity['seal_sha256']))
  return probe(index=index)
 with patch.object(common,'read',side_effect=read),patch.object(smoke_validation,'require_smoke'),patch.object(compare131,'load'),patch.object(screen,'main',side_effect=bridge):
  result=run131.main(['--index',str(index),'--output',str(run131.output(index)),'--fault-review','/synthetic/CPU-review.json','--authorized-device-window'])
 assert len(calls)==1 and result['native_exec_intercepted'] and len(result['argv'])==2
 result.update(entry='run131.main',entry_calls=calls,readiness_verified=True,real_complete_oracle=True,service_wrapper_synthetic=True,predecessors_synthetic=index>=0)
 return result


def old_negative():
 parent=P.with_name('packet131-snapshot-banks')
 spec=importlib.util.spec_from_file_location('frozen131_entry',parent/'run131.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
 try:old.main(['--index','-1','--output',str(old.output(-1)),'--authorized-device-window','--fault-review','/synthetic/CPU-review.json'])
 except ValueError as error:
  assert 'unsafe identity path' in str(error)
  return dict(passed=True,refusal=str(error),device_executed=False)
 raise AssertionError('frozen entry did not reproduce the refusal')


def main():
 negative=gate_build_negative();old=old_negative();rows=[]
 for index in range(-1,5):
  cp=subprocess.run([sys.executable,'-B',str(P/'test_gate131b.py'),'--probe',str(index)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=240)
  (P/'evidence'/f'entry131b-{index}.log').write_text(cp.stdout+cp.stderr)
  assert cp.returncode==0,cp.stdout+cp.stderr
  rows.append(json.loads(next(x.removeprefix('ENTRY_RESULT=') for x in cp.stdout.splitlines() if x.startswith('ENTRY_RESULT='))))
  print('run131 entry',index,'PASS: real readiness/oracle to two intercepted native argv',flush=True)
 files=[P/n for n in ('test_gate131b.py','ready131.py','seal131.py','run131.py','source_gate131b.py','oracle_gate131b.py','shared_oracle.py','oracle-binding.json','arguments131.py','evidence/ready131.json')]
 save(P/'evidence/gate131b.json',dict(passed=True,device_executed=False,gate_build_negative=negative,frozen_entry_negative=old,windows=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in files}))

if __name__=='__main__':
 cpu_main()
 if '--probe' in sys.argv:print('ENTRY_RESULT='+json.dumps(entry_probe(int(sys.argv[-1]))))
 else:main()
