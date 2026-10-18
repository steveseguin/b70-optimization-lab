"""Read-only packet49 authority verification, kept outside source-map resolution."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
ORACLE=P.parent/'packet49-integrate/oracle'
def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def completed_binding():
 binding=read(P/'oracle-binding.json')
 assert binding['arithmetic']=='iq3-p49-split32-v1'
 for name,digest in binding['files_sha256'].items():assert sha(ROOT/name)==digest,name
 assert sha(ORACLE/'results/completion.json')==binding['completion_sha256']
 c=read(ORACLE/'results/completion.json')
 assert c['passed'] and not c['device_executed'] and c['arithmetic']==binding['arithmetic'] and c['prompts']==12 and c['token_cap']==128
 for key,leaf in [('manifest_sha256','suite-manifest.json'),('determinism_sha256','determinism.json'),('kd_capture_sha256','kd-capture.json'),('old_v_new_sha256','old-v-new.json')]:assert sha(ORACLE/'results'/leaf)==c[key],leaf
 assert sha(ORACLE/'build-receipt.json')==c['build_receipt_sha256']
 manifest=read(ORACLE/'results/suite-manifest.json')
 assert manifest['complete'] and manifest['arithmetic']==binding['arithmetic']
 for e in manifest['prompts']:
  for name,digest in e['input_bundle_hashes'].items():assert sha(ROOT/e['input_bundle']/name)==digest
  d=ORACLE/'results'/e['prompt_id'];assert sha(d/'receipt.json')==e['oracle_receipt_sha256']
  r=read(d/'receipt.json');assert r['verified']
  assert sha(d/'result.json')==r['result_sha256'] and sha(d/'validation.json')==r['validation_sha256']
 return dict(passed=True,device_executed=False,arithmetic=binding['arithmetic'],completion_sha256=binding['completion_sha256'],prompts=12)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--require-complete',action='store_true');parser.parse_args()
 print(json.dumps(completed_binding()))
