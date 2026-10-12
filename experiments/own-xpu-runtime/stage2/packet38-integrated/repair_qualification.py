"""Narrow fixture-only relink proof; historical executions keep their original hashes."""
import gzip,json,shlex
from pathlib import Path
from seal import sha
P=Path(__file__).resolve().parent;E=P/'evidence/20261012-k2-repair'
def qualified_model_binaries(binaries):
 from build import sources
 archive=E/'prior-seal-and-gates.json.gz'
 prior=json.loads(gzip.decompress(archive.read_bytes()))
 old=json.loads(prior['build-receipt.json'])
 current=sources(); changed=[n for n,h in old['sources'].items() if n.endswith(('.cpp','.hpp')) and current.get(n)!=h]
 assert changed==['experiments/own-xpu-runtime/stage2/packet38-integrated/fixture_driver.cpp'],changed
 assert {n for n in current if n.endswith(('.cpp','.hpp'))}=={n for n in old['sources'] if n.endswith(('.cpp','.hpp'))}
 allowed={'fixture_driver.cpp','k2-class-registry.json','k2_summary.py','test_p38_k2.py','test_window.py','validation_gate.py','window.py','seal.py','draft_window.py','test_draft_window_cleanup.py','test_window_seal_admission.py'}
 assert all(Path(n).parent.name=='packet38-integrated' and Path(n).name in allowed for n,h in old['sources'].items() if current.get(n)!=h),'change outside fixture repair; full model gates required'
 original_objects={}
 with gzip.open(P/'evidence/regenerable-object-hashes.jsonl.gz','rt') as f:
  for line in f:
   row=json.loads(line)
   if row.get('kind')=='file' and row['path'].endswith('.o'):original_objects[row['path']]=row['sha256']
 metadata=json.loads((E/'before-build.json').read_text())['metadata']
 proof={};qualified=dict(binaries)
 for mode in ('gnu-host','icpx-host','asan','device'):
  path=E/('build-'+mode+'.json');r=json.loads(path.read_text())
  assert r['passed'] and not r['device_executed'] and not r['unexpected']
  assert r['fixture_source_sha256']==sha(P/'fixture_driver.cpp')
  assert r['objects'] and all(x['before']==original_objects[x['path']] for x in r['objects'])
  observed={x['path'] for x in r['objects']};assert len(observed)==len(r['objects']),'duplicate object proof'
  link=metadata['build/'+mode+'/CMakeFiles/own-rt-iq3.dir/link.txt']
  required={str(Path('build')/mode/arg) for arg in shlex.split(link) if arg.endswith('.o')}
  assert required and required<=observed,'incomplete model object proof'
  assert all(x['before']==x['after'] for x in r['objects'] if not x['path'].endswith(('entry-k2_fixture.cpp.o','entry-nongemv_fixture.cpp.o')))
  for name,h in r['binaries'].items():assert binaries[mode+'/'+name]==h==sha(P/'build'/mode/name)
  for name,text in metadata.items():
   if name.startswith('build/'+mode+'/'):assert (P/name).read_text()==text
  proof[str(path.relative_to(P))]=sha(path)
  if mode!='device':qualified[mode+'/own-rt-iq3']=old['artifacts_sha256'][mode+'/own-rt-iq3']
 # Only these relink targets may change. Every independent test executable stays exact.
 targets={m+'/'+t for m in ('gnu-host','icpx-host','asan','device') for t in ('own-rt-iq3','k2-fixtures','nongemv-fixtures','p33-linked-fixtures')}|{'device/jit-smoke'}
 assert all(h==old['artifacts_sha256'][n] for n,h in binaries.items() if n not in targets)
 result=dict(passed=True,device_executed=False,scope='Historical model CPU arithmetic/controller/suite evidence carried across fixture-only relink; not a new execution of those gates',
  prior_archive_sha256=sha(archive),proof_receipts_sha256=proof,
  source_delta=changed,link_commands_unchanged=True,
  model_binary_mapping={m:dict(executed_sha256=qualified[m+'/own-rt-iq3'],current_sha256=binaries[m+'/own-rt-iq3']) for m in ('gnu-host','icpx-host','asan')},
  excluded='Fixture arithmetic/validation, resident QSA arithmetic, wrapper and seal admission rerun; no old device window admitted',
  limitation='Object/code equivalence is not a fresh full-model execution of the relinked executable; coordinator device qualification remains mandatory')
 out=E/'model-gate-carry-forward.json';out.write_text(json.dumps(result,indent=2)+'\n')
 return qualified,dict(path=str(out.relative_to(P)),sha256=sha(out),**result)
