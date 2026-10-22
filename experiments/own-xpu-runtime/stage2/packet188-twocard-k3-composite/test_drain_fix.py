"""Reproduce clock advancement between the cooldown condition and its sleep."""
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest

P=Path(__file__).resolve().parent
O=P/'v5'
import sys
sys.path.insert(0,str(O))

def load(path, old=False):
    # The negative control changes only the clamp in an in-memory source copy.
    source=path.read_text()
    if old:
        fixed='self.sleep(max(0.0, min(.25, until - self.now())))'
        assert fixed in source
        source=source.replace(fixed,'self.sleep(min(.25, until - self.now()))')
    module=types.ModuleType('drain_race_fixture')
    exec(compile(source,str(path),'exec'),module.__dict__)
    return module

def race(module):
    with tempfile.TemporaryDirectory(prefix='p124-drain-') as scratch:
        root=Path(scratch);clock=[59.9];checks=[0];sleeps=[]
        def check():
            checks[0]+=1
            if checks[0]==2:clock[0]=60.1
        def sleep(delay):
            if delay<0:raise ValueError('sleep length must be non-negative')
            sleeps.append(delay)
        permit=module.DrainPermit(root/'output',root=root,check=check,now=lambda:clock[0],sleep=sleep)
        (root/'teardown-state.json').write_text(json.dumps(dict(boot_id=permit.boot,drained=True,completed_monotonic=0)))
        with permit:
            assert sleeps==[0.0]
            assert permit.record['drained'] is False
            permit.complete()
        assert json.loads((root/'teardown-state.json').read_text())['drained'] is True
        return sleeps

class DrainFixTests(unittest.TestCase):
    def test_both_copies_survive_deadline_crossing(self):
        for path in (P/'drain_gate.py',O/'p188_v5_drain_gate.py'):
            with self.subTest(path=path):self.assertEqual(race(load(path)),[0.0])
    def test_old_code_fails_same_scenario(self):
        for path in (P/'drain_gate.py',O/'p188_v5_drain_gate.py'):
            with self.subTest(path=path),self.assertRaisesRegex(ValueError,'non-negative'):race(load(path,old=True))
    def test_copies_identical(self):
        self.assertEqual((P/'drain_gate.py').read_bytes(),(O/'p188_v5_drain_gate.py').read_bytes().replace(b'p188_v5_',b''))
    def test_static_scanner_rejects_old_code(self):
        root=P.parents[3]
        spec=importlib.util.spec_from_file_location('scan124',root/'scripts/check_drain_fix.py')
        scanner=importlib.util.module_from_spec(spec);spec.loader.exec_module(scanner)
        for path in (P/'drain_gate.py',O/'p188_v5_drain_gate.py'):
            source=path.read_text()
            self.assertEqual(scanner.inspect_source(source,drain_gate=True)['status'],'FIXED')
            source=source.replace('max(0.0, min(.25, until - self.now()))','min(.25, until - self.now())')
            self.assertEqual(scanner.inspect_source(source,drain_gate=True)['status'],'UNFIXED')
if __name__=='__main__':unittest.main()
