"""CPU-only watcher tests: fake child, clock and journal; no device commands."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('window',HERE/'window.py')
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)

class Guards(unittest.TestCase):
    def setUp(self):
        (HERE/'build').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=HERE/'build');self.root=Path(self.temp.name)
        self.packet=self.root/'packet';self.build=self.packet/'build';self.build.mkdir(parents=True)
        self.binary=self.build/'device/own-rt-iq3';self.binary.parent.mkdir();self.binary.write_text('fake, never executed')
        self.input=self.build/'input';self.input.mkdir();(self.input/'tokens.txt').write_text('1 2')
        (self.input/'input.json').write_text(json.dumps(dict(tokens=[1,2],model_dir='never-opened',files={'tokens.txt':w.sha(self.input/'tokens.txt')})))
        self.receipt=dict(passed=True,sources={},arithmetic='test-order',arithmetic_sources={},
                          input_sha256=w.sha(self.input/'input.json'),artifacts_sha256={'device/own-rt-iq3':w.sha(self.binary)})
        (self.packet/'build-receipt.json').write_text(json.dumps(self.receipt))
        self.out=self.build/'window';self.launched=0;self.journal_count=0
        self.fault=False;self.lost=False;self.safe=True;self.missing=False;self.short=False;self.changed=False
        self.stage='first-token';self.cards=1;self.card=3;self.memory='layer-streaming';self.extra=[];self.running=False;self.signals=0;self.invalid_receipt=False
    def tearDown(self):self.temp.cleanup()
    def invoke(self):
        test=self
        class Child:
            pid=123;returncode=0
            def __init__(self,cmd,**kwargs):
                test.launched+=1;run=Path(cmd[cmd.index('--output')+1]);run.mkdir()
                assert cmd[cmd.index('--cards')+1]==str(test.cards)
                assert cmd[cmd.index('--memory')+1]==test.memory
                for step in range(1,9 if test.stage=='first-token' else 2):
                    d=run/f'step{step}';d.mkdir()
                    for layer in range(48 if test.stage=='first-token' else 1):
                        if not(test.missing and step==1 and layer==0):
                            (d/f'layer-{layer:02}.bf16').write_bytes(bytes([int(test.changed)])*20480)
                tears=[dict(safe_to_exit=test.safe,live_bytes=0,in_flight=0)]*test.cards
                tokens=([1]* (7 if test.short else 8)) if test.stage=='first-token' else []
                (run/'receipt.json').write_text('{' if test.invalid_receipt else json.dumps(dict(passed=True,tokens=tokens,teardown=tears)))
                if test.running:self.returncode=None
            def poll(self):return self.returncode
            def send_signal(self,sig):
                assert self.returncode is None
                test.signals+=1;self.returncode=143
        def journal(cursor=None):
            self.journal_count+=1
            if self.lost and self.journal_count>1:raise RuntimeError('journal unavailable')
            return ('Fault response\n' if self.fault and self.journal_count==2 else '',str(self.journal_count))
        argv=['window.py','--authorized-device-window','--card',str(self.card),'--cards',str(self.cards),
              '--memory',self.memory,'--stage',self.stage,'--input',str(self.input),'--output',str(self.out),*self.extra]
        with patch.object(w,'HERE',self.packet),patch.object(w,'ROOT',self.root),patch.object(sys,'argv',argv),\
             patch.object(w.os,'getpriority',return_value=19),patch.dict(w.os.environ,{'OMP_NUM_THREADS':'2'}),\
             patch.object(w.subprocess,'check_output',return_value='idle'),patch.object(w.subprocess,'Popen',Child),\
             patch.object(w.p2,'journal',side_effect=journal),patch.object(w.time,'sleep'),patch.object(w.signal,'signal'):
            with self.assertRaises(SystemExit) as caught:w.main()
        return caught.exception.code
    def test_eight_steps_384_hashes_no_quality_claim(self):
        self.assertEqual(self.invoke(),0);r=json.loads((self.out/'window.json').read_text())
        self.assertEqual(len(r['layer_hashes']),384);self.assertIsNone(r['oracle_exact']);self.assertFalse(r['real_model_qualified'])
    def test_layer(self):self.stage='layer';self.assertEqual(self.invoke(),0)
    def test_two_card_command(self):
        self.cards=2;self.card=2;self.memory='resident';self.assertEqual(self.invoke(),0)
    def test_bad_pair_rejected(self):self.cards=2;self.assertNotEqual(self.invoke(),0);self.assertEqual(self.launched,0)
    def test_binary_tamper(self):self.binary.write_text('changed');self.assertNotEqual(self.invoke(),0);self.assertEqual(self.launched,0)
    def test_input_manifest_tamper(self):
        (self.input/'input.json').write_text('{}');self.assertNotEqual(self.invoke(),0);self.assertEqual(self.launched,0)
    def test_input_bytes_tamper(self):
        (self.input/'tokens.txt').write_text('9');self.assertNotEqual(self.invoke(),0);self.assertEqual(self.launched,0)
    def test_missing_layer(self):self.missing=True;self.assertEqual(self.invoke(),1)
    def test_early_eos_is_incomplete(self):self.short=True;self.assertEqual(self.invoke(),1)
    def test_fault_latch(self):
        self.fault=True;self.assertEqual(self.invoke(),1);self.assertTrue((self.build/'FAULT.json').exists())
        self.out=self.build/'second';self.assertNotEqual(self.invoke(),0);self.assertEqual(self.launched,1)
    def test_journal_loss_latches(self):self.lost=True;self.assertEqual(self.invoke(),1);self.assertTrue((self.build/'FAULT.json').exists())
    def test_running_fault_signals_once(self):
        self.running=True;self.fault=True;self.assertEqual(self.invoke(),1);self.assertEqual(self.signals,1)
    def test_invalid_receipt_latches(self):
        self.invalid_receipt=True;self.assertEqual(self.invoke(),1);self.assertTrue((self.build/'FAULT.json').exists())
    def test_unsafe_owner_latches(self):self.safe=False;self.assertEqual(self.invoke(),1);self.assertTrue((self.build/'FAULT.json').exists())
    def test_fresh_repeat(self):
        self.assertEqual(self.invoke(),0);self.extra=['--repeat-of',str(self.out/'window.json')];self.out=self.build/'repeat'
        self.assertEqual(self.invoke(),0);self.assertTrue(json.loads((self.out/'window.json').read_text())['fresh_repeat_passed'])
    def test_changed_repeat_fails(self):
        self.assertEqual(self.invoke(),0);self.extra=['--repeat-of',str(self.out/'window.json')];self.out=self.build/'repeat';self.changed=True
        self.assertEqual(self.invoke(),1)
    def test_old_oracle_rejected(self):
        oracle=self.root/'oracle';oracle.mkdir();(oracle/'arithmetic.json').write_text('{"arithmetic":"BLAS"}')
        self.extra=['--oracle',str(oracle)];self.assertNotEqual(self.invoke(),0);self.assertEqual(self.launched,0)

if __name__=='__main__':unittest.main()
