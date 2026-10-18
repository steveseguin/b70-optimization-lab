"""Four-composition synthetic chain replay; no device or network calls."""
import json
import pytest
from submission_fixture import prefix_fixture,put,p
from bundle_selection import configurations,KEYS

@pytest.mark.parametrize('config',configurations())
def test_four_composition_submission(config,tmp_path):
 name,values,placement=config
 e=prefix_fixture(placement=placement,**dict(zip(KEYS,values)))
 result=p.derive(e,p.P56_PACKET)
 assert result['primary_metric']['value_tok_s']==pytest.approx(71.25)
 assert result['realistic_final_gate']['passed'] is False
 payload=p.payload_for(result,{'path':'r','sha256':'a'},{'path':'a','sha256':'b'},'doc')['payload']
 for key in ('other_fusion','target_head','draft_prefix','suffix_schedule'):
  assert payload['engineFlags']['packet103Changes'][key]==dict(zip(KEYS,values))[key]
 assert 'preregistered non-benchmark text' in payload['notes']
 assert len(payload['notes'])<=2000
 for leaf,key in [(p.PINS_FILE,'submission-pins.json'),(p.THRESHOLD_FILE,'record-threshold.json')]:
  target=tmp_path/leaf;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(e.raw(key))
 out=tmp_path/p.STAGE/p.P56_PACKET/'submission/prepared'
 result=p.write_prepared(e,p.P56_PACKET,out,tmp_path)
 item=json.loads((out/'payload-queue.json').read_bytes())[0]
 assert p.scope_problems(item,tmp_path)==[]
 from submission import load_submitter
 cli=load_submitter();cli.REPO_ROOT=tmp_path
 assert cli.preflight_payload(item)==[]
 pins=json.loads((tmp_path/p.PINS_FILE).read_bytes());pins['lineages'][p.P56_PACKET]['build_receipt_sha256']='0'*64
 (tmp_path/p.PINS_FILE).write_bytes(p.encoded(pins))
 assert p.scope_problems(item,tmp_path) and cli.preflight_payload(item)
 assert p.replay_result(result,tmp_path)['packet']==p.P56_PACKET

@pytest.mark.parametrize('member',['bundle-selection.json','WS128/lane-admission.json','draft-prefix-selection.json','screen-seal.json'])
def test_evidence_tampering_refused(member):
 e=prefix_fixture();put(e,member,{'tampered':True})
 with pytest.raises(ValueError):p.derive(e,p.P56_PACKET)
