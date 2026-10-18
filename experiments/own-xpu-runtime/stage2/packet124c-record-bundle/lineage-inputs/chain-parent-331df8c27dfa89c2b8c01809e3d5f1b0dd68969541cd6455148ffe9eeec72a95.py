#!/usr/bin/env python3
"""No-rank tempfile-only export/cleanup coverage, including nested state evidence."""
import base64,gzip,hashlib,json,shutil,tempfile,types
from pathlib import Path
import pipeline,storage,suite,suite_export,seal
P=Path(__file__).resolve().parent

def main():
 checks=[]
 with tempfile.TemporaryDirectory(prefix='review-suite-retention-',dir=P/'build') as temporary:
  root=Path(temporary);run=root/'suite-run';run.mkdir()
  expected=list(suite.checker_module().PROMPT_IDS);prompt=expected[0]
  oracle=root/'oracle';oracle.mkdir()
  manifest=dict(arithmetic='iq3-p17-detmath-v2',token_cap=64,complete=False,prompts=[dict(prompt_id=prompt,oracle_directory=str(oracle),generated_tokens=64)])
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
  fixture_names=[f'step{i}/layer-{j:02}.bf16' for i in range(1,9) for j in range(48)]
  for base in (oracle,output):
   for name in fixture_names:
    file=base/name;file.parent.mkdir(exist_ok=True);file.write_bytes(b'exact-fixture')
  full_tokens=[7]*64;oracle_auth_calls=[]
  def authenticate(actual,reference,entry,repo):
   assert actual==reference==oracle and entry['generated_tokens']==64
   oracle_auth_calls.append(True);return 64,384
  def fixture_inventory(base,count):
   return {name:pipeline.sha(base/name) for name in fixture_names if int(Path(name).parts[0][4:])<=min(count,8)}
  checker=types.SimpleNamespace(PROMPT_IDS=tuple(expected),__file__=str(checker_source),source_sha256=pipeline.sha(checker_source),
       check_prompt=authenticate,token_record=lambda base:full_tokens if base==oracle else json.loads((base/'receipt.json').read_text())['tokens'],fixture_inventory=fixture_inventory)
  coverage=suite_export.frozen_coverage(manifest,checker,{})
  assert not coverage['complete']
  for bad in [dict(manifest,complete=True),dict(manifest,prompts=manifest['prompts']*2),dict(manifest,suite_sha256='a'*64)]:
   try:suite_export.frozen_coverage(bad,checker,dict(suite_sha256='b'*64))
   except ValueError:pass
   else:raise AssertionError('invalid frozen coverage admitted')
  complete=dict(complete=True,prompts=[dict(prompt_id=n) for n in expected],suite_sha256='a'*64,prompts_manifest_sha256='b'*64)
  assert suite_export.frozen_coverage(complete,checker,complete)['complete']
  checks.append('partial complete duplicate and frozen identity coverage guarded')
  receipt=dict(schema='own-runtime.iq3.packet26.run.v1',device_executed=False,passed=True,oracle_check=dict(passed=True,checker_sha256=checker.source_sha256),rank_trace=[dict(rank=r,op=pipeline.HALF) for r in (0,1)],tokens=[7]*8,requested_max_new=8,retain_steps='1-8',binary_sha256='f'*64,stats={},controller='native',draft='mtp')
  pipeline.save(output/'receipt.json',receipt)
  pipeline.save(run/'summary.json',dict(device_executed=False,passed=True,manifest_sha256=pipeline.sha(run/'suite-manifest.snapshot.json'),requested_max_new=8,rows=[dict(prompt_id=prompt,repeat=1,tokens=8,requested_max_new=8,receipt=str((output/'receipt.json').relative_to(run)))]))
  pipeline.save(run/'input-admission.json',dict(passed=True))
  for rank in (0,1):
   (run/f'ranks/rank{rank}').mkdir(parents=True)
   pipeline.save(run/f'ranks/rank{rank}-launch.json',dict(device_executed=False,pid=100+rank,argv=[str(P/'build/icpx-host/own-rt-iq3'),'--max-new','8']))
   pipeline.save(run/f'ranks/rank{rank}/receipt.json',dict(passed=True,rank=rank,teardown=[dict(safe_to_exit=True,live_bytes=0,in_flight=0)]))
  original=suite.checker_module;suite.checker_module=lambda:checker
  identity_original=suite_export.cpu_suite_identity
  suite_export.cpu_suite_identity=lambda:dict(host_compiler='icpx-host',binary_relative_to_build='icpx-host/own-rt-iq3',binary_sha256='f'*64)
  try:
   exported=suite_export.export_run(run,root/'export.json')
   assert exported['rows'][0]['state_evidence_sha256']==bound['state_evidence_sha256'] and not exported['complete_frozen_suite']
   assert exported['host_compiler']=='icpx-host' and exported['binary_relative_to_build']=='icpx-host/own-rt-iq3'
   assert exported['requested_max_new']==8 and exported['oracle_token_cap']==64 and exported['prefix_only'] and not exported['full_oracle_generation']
   assert exported['token_count']==8 and exported['fixture_files']==384 and oracle_auth_calls
   checks.append('eight-token prefix authenticates full64 oracle and every384 fixture bytes')
   def refused(label):
    try:suite_export.export_run(run,root/'refused.json')
    except (ValueError,AssertionError):pass
    else:raise AssertionError('admitted '+label)
    checks.append(label+' refused')
   for label,delta in [('truncated prefix',dict(tokens=[7]*7)),('extra token',dict(tokens=[7]*9)),('changed token',dict(tokens=[8]+[7]*7)),('request cap mismatch',dict(requested_max_new=7)),('missing fixtures selector',dict(retain_steps='none'))]:
    pipeline.save(output/'receipt.json',dict(receipt,**delta));refused(label)
   pipeline.save(output/'receipt.json',receipt)
   summary_path=run/'summary.json';good_summary=json.loads(summary_path.read_text())
   for value in (0,65,True):
    pipeline.save(summary_path,dict(good_summary,requested_max_new=value));refused('invalid summary cap '+str(value))
   pipeline.save(summary_path,good_summary)
   launch=run/'ranks/rank0-launch.json';good_launch=json.loads(launch.read_text())
   for args in (['--max-new','7'],[],['--max-new','8','--tokens','8']):
    pipeline.save(launch,dict(good_launch,argv=[good_launch['argv'][0],*args]));refused('missing differing or duplicate launch cap '+str(args))
   pipeline.save(launch,good_launch)
   file=output/fixture_names[0];good_fixture=file.read_bytes();file.write_bytes(b'changed');refused('fixture hash mismatch');file.write_bytes(good_fixture)
   # Even equal untrusted inventory hashes cannot bypass the byte comparison.
   saved_inventory=checker.fixture_inventory
   checker.fixture_inventory=lambda base,count:saved_inventory(oracle,count)
   file.write_bytes(b'changed');refused('fixture byte mismatch under matching reported hashes');file.write_bytes(good_fixture)
   checker.fixture_inventory=saved_inventory
   saved_auth=checker.check_prompt
   def bad_oracle(*args):raise ValueError('oracle receipt binding differs')
   checker.check_prompt=bad_oracle;refused('full oracle authentication failure');checker.check_prompt=saved_auth
   # Full-cap export remains supported, distinctly labeled.
   pipeline.save(output/'receipt.json',dict(receipt,tokens=full_tokens,requested_max_new=64))
   full_summary=dict(good_summary,requested_max_new=64,rows=[dict(good_summary['rows'][0],requested_max_new=64,tokens=64)])
   pipeline.save(summary_path,full_summary)
   for rank in (0,1):
    file=run/f'ranks/rank{rank}-launch.json';data=json.loads(file.read_text());data['argv'][-1]='64';pipeline.save(file,data)
   full=suite_export.export_run(run,root/'full.json');assert full['token_count']==64 and full['full_oracle_generation'] and not full['prefix_only'];checks.append('full64 generation remains distinct from prefix and prompt completeness')
   seal.require_full_cpu_suite(full);checks.append('full64 meets inherited seal response scope')
   for row in (exported,dict(exported,prefix_only=False,full_oracle_generation=True),dict(full,prefix_only=True)):
    try:seal.require_full_cpu_suite(row)
    except AssertionError:pass
    else:raise AssertionError('prefix or contradictory coverage qualified inherited suite')
   checks.append('seal refuses diagnostic8 even with forged full-generation flags')
   pipeline.save(output/'receipt.json',receipt);pipeline.save(summary_path,good_summary)
   for rank in (0,1):
    file=run/f'ranks/rank{rank}-launch.json';data=json.loads(file.read_text());data['argv'][-1]='8';pipeline.save(file,data)
   for targets in [(0,),(0,1)]:
    for rank in targets:pipeline.save(run/f'ranks/rank{rank}-launch.json',dict(device_executed=False,pid=100+rank,argv=[str(P/'build/gnu-host/own-rt-iq3'),'--max-new','8']))
    try:suite_export.export_run(run,root/'wrong-compiler.json')
    except ValueError:pass
    else:raise AssertionError('wrong or mixed compiler rank launch admitted')
    for rank in targets:pipeline.save(run/f'ranks/rank{rank}-launch.json',dict(device_executed=False,pid=100+rank,argv=[str(P/'build/icpx-host/own-rt-iq3'),'--max-new','8']))
   checks.extend(['mixed rank compiler paths refused','GNU-only suite compiler refused'])
   wrong=dict(receipt,binary_sha256='0'*64);pipeline.save(output/'receipt.json',wrong)
   try:suite_export.export_run(run,root/'wrong-binary.json')
   except ValueError:pass
   else:raise AssertionError('request binary differs from qualified Intel binary')
   pipeline.save(output/'receipt.json',receipt);checks.append('request binary hash mismatch refused')
   assert pipeline.sha(P/exported['export_checker_snapshot'])==exported['export_checker_sha256']
   teardown=run/'ranks/rank0/receipt.json';good=teardown.read_bytes();pipeline.save(teardown,dict(passed=True,rank=0,teardown=[]))
   try:suite_export.export_run(run,root/'invalid.json')
   except ValueError:pass
   else:raise AssertionError('empty teardown accepted')
   teardown.write_bytes(good)
  finally:suite.checker_module=original;suite_export.cpu_suite_identity=identity_original
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
 result=dict(passed=True,device_executed=False,native_ranks_executed=False,synthetic_export_only=True,checks=checks,source_sha256={n:pipeline.sha(P/n) for n in ['storage.py','cleanup.py','suite_export.py','cpu_campaign.py','seal.py','test_suite_export_retention.py']})
 pipeline.save(P/'suite-export-retention-gates.json',result);print(json.dumps(result))
if __name__=='__main__':main()
