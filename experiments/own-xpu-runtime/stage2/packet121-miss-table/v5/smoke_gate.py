"""Exact smoke receipts, never a speed claim. Safe for runtime import."""
from pathlib import Path
from common import HERE,ROOT,D,read,require,sha
OUTPUT=HERE/'evidence/device-smoke-B'
def check_views(output,identity):
 proof=read(output/'run/bracket-inputs.json')
 require(proof.get('passed') is True and proof.get('kind')=='smoke','smoke proof missing')
 views=proof['views'];require(len(views)==3,'three smoke views required')
 descriptors=None
 for i,(view,selected) in enumerate(zip(views,identity['bracket']['views'])):
  require(view['passed'] is True and view['index']==i and view['choice']==selected['choice'] and view['selection_sha256']==selected['selection_sha256'],'smoke selection differs')
  dest=output/'run/views'/f'{i:02d}-{view["choice"]}'
  require(view['output']==str(dest),'smoke output escapes')
  actual=[]
  for rank in (0,1):
   boundary=read(dest/'boundary'/f'boundary-rank{rank}.json')
   require(boundary==view['boundary'][rank] and boundary['passed'] is True and boundary['total_reset'] is True and boundary['cached_tokens']==0 and boundary['selection_sha256']==selected['selection_sha256'] and boundary['weight_uploads_after_load']==0,'smoke reset failed')
   actual.append((boundary['arena_descriptors_sha256'],boundary['weight_descriptors_sha256']))
  if descriptors is None:descriptors=actual
  require(actual==descriptors,'smoke changed allocations/weights')
  rows=view['requests'];require([r['prompt_id'] for r in rows]==list(D.CHECK.PROMPT_IDS),'all twelve prompts in order required')
  for r in rows:
   require(r.get('passed') is True and r.get('exact_oracle') is True and r.get('cached_tokens')==0 and r['tokens']==D.CHECK.token_record(D.ORACLE/'results'/r['prompt_id'])[:64] and len(r['tokens'])==64,'smoke tokens differ')
   require(read(dest/r['prompt_id']/'receipt.json')==r,'smoke raw request differs')
  architecture=next(r for r in rows if r['prompt_id']=='architecture-tradeoff')
  require(architecture['tokens'][30]==215495,'known suffix regression not exercised')
  require(sum(r['stats']['misses'] for r in rows)>0,'smoke must exercise misses')
  incident=dest/'incident64/receipt.json'
  require(sha(incident)==view['incident64']['receipt_sha256'],'smoke incident receipt changed')
  r=read(incident);require(r['passed'] is True and r['cached_tokens']==0 and r['tokens']==D.CHECK.token_record(D.ORACLE/'results'/D.CHECK.PROMPT_IDS[0])[:64],'incident oracle differs')
 # RESET redirects the native output directory; the candidate's last request
 # receives its boundary counters just before switching back to control.
 counters=read(output/'run/views/01-candidate'/D.CHECK.PROMPT_IDS[-1]/'rank0/p121-restore-table.json')
 require(counters['mode']=='p121' and counters['reused_restore_tables']>0 and counters['restore_extent_guards_unchanged'] is True,'candidate restore never exercised')
 return dict(passed=True,smoke=True,diagnostic=True,submission_eligible=False,views=3,request_count=36,tokens_per_request=64,extra_incident_requests=3,cached_tokens=0,exact_oracle=True,reused_tables=counters['reused_restore_tables'])
def verify(output=OUTPUT):
 output=Path(output);window=read(output/'window.json');identity=read(output/'identity.json')
 require(window.get('passed') is True and window.get('device_complete') is True and window.get('device_executed') is True and window.get('lease_released') is True and not window.get('stop_reasons') and not window.get('child_still_running'),'smoke did not finish cleanly')
 require(window['identity']==identity,'smoke identity changed')
 require(window['wrapper_seal_sha256']==sha(HERE/'placement-validation/wrapper-seal.json'),'smoke CPU seal changed')
 for leaf,digest in window['files'].items():
  path=(output/leaf).resolve();require(path.is_relative_to(output.resolve()) and sha(path)==digest,'smoke artifact changed: '+leaf)
 require(read(output/'run/teardown.json')['drained'] is True,'smoke drain missing')
 require(read(output/'run/device-isolation.json')['passed'] is True,'smoke isolation failed')
 require(window['oracle_completion_sha256']==sha(D.ORACLE/'results/completion.json'),'smoke oracle changed')
 from bracket import load_config
 require(identity['bracket']==load_config(HERE/'configs/smoke.json'),'smoke config differs')
 return check_views(output,identity)
