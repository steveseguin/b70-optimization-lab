#!/usr/bin/env python3
"""No-rank tempfile-only export/cleanup coverage, including nested state evidence."""
import base64,gzip,hashlib,json,shutil,tempfile,types
from pathlib import Path
import pipeline,storage,suite,suite_export
P=Path(__file__).resolve().parent

def main():
 checks=[]
 with tempfile.TemporaryDirectory(prefix='review-suite-retention-',dir=P/'build') as temporary:
  root=Path(temporary);run=root/'suite-run';run.mkdir()
  expected=list(suite.checker_module().PROMPT_IDS);prompt=expected[0]
  manifest=dict(arithmetic='iq3-p17-detmath-v2',complete=False,prompts=[dict(prompt_id=prompt,oracle_directory='unused')])
  pipeline.save(run/'suite-manifest.snapshot.json',manifest)
  output=run/'repeat-1'/prompt;output.mkdir(parents=True)
  for rank in (0,1):
   state=output/f'rank{rank}/state-2147483647';state.mkdir(parents=True)
   data=b'exact target '+bytes([rank]);(state/'x.bin').write_bytes(data)
   pipeline.save(state/'state.json',dict(buffers={'x':hashlib.sha256(data).hexdigest()}))
   pipeline.save(output/f'rank{rank}/request-state-inventory.json',dict(standalone_target_mutable={'scratch':dict(bytes=4,sha256='0'*64)},loaded_layer=[-1]))
   (output/f'rank{rank}/timings.jsonl').write_text('{}\n')
   fixture=output/f'rank{rank}/step1/layer-00.bf16';fixture.parent.mkdir();fixture.write_bytes(b'fixture')
  retention=suite.retain_request_state(output);pipeline.save(output/'state-retention.json',retention)
  bound=suite_export.retained_state_binding(output);assert bound['retained_state_files']==6 and set(bound['runtime_state_inventory_sha256'])=={'0','1'}
  checks.append('state archive and both runtime inventories bound')
  checker_source=root/'checker.py';checker_source.write_text('# exact snapshot\n')
  checker=types.SimpleNamespace(PROMPT_IDS=tuple(expected),__file__=str(checker_source),source_sha256=pipeline.sha(checker_source),
       check_prompt=lambda *unused:(64,384),fixture_inventory=lambda *unused:{'fixture':'a'*64})
  coverage=suite_export.frozen_coverage(manifest,checker,{})
  assert not coverage['complete']
  for bad in [dict(manifest,complete=True),dict(manifest,prompts=manifest['prompts']*2),dict(manifest,suite_sha256='a'*64)]:
   try:suite_export.frozen_coverage(bad,checker,dict(suite_sha256='b'*64))
   except ValueError:pass
   else:raise AssertionError('invalid frozen coverage admitted')
  complete=dict(complete=True,prompts=[dict(prompt_id=n) for n in expected],suite_sha256='a'*64,prompts_manifest_sha256='b'*64)
  assert suite_export.frozen_coverage(complete,checker,complete)['complete']
  checks.append('partial complete duplicate and frozen identity coverage guarded')
  receipt=dict(schema='own-runtime.iq3.packet26.run.v1',device_executed=False,passed=True,oracle_check=dict(passed=True,checker_sha256=checker.source_sha256),rank_trace=[dict(rank=r,op=pipeline.HALF) for r in (0,1)],tokens=[7]*64,binary_sha256='f'*64,stats={},controller='native',draft='mtp')
  pipeline.save(output/'receipt.json',receipt)
  pipeline.save(run/'summary.json',dict(device_executed=False,passed=True,manifest_sha256=pipeline.sha(run/'suite-manifest.snapshot.json'),rows=[dict(prompt_id=prompt,repeat=1,receipt=str((output/'receipt.json').relative_to(run)))]))
  pipeline.save(run/'input-admission.json',dict(passed=True))
  for rank in (0,1):
   (run/f'ranks/rank{rank}').mkdir(parents=True)
   pipeline.save(run/f'ranks/rank{rank}-launch.json',dict(device_executed=False,pid=100+rank))
   pipeline.save(run/f'ranks/rank{rank}/receipt.json',dict(passed=True,rank=rank,teardown=[dict(safe_to_exit=True,live_bytes=0,in_flight=0)]))
  original=suite.checker_module;suite.checker_module=lambda:checker
  try:
   exported=suite_export.export_run(run,root/'export.json')
   assert exported['rows'][0]['state_evidence_sha256']==bound['state_evidence_sha256'] and not exported['complete_frozen_suite']
   assert pipeline.sha(P/exported['export_checker_snapshot'])==exported['export_checker_sha256']
   teardown=run/'ranks/rank0/receipt.json';good=teardown.read_bytes();pipeline.save(teardown,dict(passed=True,rank=0,teardown=[]))
   try:suite_export.export_run(run,root/'invalid.json')
   except ValueError:pass
   else:raise AssertionError('empty teardown accepted')
   teardown.write_bytes(good)
  finally:suite.checker_module=original
  checks.append('full synthetic export binds state and checker; empty teardown refused')
  raw_archive=output/'state-evidence.json.gz';original_nested=raw_archive.read_bytes()
  archive=root/'retained.jsonl.gz';result=storage.archive_files([f for f in run.rglob('*') if f.is_file()],archive)
  verified=storage.verify_archive(archive);assert verified['files']==result['files']
  nested=bytearray();collect=False
  with gzip.open(archive,'rt') as source:
   for line in source:
    row=json.loads(line)
    if row.get('kind')=='file':collect=row['path']==str(raw_archive.relative_to(P))
    elif row.get('kind')=='chunk' and collect:nested.extend(base64.b64decode(row['base64']))
    elif row.get('kind')=='end':collect=False
  assert bytes(nested)==original_nested
  assert json.loads(gzip.decompress(nested))['files']
  checks.append('streaming archive retains exact nested gzip metadata bytes')
  # Exercise discard with the same archive helper without leaving artifacts.
  disposable=root/'disposable';disposable.mkdir();(disposable/'state.json.gz').write_bytes(original_nested)
  saved_p,saved_b=storage.P,storage.B;storage.P=root;storage.B=root
  try:
   deleted=storage.discard(disposable);assert not disposable.exists()
   storage.verify_archive(root/deleted['path'])
  finally:storage.P,storage.B=saved_p,saved_b
  checks.append('discard removes scratch only after verified archive')
  tampered=root/'truncated.jsonl.gz'
  with gzip.open(tampered,'wt') as target:
   target.write(json.dumps({'schema':'packet38.scratch-stream.v1'})+'\n')
   target.write(json.dumps(dict(kind='file',path='x',bytes=1,sha256='0'*64,retained=True))+'\n')
  try:storage.verify_archive(tampered)
  except ValueError:pass
  else:raise AssertionError('truncated member accepted')
  checks.append('truncated archive refused')
 result=dict(passed=True,device_executed=False,native_ranks_executed=False,synthetic_export_only=True,checks=checks,source_sha256={n:pipeline.sha(P/n) for n in ['storage.py','cleanup.py','suite_export.py','cpu_campaign.py','test_suite_export_retention.py']})
 pipeline.save(P/'suite-export-retention-gates.json',result);print(json.dumps(result))
if __name__=='__main__':main()
