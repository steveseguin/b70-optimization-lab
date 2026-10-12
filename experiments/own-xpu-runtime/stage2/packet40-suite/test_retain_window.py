#!/usr/bin/env python3
"""Synthetic offline window-retention success/refusal tests; never starts ranks."""
import hashlib,json,tempfile
from pathlib import Path
from unittest.mock import patch
import retain_window as helper
import storage,suite,pipeline
P=Path(__file__).resolve().parent

def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value)+'\n')
def bind(root):
 row=json.loads((root/'window.json').read_text())
 row['receipts']={str(f.relative_to(root)):storage.digest(f) for f in (root/'run').rglob('receipt.json')}
 save(root/'window.json',row)
def owners(run,suite_mode=False):
 owner=run/'ranks' if suite_mode else run
 save(owner/'ownership.json',dict(retained_pids=[],returncodes=[0,0]))
 for rank in (0,1):save(owner/f'rank{rank}/receipt.json',dict(passed=True,rank=rank,teardown=[dict(safe_to_exit=True,live_bytes=0,in_flight=0)]))
def states(output):
 for rank in (0,1):
  base=output/f'rank{rank}/state-2147483647';base.mkdir(parents=True)
  (base/'x.bin').write_bytes(b'state');save(base/'state.json',dict(buffers={'x':storage.digest(base/'x.bin')}))
  save(output/f'rank{rank}/request-state-inventory.json',dict(logical_event=0,standalone_target_mutable={'scratch':dict(bytes=4,sha256='a'*64)},loaded_layer=[-1]))
def pair(build):
 roots=[build/('W2s-'+c) for c in ('python','native')]
 for root,controller in zip(roots,('python','native')):
  run=root/'run';run.mkdir(parents=True);states(run);owners(run)
  save(run/'receipt.json',dict(passed=True,controller=controller,tokens=[7,8],stats=dict(guesses=1,hits=1,misses=0,no_guess=0),guess_sequence=[8],guess_rows=[dict(position=1,guess=8,actual=8,hit=True)]))
  hashes={}
  for rank in (0,1):
   f=run/f'rank{rank}/step1/layer-{rank:02}.bf16';f.parent.mkdir();f.write_bytes(b'fixture'+bytes([rank]));hashes[f'step1/{f.name}']=storage.digest(f)
  save(root/'window.json',dict(passed=True,window='W2s',card=0,boot_id='synthetic',artifacts_sha256={'binary':'b'*64},build_receipt_sha256='c'*64,dispatch_sha256='d'*64,oracle_hashes=hashes,expected_tokens=[7,8],prompt_overlap='on',layer_matches=2))
  bind(root)
 return roots

def suite_root(build):
 root=build/'WS';run=root/'run';run.mkdir(parents=True);owners(run,True)
 output=run/'repeat-1/synthetic';output.mkdir(parents=True);states(output)
 retained=suite.retain_request_state(output);save(output/'state-retention.json',retained)
 step=output/'step1';step.mkdir();rows=[]
 for layer in range(48):
  f=step/f'layer-{layer:02}.bf16';f.write_bytes(bytes(20480));rows.append(dict(layer=layer,sha256=storage.digest(f)))
 (step/'layers.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
 request=dict(passed=True,prompt_id='synthetic',repeat=1,tokens=[7],oracle_check=dict(passed=True));save(output/'receipt.json',request)
 summary=dict(passed=True,rows=[dict(passed=True,prompt_id='synthetic',repeat=1,receipt='repeat-1/synthetic/receipt.json')])
 save(run/'receipt.json',summary);save(run/'summary.json',summary)
 save(root/'window.json',dict(passed=True,window='WS',summary=summary));bind(root)
 return root

def main():
 checks=[]
 with tempfile.TemporaryDirectory(prefix='review-window-retention-',dir=P/'build') as temp:
  base=Path(temp)
  def case(name):
   root=base/name;build=root/'build';build.mkdir(parents=True)
   return root,build
  for name,mutate in [
   ('failed-window',lambda roots:save(roots[0]/'window.json',dict(json.loads((roots[0]/'window.json').read_text()),passed=False))),
   ('receipt-hash',lambda roots:(roots[0]/'run/receipt.json').write_text('{}')),
   ('owned-rank',lambda roots:save(roots[0]/'run/ownership.json',dict(retained_pids=[123],returncodes=[None,0]))),
   ('missing-rank-state',lambda roots:(roots[1]/'run/rank1/state-2147483647/x.bin').unlink()),
   ('identity-mismatch',lambda roots:save(roots[1]/'window.json',dict(json.loads((roots[1]/'window.json').read_text()),card=1))),
   ('prerequisite',lambda roots:save(roots[0]/'window.json',dict(json.loads((roots[0]/'window.json').read_text()),window='K2'))),
   ('token-difference',lambda roots:save(roots[1]/'run/receipt.json',dict(json.loads((roots[1]/'run/receipt.json').read_text()),tokens=[7,9])))]:
   root,build=case(name)
   with patch.multiple(helper,P=root,B=build),patch.multiple(storage,P=root,B=build):
    roots=pair(build);mutate(roots)
    if name=='token-difference':bind(roots[1])
    try:helper.retain(roots,pair=True)
    except (ValueError,AssertionError,FileNotFoundError):pass
    else:raise AssertionError('refusal missed: '+name)
    assert all(r.exists() for r in roots);assert not list((root/'evidence').glob('*'))
   checks.append(name+' refuses without deletion')
  root,build=case('missing-draft-state')
  with patch.multiple(helper,P=root,B=build),patch.multiple(storage,P=root,B=build):
   roots=pair(build)
   for window in roots:save(window/'window.json',dict(json.loads((window/'window.json').read_text()),window='W2m'))
   try:helper.retain(roots,pair=True)
   except ValueError:pass
   else:raise AssertionError('missing draft state accepted')
   assert all(window.exists() for window in roots)
  checks.append('missing MTP draft final-state refuses deletion')
  root,build=case('symlink')
  with patch.multiple(helper,P=root,B=build),patch.multiple(storage,P=root,B=build):
   roots=pair(build);alias=build/'alias';alias.symlink_to(roots[0],target_is_directory=True)
   try:helper.retain([alias,roots[1]],pair=True)
   except ValueError:pass
   else:raise AssertionError('symlink accepted')
   assert all(r.exists() for r in roots)
  checks.append('symlink input refuses before resolution')
  root,build=case('archive-failure')
  with patch.multiple(helper,P=root,B=build),patch.multiple(storage,P=root,B=build):
   roots=pair(build)
   with patch.object(helper,'discard',side_effect=OSError('injected archive failure')):
    try:helper.retain(roots,pair=True)
    except OSError:pass
    else:raise AssertionError('archive error hidden')
   record=json.loads((root/'evidence/W2s-controller-parity-retention.json').read_text())
   assert record['comparison_passed'] and not record['passed'] and not record['retention_complete'] and all(r.exists() for r in roots)
  checks.append('archive failure leaves incomplete receipt and raw evidence')
  root,build=case('pair-success')
  with patch.multiple(helper,P=root,B=build),patch.multiple(storage,P=root,B=build):
   roots=pair(build);result=helper.retain(roots,pair=True)
   assert result['passed'] and result['retention_complete'] and len(result['archives'])==2 and not any(r.exists() for r in roots)
   for row in result['archives']:assert storage.digest(root/row['path'])==row['sha256'];storage.verify_archive(root/row['path'])
  checks.append('exact pair archives verify before scratch removal')
  root,build=case('suite-success')
  with patch.multiple(helper,P=root,B=build),patch.multiple(storage,P=root,B=build):
   window=suite_root(build);result=helper.retain([window]);assert result['passed'] and not window.exists()
   assert result['proof']['requests'][0]['fixtures']==48 and set(result['proof']['requests'][0]['runtime_state_inventory_sha256'])=={'0','1'}
   storage.verify_archive(root/result['archives'][0]['path'])
  checks.append('finished suite validates state and fixture hashes then retains')
  root,build=case('suite-corrupt')
  with patch.multiple(helper,P=root,B=build),patch.multiple(storage,P=root,B=build):
   window=suite_root(build);f=window/'run/repeat-1/synthetic/step1/layer-00.bf16';f.write_bytes(b'x'*20480)
   try:helper.retain([window])
   except ValueError:pass
   else:raise AssertionError('corrupt suite fixture accepted')
   assert window.exists()
  checks.append('corrupt suite fixture refuses deletion')
 result=dict(passed=True,device_executed=False,rank_processes_started=0,synthetic_only=True,checks=checks,source_sha256={n:storage.digest(P/n) for n in ['retain_window.py','test_retain_window.py','compare_controllers.py','storage.py','suite_export.py','suite.py']})
 save(P/'window-retention-gates.json',result);print(json.dumps(result))
if __name__=='__main__':main()
