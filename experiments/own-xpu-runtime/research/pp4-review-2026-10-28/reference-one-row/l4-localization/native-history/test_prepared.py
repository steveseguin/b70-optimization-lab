import copy,json,struct,tempfile,unittest
from pathlib import Path
import validate_prepared as P
import validate as V
from unittest.mock import patch
import capture_history as H
def fixture(root):
 d=root/'prepared';d.mkdir();control=root/'controls';control.write_bytes(bytes(384));attempts=root/'attempts';data=bytearray();rows=[];observed=[]
 for p in range(244):
  bindings=[]
  for k in range(20):
   b=dict(slot=k,allocation=k+1,pointer=4096*(k+1)+16,base=4096*(k+1),offset=16,allocation_bytes=20000,read_slot=k in P.READS,binding='bound',live=True,memory_kind=0,label='unused')
   if k==3:b['label']='card0:weight:blk.4.ssm_a'
   if k==4:b['label']='card0:weight:blk.4.ssm_dt.bias'
   bindings.append(b)
  stages=[dict(kernel='round2::Kernel<gdn,%d>'%s,stage=s,prepared=True,shape=[7,1,2560,4,0,94,4096,2048,0])for s in (1,0)]
  meta=dict(site=170,implementation=2,bank_parity=p%2,actual_stages=stages,bindings=bindings)
  piece=bytes(P.SCRATCH+384)+struct.pack('<3i',0,p,1);parts=[piece[P.SCRATCH:P.SCRATCH+192],piece[P.SCRATCH+192:P.SCRATCH+384],piece[-12:-8],piece[-8:-4],piece[-4:]]
  rows.append(dict(position=p,offset=p*P.ROW_BYTES,scratch_sha256=V.sha(piece[:P.SCRATCH]),controls_sha256=[V.sha(x)for x in parts],invocation=meta));data.extend(piece)
  command=dict(queue=0,ids=[b['allocation']for b in bindings],pointers=[b['pointer']for b in bindings]);calls=[dict(stage=s['stage'],prepared=True,shape=s['shape'],pointers=command['pointers'])for s in stages]
  observed.append(dict(position=p,site=170,observed_calls=calls,commands=[command,copy.deepcopy(command)]))
 (d/'prepared.bin').write_bytes(data);(d/'rows.jsonl').write_text(''.join(json.dumps(x)+'\n'for x in rows));attempts.write_text(''.join(json.dumps(x)+'\n'for x in observed));seal(d)
 return d,attempts,control
def seal(d):
 (d/'seal.json').write_text(json.dumps(dict(schema='ownrt.l4-prepared-history.v1',rows=244,row_bytes=P.ROW_BYTES,payload_bytes=P.TOTAL,payload_sha256=V.sha((d/'prepared.bin').read_bytes()),index_sha256=V.sha((d/'rows.jsonl').read_bytes()))))
class Tests(unittest.TestCase):
 def test_explicit_plan_option_and_rank0_only_environment(self):
  with tempfile.TemporaryDirectory()as t:
   root=Path(t);control=root/'controls';control.write_bytes(bytes(384));config=root/'config.json'
   for value in (False,True,'yes'):
    cfg=dict(prepared_history=value,prepared_control_reference=str(control),neutrality_baselines={str(k):str(Path(__file__).parent/'baselines'/f'rank{k}')for k in (0,1)})
    config.write_text(json.dumps(cfg));base=dict(pins={},stages=[dict(id=k,environment={})for k in (0,1)])
    with patch.object(H.P,'make_plan',return_value=base):
     if value=='yes':
      with self.assertRaises(AssertionError):H.make_plan(config)
     else:
      plan=H.make_plan(config);self.assertIs(plan['prepared_history'],value)
      self.assertEqual([s['environment'].get('OWNRT_L4_PREP_HISTORY')for s in plan['stages']],['1'if value else None,None])
 def test_full_seal_and_actual_nonzero_offsets(self):
  with tempfile.TemporaryDirectory()as t:self.assertEqual(P.verify(*fixture(Path(t)))['payload_bytes'],4188016)
 def test_authenticated_bad_stage_offset_or_control_refused(self):
  for defect in ('stage','offset','control'):
   with self.subTest(defect=defect),tempfile.TemporaryDirectory()as t:
    d,a,c=fixture(Path(t))
    if defect=='control':c.write_bytes(bytes(383)+b'X')
    else:
     rows=[json.loads(x)for x in (d/'rows.jsonl').read_text().splitlines()]
     if defect=='stage':rows[0]['invocation']['actual_stages'][0]['stage']=0
     else:rows[0]['invocation']['bindings'][19]['offset']=19999
     (d/'rows.jsonl').write_text(''.join(json.dumps(x)+'\n'for x in rows));seal(d)
    with self.assertRaises(AssertionError):P.verify(d,a,c)
if __name__=='__main__':unittest.main()
