"""Offline checks of all selected payload identities and the pinned record floor."""
import sys,json,gzip,importlib.util,hashlib,resource
from source_decision import P,O,ROOT,sha,save
sys.path.insert(0,str(P))
import submission_evidence as current
from compositions import all_compositions,native,DIMENSIONS
from bundle_selection import FIXED,KEYS,name

def main():
 ledger=current.validate_threshold(json.loads((ROOT/current.THRESHOLD_FILE).read_text()))
 assert ledger['reference_submission']=='cmve4dtir007wrf01k57sdf23' and abs(ledger['threshold_tok_s']-58.798109)<1e-6
 rows=[]
 for s in all_compositions():
  values=FIXED+tuple(s[k] for k in DIMENSIONS)
  bundle=dict(zip(KEYS,values),name=name(*values),placement='1',draft='draft-hc',miss='banks-batch',draft_rank=1,target_split=0,layer_boundary=24)
  current.validate_bundle(bundle,native(s));notes=current.submission_notes(bundle,ledger)
  assert all(k+'='+s[k] in notes for k in DIMENSIONS) and 'strict512 realistic_final_gate.passed=false' in notes
  rows.append(dict(selection=s,notes=notes))
 # Replay frozen parent evidence with its own identity; raising the ledger must
 # reject it, including the rounding boundary 58.798108759 < 58.798109.
 import packet56_submission as parent
 import bundle8_selection
 actual_bundle=sys.modules['bundle_selection'];sys.modules['bundle_selection']=bundle8_selection
 members=json.loads(gzip.decompress((P/'lineage-inputs/packet136-chain-evidence.json.gz').read_bytes()))['members']
 e=parent.Evidence(members);result=parent.derive(e,'packet136-record-bundle')
 assert result['primary_metric']['value_tok_s']==ledger['threshold_tok_s']
 changed=parent.Evidence(dict(members));changed.members.pop('record-threshold.json')
 changed.add('record-threshold.json',ROOT/current.THRESHOLD_FILE)
 try:parent.derive(changed,'packet136-record-bundle')
 except ValueError as error:
  assert 'speed at or below' in str(error);refusal=str(error)
 else:raise AssertionError('old record accepted as new record')
 sys.modules['bundle_selection']=actual_bundle
 pin=current.pin_resealed_packet56()
 save(O/'evidence/submission143.json',dict(passed=True,device_executed=False,network_used=False,submitted=False,all_compositions=rows,pinned_ledger=ledger,parent_replay_rate=result['primary_metric']['value_tok_s'],current_floor_refusal=refusal,pins=pin,scope='Parent evidence retains packet136 identity; no packet143 performance fabricated'))
 print('16 submission identities and current-ledger refusal PASS')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
