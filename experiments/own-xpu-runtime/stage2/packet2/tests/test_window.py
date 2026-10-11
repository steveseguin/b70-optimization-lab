"""Fault-watch orchestration tests: mocked child and journal, CPU files only."""
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import device_window as window

class Window(unittest.TestCase):
    def simulate(self,case):
        scratch=window.HERE/'build'
        with tempfile.TemporaryDirectory(dir=scratch,prefix='watcher-test-') as temporary:
            packet=Path(temporary);build=packet/'build';fixtures=build/'fixtures/device-fixtures';fixtures.mkdir(parents=True)
            fixture=fixtures/'random0-test.fixture';fixture.write_bytes(b'mocked fixture')
            binary=build/'device/device-test';binary.parent.mkdir();binary.write_bytes(b'NOT AN EXECUTABLE')
            cpu={'passed':True,'fixtures':[{'label':'random0-test','fixture_sha256':window.sha(fixture)}]}
            (packet/'cpu-receipt.json').write_text(json.dumps(cpu))
            receipt={'passed':True,'cpu_receipt_sha256':window.sha(packet/'cpu-receipt.json'),'source_sha256':{},'artifacts_sha256':{'device/device-test':window.sha(binary)}}
            (packet/'build-receipt.json').write_text(json.dumps(receipt))
            output=build/'window';children=[];calls=0
            def journal(cursor=None):
                nonlocal calls
                calls+=1
                if case=='preflight-failure' and calls==1:raise RuntimeError('no kernel journal')
                if case=='journal-timeout' and calls==2:raise subprocess.TimeoutExpired('journalctl',2)
                if case=='postflight-failure' and calls>3:raise RuntimeError('journal lost')
                line='Fault response\n' if (case=='fault' and calls==2) or (case=='postfault' and calls==4) else ''
                return line,'cursor'
            class Child:
                pid=12345;returncode=0
                def __init__(self,args,**kwargs):
                    self.polls=0;self.signals=[];children.append(self)
                    Path(args[-2]).write_text(json.dumps({'checks':4,'teardown':{'safe_to_exit':True}}))
                    Path(args[-1]).write_text('{}')
                def poll(self):self.polls+=1;return None if self.polls<2 else 0
                def send_signal(self,s):self.signals.append(s)
            argv=['device_window.py','--authorized-device-window','--card','0','--output',str(output)]
            with patch.object(window,'HERE',packet),patch.object(window,'journal',journal),patch.object(window.subprocess,'Popen',Child),patch.object(window.time,'sleep',lambda _:None),patch.object(window.signal,'signal'),patch('sys.argv',argv):
                if case=='preflight-failure':
                    with self.assertRaises(RuntimeError):window.main()
                    self.assertFalse(children);return
                with self.assertRaises(SystemExit) as result:window.main()
            self.assertEqual(len(children),1)
            saved=json.loads((output/'window.json').read_text())
            self.assertEqual(result.exception.code,0 if case=='pass' else 1)
            self.assertEqual(saved['passed'],case=='pass')
            if case in ('fault','journal-timeout'):self.assertEqual(children[0].signals,[signal.SIGTERM])
            else:self.assertEqual(children[0].signals,[])
            if case!='pass':self.assertTrue(saved['stop_reason'])
    def test_pass(self):self.simulate('pass')
    def test_fault_one_cooperative_stop(self):self.simulate('fault')
    def test_postfault(self):self.simulate('postfault')
    def test_preflight_refuses_child(self):self.simulate('preflight-failure')
    def test_journal_timeout(self):self.simulate('journal-timeout')
    def test_postflight_failure_receipt(self):self.simulate('postflight-failure')
    def test_journal_timeout_argument(self):
        fake=subprocess.CompletedProcess([],0,'line\n-- cursor: abc\n','')
        with patch.object(window.subprocess,'run',return_value=fake) as call:
            text,cursor=window.journal();self.assertEqual(cursor,'abc');self.assertEqual(text,'line\n');self.assertEqual(call.call_args.kwargs['timeout'],2)
if __name__=='__main__':unittest.main()
