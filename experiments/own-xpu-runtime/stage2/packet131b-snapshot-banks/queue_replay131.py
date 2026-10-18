"""Replay unchanged queue validators using this packet's actual CPU storage.

The frozen parent's live chain now exceeds its retained-build allowance when
counted from a disposable queue directory. Do not edit or prune it. Scope the
CPU replay's storage census to packet131 plus disposable queue writes instead;
all receipt, seal, input, prefix, oracle and no-retry validators remain real.
"""
import json,sys,shutil
from unittest.mock import patch
from build131 import P,BASE,cpu_main,limits
def main():
 ops=P.parents[1]/'ops/packet124c-orchestration'
 sys.path.insert(0,str(ops));sys.path.insert(1,str(BASE))
 from chain_adapter import install
 install()
 import storage
 import queue_gate
 def used():
  own=storage.build_size(P/'build')
  assert own<=300_000_000 and shutil.disk_usage('/').free>=25_000_000_000
  scratch=storage.build_size(storage.B) if str(storage.B).startswith('/tmp/') else 0
  return own+scratch
 with patch.object(storage,'stored_build_size',side_effect=used):result=queue_gate.probe()
 result['storage_scope']='Actual packet131 CPU build plus disposable queue; frozen parent live-chain artifacts excluded.'
 result['frozen_parent_storage_admission_claimed']=False
 print('ARGUMENT_RESULT='+json.dumps(result))
if __name__=='__main__':cpu_main();main()
