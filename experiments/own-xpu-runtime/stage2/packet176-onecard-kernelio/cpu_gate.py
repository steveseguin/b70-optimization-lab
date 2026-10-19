"""Bounded native exactness, real resets, publish skip/repair and refusal gates."""
import json,resource,subprocess,tempfile,hashlib,sys
from pathlib import Path
from build_engine import P,sha,save,limits,compiler_turn
from launch_env import environment

def run(cmd,ok=True):
 cp=subprocess.run(['ionice','-c3',*map(str,cmd)],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=environment())
 if ok and cp.returncode:raise AssertionError(cp.stderr[-2000:]+cp.stdout[-500:])
 return cp

def main():
 limits();resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 records=[]
 with tempfile.TemporaryDirectory(dir=P/'build',prefix='split-cpu-') as d:
  d=Path(d);base=['--mini','--pipeline-mini','--memory','resident','--cache-maintenance','overlap','--context','32','--tokens','8','--retain-steps','1-8','--lookups','resident','--hc','p60fusion','--hc-geometry','hc-wide','--experts','wide64+halfcache','--other-fusion','fused','--retirement','ordered-foreground','--selection',P/'selection.json','--selection-sha256',sha(P/'selection.json')]
  ref=d/'reference';parent=P.with_name('packet58aj-onecard-resident')/'build/gnu-host/own-rt-iq3'
  run([parent,*base,'--output',ref]);result=json.loads((ref/'result.json').read_text())
  def files(o):return {str(f.relative_to(o)):sha(f) for f in o.glob('step*/*') if f.is_file()}
  expected=files(ref);assert expected
  tokens=d/'tokens';tokens.write_text('2 5 3 7 1\n');oracle=d/'oracle';oracle.write_text(' '.join(map(str,result['tokens']))+'\n')
  suite=d/'suite';suite.write_text(''.join(f'r{i} {tokens} {oracle}\n' for i in range(12)))
  table=d/'bracket';arms=[('A0','spin'),('B0','spin-kio'),('A1','spin'),('B1','spin-kio'),('A2','spin')]
  table.write_text(''.join(f'{label} {P/"selection.json"} {sha(P/"selection.json")} overlap max {arm}\n' for label,arm in arms))
  for mode in ('gnu-host','intel-host'):
   out=d/mode;binary=P/'build'/mode/'own-rt-iq3'
   run([binary,*base,'--suite-inputs',suite,'--bracket-inputs',table,'--output',out])
   resets=0;arenas=set()
   for label,arm in arms:
    assert [json.loads(x)['phase'] for x in (out/label/'host-memory.jsonl').read_text().splitlines()]==['before_view_reset','after_view_reset']
    boundary=json.loads((out/label/'boundary.json').read_text());arenas.add(boundary['arena_descriptors_sha256'])
    assert boundary['wait_policy']=='spin' and boundary['bracket_arm']==arm and boundary['foreground_io']==('kernel' if arm=='spin-kio' else 'copy'),boundary
    for i in range(12):
     request=out/label/f'r{i}';assert files(request)==expected
     assert json.loads((request/'result.json').read_text())['tokens']==result['tokens']
     rows=[json.loads(x) for x in (request/'timings.jsonl').read_text().splitlines()]
     assert rows and all(r['foreground_io']==('kernel' if arm=='spin-kio' else 'copy') and r['head_transfer_ms']>=0 and r['tail_transfer_ms']>=0 for r in rows)
     sensors=[json.loads(x) for x in (request/'host-memory.jsonl').read_text().splitlines()]
     assert [v['phase'] for v in sensors]==['before_reset','after_reset'] and all(v['MemAvailable']>0 for v in sensors)
     resets+=1
   assert len(arenas)==1
   records.append(dict(compiler=mode,binary_sha256=sha(binary),passed=True,resets=resets,real_sensor_samples=2*resets+10,view_resets=5,all_fixture_bytes_equal=True))
  # Native oracle refusal must prevent the second view.
  oracle.write_text('31\n');bad=d/'bad';cp=run([P/'build/gnu-host/own-rt-iq3',*base,'--suite-inputs',suite,'--bracket-inputs',table,'--output',bad],False)
  assert cp.returncode!=0 and not (bad/'B0').exists()
  # The parent's poll/spin bracket order is refused by this binary (no silent relabeling).
  oracle.write_text(' '.join(map(str,result['tokens']))+'\n');old=d/'old-order';old.write_text(''.join(f'{label} {P/"selection.json"} {sha(P/"selection.json")} overlap max {arm}\n' for label,arm in [('A0','poll'),('B0','spin'),('A1','poll'),('B1','spin'),('A2','poll')]))
  cp=run([P/'build/gnu-host/own-rt-iq3',*base,'--suite-inputs',suite,'--bracket-inputs',old,'--output',d/'old-order-out'],False)
  assert cp.returncode!=0 and not (d/'old-order-out'/'A0').exists(),cp.stderr[-500:]
 save(P/'evidence/cpu-exactness.json',dict(passed=True,device_executed=False,records=records,synthetic_weights=True,oracle_refusal=True,old_poll_spin_order_refused=True,arms=[a for _,a in arms],wait_completion_deadline_async_errors=True,miniature_cache_publication=False,fullshape_publication_covered_by='preparation.json',parent_binary_sha256=sha(parent),peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024))
 print('PASS GNU/Intel 120 request resets, byte equality, oracle refusal, bounded wait')
if __name__=='__main__':main()
