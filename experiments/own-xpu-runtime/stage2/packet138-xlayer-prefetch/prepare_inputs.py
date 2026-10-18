"""Pin held-out packet55 inputs and saved target tokens; no tokenizer/model load."""
import hashlib,json,os,resource,shutil
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
from shared_oracle import completed_binding
S=P.parent/'packet55-feasibility/route'
def main():
 limits();completed_binding()
 manifest=json.loads((S/'build/calibration-tokenized.json').read_text())
 original=json.loads((S/'calibration-prompts.json').read_text())
 assert manifest['source_sha256']==sha(S/'calibration-prompts.json') and manifest['benchmark_prompt_overlap'] is False
 baseline=json.loads((P.parent/'packet100b-route-capture/suite.snapshot.json').read_text())['prompts'][0]
 base=ROOT/baseline['input_bundle'];entries=[];sources={}
 for f in (S/'calibration-prompts.json',S/'build/calibration-tokenized.json'):sources[str(f.relative_to(ROOT))]=sha(f)
 def add(row,tokens,reference,kind,category):
  name=row['prompt_id'];dest=P/'inputs'/name;dest.mkdir(parents=True,exist_ok=True)
  for leaf in ('plan.tsv','identity.tsv','vocab.bin'):
   d=dest/leaf
   if not d.exists():d.symlink_to(os.path.relpath(base/leaf,dest))
  inp=json.loads((base/'input.json').read_text());inp['tokens']=tokens
  (dest/'input.json').write_text(json.dumps(inp,indent=2)+'\n');(dest/'tokens.txt').write_text(' '.join(map(str,tokens))+'\n')
  ref=json.loads(reference.read_text());assert ref.get('passed',True) and len(ref['tokens'])>=48
  sources[str(reference.relative_to(ROOT))]=sha(reference)
  entries.append(dict(prompt_id=name,category=category,split=kind,analysis_included=kind=='test',prompt_tokens=len(tokens),
   input_bundle=str(dest.relative_to(ROOT)),input_bundle_hashes={n:sha(dest/n) for n in ('plan.tsv','identity.tsv','vocab.bin','input.json','tokens.txt')},
   expected_tokens=ref['tokens'][:48],reference=str(reference.relative_to(ROOT)),reference_sha256=sha(reference),
   reference_kind='packet49 CPU oracle' if kind=='sanity' else 'packet55 saved target, same arithmetic; not independent CPU oracle'))
 add(baseline,list(map(int,(base/'tokens.txt').read_text().split())),ROOT/baseline['oracle_directory']/'result.json','sanity','operations')
 for row,source in zip(manifest['prompts'],original['prompts']):
  assert row['text']==source['text'] and row['split']==source['split']
  if row['split']!='test':continue
  tokens=row['tokens'];assert tokens!=list(map(int,(base/'tokens.txt').read_text().split()))
  add(row,tokens,S/'evidence/cards23-a/requests'/row['prompt_id']/'result.json','test',row['category'])
 assert len(entries)==13 and sum(e['analysis_included'] for e in entries)==12
 save(P/'suite.snapshot.json',dict(schema='packet138.heldout.v1',arithmetic='iq3-p49-split32-v1',token_cap=48,context=4096,diagnostic_only=True,benchmark_training=False,prompts=entries,sources=sources))
 print('12 held-out inputs + separate p49 sanity pinned; 48 tokens each')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
