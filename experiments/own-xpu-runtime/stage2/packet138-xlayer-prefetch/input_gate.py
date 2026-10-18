"""Read-only fixed-input and every-token reference check for this diagnostic."""
import json,shutil
from pathlib import Path
from shared_oracle import completed_binding,sha,ROOT,P

def validate_manifest(manifest):
 completed_binding()
 assert manifest['arithmetic']=='iq3-p49-split32-v1' and manifest['token_cap']==48
 assert len(manifest['prompts'])==13 and [e['split'] for e in manifest['prompts']]==['sanity']+['test']*12
 for name,digest in manifest['sources'].items():assert sha(ROOT/name)==digest,name
 for e in manifest['prompts']:
  assert len(e['expected_tokens'])==48 and e['analysis_included']==(e['split']=='test')
  assert sha(ROOT/e['reference'])==e['reference_sha256']
  expected=json.loads((ROOT/e['reference']).read_text())['tokens'][:48]
  assert expected==e['expected_tokens']
  for name,digest in e['input_bundle_hashes'].items():assert sha(ROOT/e['input_bundle']/name)==digest
 return manifest

def admit_inputs(entries,output,unused):
 manifest=validate_manifest(json.loads((P/'suite.snapshot.json').read_text()))
 assert entries==manifest['prompts']
 snapshots={};first=None
 for e in entries:
  base=ROOT/e['input_bundle'];dest=output/'input-bundles'/e['prompt_id'];dest.mkdir(parents=True)
  for name in e['input_bundle_hashes']:shutil.copyfile(base/name,dest/name)
  inp=json.loads((dest/'input.json').read_text());tokens=list(map(int,(dest/'tokens.txt').read_text().split()))
  assert inp['tokens']==tokens and len(tokens)==e['prompt_tokens']
  identity=(e['input_bundle_hashes']['plan.tsv'],e['input_bundle_hashes']['identity.tsv'],inp['model_dir'])
  if first is None:first=identity
  assert first==identity
  snapshots[e['prompt_id']]=(dest,tokens)
 return snapshots
