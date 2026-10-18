"""Actual serial queue control flow; native processes and host probes are mocked."""
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch
import queue_runner as Q
import fault_review as F
import verify_ready as R

class QueueTests(unittest.TestCase):
    def run_chain(self, fail=None):
        with tempfile.TemporaryDirectory() as tmp:
            packet=Path(tmp)/'packet';packet.mkdir();(packet/'evidence').mkdir()
            out=packet/'evidence/card0-58w-b';seen=[]
            review=packet/'review.json';review.write_text('{}')
            def spawn(command,**kwargs):
                name=Path(command[command.index('--output')+1]).name
                seen.append(name);dest=out/name;dest.mkdir()
                self.assertEqual(command[command.index('--faults-reviewed-through')+1],'2026-10-18T07:00:04.230449Z')
                self.assertEqual(command[command.index('--view')+1],'down-tile16')
                window='K1' if name.startswith('K1') else name
                row=dict(window=window,passed=name!=fail,device_executed=True,
                    child_still_running=False,gpu_count=1,card=0,context=4096,boot_id='fixture')
                row['lane_admission']=dict(passed=True,card=0,scope=Q.W.A.window_scope(window),
                    timing_claim_eligible=window=='WS128',reservation=dict(boot_id='fixture'))
                (dest/'window.json').write_text(json.dumps(row))
                child=Mock();child.wait.return_value=1 if name==fail else 0;child.poll.return_value=child.wait.return_value
                return child
            with ExitStack() as stack:
                for obj,key,value in [(Q,'P',packet),(Q,'GAP_SECONDS',0),(Q.W,'user_unit_gate',lambda x:None),
                    (Q.W,'closed_environment',lambda:{}),(Q.W,'build_gate',lambda:{}),
                    (Q.W.SUPPORT,'storage',lambda *a:{}),(Q.W.S,'journal',lambda *a,**k:('',None)),
                    (Q.os,'getpriority',lambda *a:0),(Q.os,'sched_getaffinity',lambda *a:{0,1,2,3,16,17,18,19}),
                    (Q.subprocess,'Popen',spawn),
                    (R,'verify',lambda:dict(boot_id='fixture')),
                    (F,'validate',lambda path:(dict(boot_id='fixture',through_us=1792306806230449,through='2026-10-18T07:00:06.230449Z'),'','','cursor'))]:stack.enter_context(patch.object(obj,key,value))
                rc=Q.main(['--output-root',str(out),'--card','0','--authorized-device-window',
                    '--fault-review',str(review)])
            row=json.loads((out/'queue.json').read_text())
            self.assertEqual(rc,1 if fail else 0)
            self.assertEqual(seen,list(Q.ORDER[:3] if fail else Q.ORDER))
            self.assertEqual(row['completed'],list(Q.ORDER[:2] if fail else Q.ORDER))
            self.assertEqual(row['passed'],fail is None)
    def test_fresh_chain_starts_K1a_and_completes_seven_stages(self):self.run_chain()
    def test_KD_refusal_stops_without_retry(self):self.run_chain('KD')

if __name__=='__main__':unittest.main()
