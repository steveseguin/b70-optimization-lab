"""CPU-only recovery receipt tests; no native oracle or model evaluation."""
import json,shutil
from pathlib import Path
import long_run as m
from summarize_costs import summarize
H=m.HERE

def main():
 m.disk_guard();scratch=H/'.recovery-test.partial';scratch.mkdir();checks=[]
 try:
  attempt=scratch/'attempt';d=attempt/'native';d.mkdir(parents=True)
  m.save(d/'result.json',dict(next_position=3))
  (d/'timings.jsonl').write_text('{"label":"unfinished diagnostic"}\n')
  prior=dict(elapsed_seconds=1.,cpu_seconds=2.)
  m.finalize_partial_logs(d,attempt,prior)
  ledger=m.read(d/'log-retention.json');assert len(ledger)==1 and next(iter(ledger.values()))['end_position']==3
  assert not (d/'timings.jsonl').exists() and m.timing_complete(prior)
  m.save(d/'result.json',dict(next_position=2));assert next(iter(m.read(d/'log-retention.json').values()))['end_position']==3
  checks.append('Interrupted logs bind the pre-rollback endpoint and cannot become unbound .interrupted files')
  assert not m.timing_complete(dict(elapsed_seconds=1.))
  assert not m.timing_complete(dict(elapsed_seconds=1.,cpu_seconds=2.,prior_attempt={"status":"running"}))
  checks.append('Missing timing in any attempt remains incomplete')
  # Exercise the actual completed-partial return branch without launching a process.
  old_here,old_preflight=m.HERE,m.preflight
  try:
   m.HERE=scratch;build=m.read(H/'build-receipt.json');m.preflight=lambda:build
   attempt=scratch/'.TEST.partial';d=attempt/'native';d.mkdir(parents=True)
   bundle=m.INPUTS/'LONG-A'
   m.save(attempt/'receipt.json',dict(binary_sha256=build['binary_sha256'],input_sha256=m.sha(bundle/'input.json')))
   m.save(d/'result.json',dict(status='token-cap',next_position=629));(d/'teardown.json').write_text('[]')
   (d/'timings.jsonl').write_text('')
   assert m.launch('TEST',bundle,32)==d
   assert not m.read(attempt/'receipt.json')['timing_complete']
   assert next(iter(m.read(d/'log-retention.json').values()))['end_position']==629
   checks.append('Completed partial recovery archives final logs and labels unavailable timing')
  finally:m.HERE,m.preflight=old_here,old_preflight
  # A rolled-back position is replaced by the later complete forward pass.
  d=scratch/'summary';d.mkdir();m.save(d/'result.json',dict(next_position=3))
  m.save(d/'receipt.json',dict(verified=True,result_sha256=m.sha(d/'result.json')))
  (d/'positions.jsonl').write_text(''.join(json.dumps(dict(position=i,seconds=1.))+"\n" for i in range(3)))
  def forward(ms):
   rows=[dict(label='begin.0',wall_ms=ms)]
   for layer in range(3,48,4):
    rows.extend(dict(label=f'{layer}.qsa.{op}',wall_ms=ms) for op in ('pool','select','attention'))
   rows.append(dict(label='commit.final',wall_ms=ms));return ''.join(json.dumps(r)+'\n' for r in rows)
  old=d/'timings.jsonl';old.write_text(forward(1)+forward(1)+forward(1)+json.dumps(dict(label='begin.0',wall_ms=999))+'\n')
  m.archived_logs(d,True)
  old.write_text(forward(2));m.archived_logs(d,True)
  report=summarize(d);assert report['positions']==3
  assert abs(report['bins'][0]['qsa_attention_seconds']-.016)<1e-12
  checks.append('Cost summary drops an uncommitted position and uses later recomputed timing')
  m.save(H/'recovery-tests.json',dict(passed=True,numerical_oracle_executed=False,checks=checks))
  print(json.dumps(checks,indent=2))
 finally:shutil.rmtree(scratch)
if __name__=='__main__':main()
