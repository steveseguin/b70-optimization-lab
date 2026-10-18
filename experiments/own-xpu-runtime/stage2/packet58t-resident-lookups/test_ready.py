"""Native launch remains closed when current resident screen evidence is absent."""
from contextlib import ExitStack
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
import queue_runner as Q
import verify_ready as R
class ReadyTests(unittest.TestCase):
    def test_no_launch_when_readiness_refuses_even_with_ready_json(self):
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            root=Path(tmp);(root/'evidence').mkdir();(root/'ready.json').write_text('{"ready":true}')
            stack.enter_context(patch.object(Q,'P',root))
            for obj,name,ret in ((Q.W,'build_gate',{}),(Q.W,'user_unit_gate',None),(Q.W,'closed_environment',{}),(Q.os,'getpriority',0),(Q.os,'sched_getaffinity',{0,1,2,3,16,17,18,19})):
                stack.enter_context(patch.object(obj,name,return_value=ret))
            stack.enter_context(patch.object(R,'verify',side_effect=ValueError('missing screen receipt')))
            spawn=stack.enter_context(patch.object(Q.subprocess,'Popen',side_effect=AssertionError('must not launch')))
            with self.assertRaisesRegex(ValueError,'missing screen'):
                Q.main(['--output-root',str(root/'evidence/card0-58t-a'),'--fault-review','/unused','--view','down-tile16','--authorized-device-window'])
            spawn.assert_not_called()
    def test_command_is_emitted_only(self):
        command=R.chain_command()
        for text in ('systemd-run --user','--property=Restart=no','--property=SendSIGKILL=no','--property=Nice=0','--view down-tile16','--fault-review','card0-58t-a','< /dev/null'):self.assertIn(text,command)

class ScreenClosureTests(unittest.TestCase):
    def test_complete_file_closure_and_kernel_and_memory(self):
        import json
        import screen_window as W
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'run/run').mkdir(parents=True)
            names=('summary.json','kernel-before.jsonl','kernel-window.jsonl','run/receipt.json','run/summary.json','run/run/receipt.json','host-memory.jsonl')
            for name in names:(root/name).write_text('{}')
            identity=dict(boot_id='boot',build_receipt_sha256='seal',artifacts_sha256={'binary':'hash'},environment={},card=0,context=4096,gpu_count=1)
            row=dict(identity,schema='own-runtime.packet58.window.v1',passed=True,device_executed=True,child_still_running=False,window='WSCREEN',qualifying=False,stop_reasons=[],pid=42,process_start_ticks=123)
            row['lane_admission']=dict(passed=True,card=0,scope='whole-host',timing_claim_eligible=False,reservation=dict(boot_id='boot'))
            row['native_files']={n:W.sha(root/n) for n in names if n!='host-memory.jsonl'}
            row['postload_memory']=dict(complete_postload=True,sources={'host-memory.jsonl':W.sha(root/'host-memory.jsonl')})
            row['memory_samples_sha256']=W.sha(root/'host-memory.jsonl')
            path=root/'window.json'
            def check():
                path.write_text(json.dumps(row));return W.prerequisite(path,'WSCREEN',identity)
            self.assertTrue(check()['passed'])
            files=row['native_files'];row['native_files']={}
            with self.assertRaisesRegex(ValueError,'closure incomplete'):check()
            row['native_files']=files
            (root/'kernel-window.jsonl').write_text('Fault response')
            files['kernel-window.jsonl']=W.sha(root/'kernel-window.jsonl')
            with self.assertRaisesRegex(ValueError,'kernel fault'):check()
            (root/'kernel-window.jsonl').write_text('{}');files['kernel-window.jsonl']=W.sha(root/'kernel-window.jsonl')
            (root/'host-memory.jsonl').write_text('changed')
            with self.assertRaises(ValueError):check()
