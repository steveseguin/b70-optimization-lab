"""Prove the private entry differs only in admission/help and path relocation."""
import difflib,hashlib,json,re
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
for name in ['one-card','two-card']:
 p=P/name;mirror=p/'native-source/repo';r=json.loads((p/'lineage/build-inputs.json').read_text());changes=[]
 for src,wanted in r['source_sha256'].items():
  text=(mirror/src).read_text().replace(str(mirror)+'/',str(ROOT)+'/');original=text
  text=re.sub(r'\n  // PACKET163_HELP_BEGIN:.*?// PACKET163_HELP_END\n','',text,flags=re.S)
  text=text.replace('a.tokens <= 512','a.tokens <= 128').replace('requests.size()<=13','requests.size()<=12')
  assert hashlib.sha256(text.encode()).hexdigest()==wanted,src
  if original!=text:changes.extend(difflib.unified_diff(text.splitlines(True),original.splitlines(True),fromfile='a/'+src,tofile='b/'+src))
 for f,row in r['objects'].items():assert sha(p/f)==row['sha256'],f
 (p/'measurement-admission.patch').write_text(''.join(changes))
 result=dict(passed=True,source_count=len(r['source_sha256']),unchanged_linked_kernel_objects=len(r['objects']),arithmetic='iq3-p49-split32-v1',allowed_deltas=['parser response-cap128->512','one-card suite request-count12->13','pre-device --help metadata','private source and constant path relocation'],device_executed=False,extended_oracle_exactness_claimed=False)
 (p/'evidence/identity-check.json').write_text(json.dumps(result,indent=2)+'\n');print(name,'identity PASS')
