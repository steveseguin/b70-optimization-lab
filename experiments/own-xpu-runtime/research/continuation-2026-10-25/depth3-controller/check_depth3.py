from dataclasses import replace
from hashlib import sha256
import struct,json,tempfile
from pathlib import Path
from unittest.mock import patch
import ring_live_wire as codec,ring_wire as wire
from test_ring_live_wire import final_fixture
from test_ring_wire import command
from test_persistent_rolling import PersistentPlanTests,driver,base
_,_,_,c=final_fixture();c=replace(c,depth=3);s=c.seed.row
raw=codec.PROPOSAL.pack(0x44525032,2,224,3,0,5,2,1,2,1,1,1,3,3,18,32,0,1,s.request,s.after,sha256(c.parent.handoff.hidden).digest())+struct.pack('<i',44)+bytes(28)
assert codec.decode_proposal(raw,c,vocab=97,context=64)['guesses']==[18,32,44]
for off in [4,8,72,192,196,223]:
 bad=bytearray(raw);bad[off]=255
 try:codec.decode_proposal(bytes(bad),c,vocab=97,context=64)
 except ValueError:pass
 else:raise AssertionError(('accepted corruption',off))
a=command();pending=[replace(a,sequence=11+i,row=replace(a.row,identity=2+i,parent=1+i,position=1+i)) for i in range(3)]
abort=wire.ring.Command(0,wire.ring.ABORT_SUFFIX,14,a.row,True,11)
ack=wire.ACK_META.pack(0x5241434b,2,128,0,0,2,2,3,0,14,11,1,1,3,0,0,struct.pack('<Q',4)+bytes(40))
wire.resolution_ack(ack,abort,pending,physical=4,committed=1,verify_restore=False,depth=3)
for off in [4,80,88,127]:
 bad=bytearray(ack);bad[off]^=1
 try:wire.resolution_ack(bytes(bad),abort,pending,physical=4,committed=1,verify_restore=False,depth=3)
 except ValueError:pass
 else:raise AssertionError(('accepted ACK corruption',off))
with tempfile.TemporaryDirectory() as tmp:
 p,cfg,_,under=PersistentPlanTests().fixture(Path(tmp),'measured',32)
 cfg['speculative_depth']=3;p.write_text(json.dumps(cfg))
 with patch.object(base,'make_plan',side_effect=under):plan=driver.make_plan(p)
 assert plan['speculative_depth']==3 and all(base.option(s['argv'],'--pipeline-ring-depth')=='3' for s in plan['stages'])
 def inherited(path):
  value=under(path);value['stages'][0]['argv'] += ['--pipeline-ring-depth','3'];return value
 with patch.object(base,'make_plan',side_effect=inherited):
  try:driver.make_plan(p)
  except ValueError as e:assert 'inherited' in str(e)
  else:raise AssertionError('inherited native depth accepted')
 for bad in [True,1,4,'3']:
  cfg['speculative_depth']=bad;p.write_text(json.dumps(cfg))
  with patch.object(base,'make_plan') as mock:
   try:driver.make_plan(p)
   except ValueError:pass
   else:raise AssertionError('bad configured depth accepted')
   mock.assert_not_called()
print('PASS depth3 proposal+ACK exact extent/version/third value/reserved refusal; planner opt-in+invalid-depth refusal; default8tests alsoPASS')
