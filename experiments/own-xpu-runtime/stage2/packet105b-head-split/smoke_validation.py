"""Verify all twelve smoke receipts, exact seal, drain and known suffix token."""
import json
from types import SimpleNamespace
from build_engine import P,ROOT,sha
def require_smoke():
 from device_gate import require_micro
 micro=require_micro()
 from screen_jobs import view,smoke_output,SMOKE_CHOICE
 from bootstrap import install
 install()
 from common import sealed,D,compare_tokens
 root=smoke_output();window=json.loads((root/'window.json').read_text());actual=json.loads((root/'identity.json').read_text())
 lineage=view(SMOKE_CHOICE)
 expected=sealed(SimpleNamespace(lineage=lineage,seal=lineage/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement='1'))
 assert all(actual.get(k)==v for k,v in expected.items())
 assert actual['lane']=='B' and window['identity']==actual
 assert window['passed'] and window['device_executed'] and window['device_complete'] and window['lease_released']
 assert not window.get('child_still_running') and not window.get('child_retained') and not window.get('stop_reasons')
 manifest=D.oracle_inputs();prompts=[e['prompt_id'] for e in manifest['prompts']];assert len(prompts)==12
 files=['identity.json','summary.json','run/teardown.json','suite-manifest.snapshot.json']+['run/'+pid+'64/receipt.json' for pid in prompts]
 for leaf in files:assert window['files'][leaf]==sha(root/leaf),leaf
 assert json.loads((root/'suite-manifest.snapshot.json').read_text())==manifest
 result=json.loads((root/'summary.json').read_text())
 assert result['passed'] and result['smoke'] and result['request_count']==12 and result['tokens']==64 and result['target_suffix_winners']>0
 assert [r['prompt_id'] for r in result['requests']]==prompts
 for request in result['requests']:
  assert request['passed'] and request['exact_oracle'] and request['cached_tokens']==0 and request['repeat']==1
  compare_tokens(request['tokens'],D.CHECK.token_record(D.ORACLE/'results'/request['prompt_id']),64,request['prompt_id'])
 assert next(r for r in result['requests'] if r['prompt_id']=='architecture-tradeoff')['tokens'][30]==215495
 if 'draft-split' in SMOKE_CHOICE:assert result['draft_suffixes']>0
 assert json.loads((root/'run/teardown.json').read_text())['drained']
 coordination=json.loads((root/'lane-coordination.json').read_text());assert coordination['passed'] and coordination['released_before_report']
 return dict(passed=True,path=str(root),window_sha256=sha(root/'window.json'),micro=micro)
if __name__=='__main__':print(json.dumps(require_smoke(),sort_keys=True))
