#!/usr/bin/env python3
"""Exercise coordinator guards with a fake child; no device or journal access."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('window',HERE/'window.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
class Guards(unittest.TestCase):
    def setUp(self):
        (HERE/'build').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=HERE/'build');self.root=Path(self.temp.name)
        self.packet=self.root/'packet';self.build=self.packet/'build';self.build.mkdir(parents=True)
        self.binary=self.build/'device/own-rt-iq3';self.binary.parent.mkdir();self.binary.write_text('fake binary, never executed')
        self.input=self.build/'input';self.input.mkdir();(self.input/'tokens.txt').write_text('1 2')
        (self.input/'input.json').write_text(json.dumps(dict(tokens=[1,2],model_dir='not-opened',files={'tokens.txt':w.sha(self.input/'tokens.txt')})))
        self.oracle=self.root/'oracle/step1';self.oracle.mkdir(parents=True)
        (self.oracle.parent/'input.json').write_text('{"tokens":[1,2]}');(self.oracle/'layer-00.bf16').write_bytes(bytes(20480))
        (self.packet/'build-receipt.json').write_text(json.dumps(dict(passed=True,sources={},artifacts_sha256={'device/own-rt-iq3':w.sha(self.binary)})))
        self.out=self.build/'window';self.launched=0;self.journal_count=0;self.fault=False;self.mismatch=False
    def tearDown(self):self.temp.cleanup()
    def invoke(self):
        test=self
        class Child:
            pid=123
            returncode=0
            def __init__(self,cmd,**kwargs):
                test.launched+=1;run=Path(cmd[cmd.index('--output')+1]);run.mkdir();(run/'receipt.json').write_text(json.dumps(dict(oracle_exact=not test.mismatch,teardown=[dict(safe_to_exit=True)])))
            def poll(self):return 0
            def send_signal(self,sig):raise AssertionError('already exited child')
        def journal(cursor=None):
            self.journal_count+=1
            return ('Fault response\n' if self.fault and self.journal_count==2 else '',str(self.journal_count))
        argv=['window.py','--authorized-device-window','--card','3','--stage','layer','--input',str(self.input),'--oracle',str(self.oracle),'--output',str(self.out)]
        with patch.object(w,'HERE',self.packet),patch.object(w,'ROOT',self.root),patch.object(sys,'argv',argv),patch.object(w.os,'getpriority',return_value=19),patch.dict(w.os.environ,{'OMP_NUM_THREADS':'2'}),patch.object(w.subprocess,'check_output',return_value='idle'),patch.object(w.subprocess,'Popen',Child),patch.object(w.p2,'journal',side_effect=journal),patch.object(w.time,'sleep'):
            with self.assertRaises(SystemExit) as caught:w.main()
        return caught.exception.code
    def test_layer_pass(self):
        self.assertEqual(self.invoke(),0);self.assertEqual(self.launched,1);r=json.loads((self.out/'window.json').read_text());self.assertTrue(r['passed']);self.assertFalse(r['fresh_repeat_passed'])
    def test_binary_tamper_refused_before_child(self):
        self.binary.write_text('changed');self.assertNotEqual(self.invoke(),0);self.assertEqual(self.launched,0)
    def test_missing_oracle_refused_before_child(self):
        (self.oracle/'layer-00.bf16').unlink();self.assertNotEqual(self.invoke(),0);self.assertEqual(self.launched,0)
    def test_oracle_mismatch_never_passes(self):
        self.mismatch=True;self.assertEqual(self.invoke(),1);self.assertFalse(json.loads((self.out/'window.json').read_text())['passed'])
    def test_fault_latches_and_forbids_pass(self):
        self.fault=True;self.assertEqual(self.invoke(),1);self.assertTrue((self.build/'FAULT.json').exists())
if __name__=='__main__':unittest.main()
