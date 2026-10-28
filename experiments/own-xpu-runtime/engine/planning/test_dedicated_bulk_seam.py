"""Actual seven-chunk incident metadata; no device/model execution."""
from hashlib import sha256
import json
from pathlib import Path
import socket
import struct
import unittest
from rolling_provider.dedicated import DedicatedCoordinator
from rolling_provider.dedicated_prefill import Adoption
from rolling_provider.dedicated_transport import Stage,start_targets,ring

class Seam(unittest.TestCase):
 def test_actual_start_and_recorded_first_row_then_accept(self):
  root=Path(__file__).resolve().parents[2]
  f=json.loads((root/'research/pp4-review-2026-10-28/dedicated-gate/bulk-candidate/seam-r1-fixture.json').read_text())
  prompt=f['prompt'];bulk=len(prompt)-2;self.assertEqual(bulk,1675)
  m=DedicatedCoordinator(stages=3,request=bytes.fromhex(f['request']),epoch=0,prompt=prompt,max_new=32,context=262144,vocab=248320,eos_token_ids=[248044,248046],stream_bytes=40960,speculative_depth=3)
  raw=struct.pack(f'<{len(prompt)}i',*prompt)
  m.adopt_prefill(bulk,native=Adoption(bulk,0,m.request,sha256(raw).digest(),tuple(f['target_sequences']),7,bulk,7,bytes.fromhex(f['last_ack_hex'])))
  left,right=socket.socketpair()
  try:
   stage=object.__new__(Stage);stage.sock=left;stage.sequence=7;stage.physical=stage.committed=bulk
   stage.start_async() # The actual inherited path reproduces the original bug.
   self.assertEqual((stage.physical,stage.committed),(0,0))
   start_targets([stage],dict(prefill_positions=bulk))
   self.assertEqual((stage.physical,stage.committed),(bulk,bulk))
   command=next(c for c in m.commands() if c.stage==0);native=f['first_native_row']
   self.assertEqual((command.sequence,command.row.identity,command.row.position,command.row.token),(native['sequence'],native['row_id'],native['position'],native['token']))
   # RingStage.read_ready derives these fields from its transport counters.
   stage.physical+=1
   self.assertEqual((stage.physical,stage.committed,1),(native['physical'],native['committed'],native['pending']))
   ack=ring.Ack(0,0,command.sequence,command.row.identity,command.sequence,stage.physical,stage.committed,1,stream=bytes(40960))
   m.complete(command,ack)
   accept=next(c for c in m.commands() if c.stage==0 and c.op==ring.ACCEPT)
   # CPU resolution shape only; failed native incident never executed ACCEPT.
   m.complete(accept,ring.Ack(0,0,accept.sequence,accept.row.identity,command.sequence,bulk+1,bulk+1,0))
   self.assertEqual((m.stages[0].physical,m.stages[0].committed),(bulk+1,bulk+1))
  finally:left.close();right.close()
if __name__=='__main__':unittest.main()
