#!/usr/bin/env python3
"""CPU-only protocol tests; fake files, no subprocess/device/journal access."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import device_window as w
class Admission(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='p15-test-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.build=self.root/'build';self.build.mkdir();self.fixtures=self.build/'fixtures';self.fixtures.mkdir();(self.fixtures/'cases.txt').write_text('a.fixture\n')
        (self.root/'source').write_text('code')
        self.m=dict(compiled=True,device_executed=False,cpu_exactness_passed=True,hashes={'source':w.sha(self.root/'source')},fixtures={'cases':[{'name':'a.fixture'}]})
        self.write();self.output=self.build/'card3-new'
        for key,value in [('ROOT',self.root),('BUILD',self.build),('LATCH',self.build/'latch')]:
            p=patch.object(w,key,value);p.start();self.addCleanup(p.stop)
        p=patch.object(w.os,'getpriority',return_value=19);p.start();self.addCleanup(p.stop)
        p=patch.dict(w.os.environ,{'OMP_NUM_THREADS':'2'});p.start();self.addCleanup(p.stop)
    def write(self):w.save(self.build/'prepared.json',self.m)
    def proof(self):
        p=self.build/'card3-exact';p.mkdir();e=dict(passed=True,prepared_sha256=w.sha(self.build/'prepared.json'),runs=[])
        for j in range(2):
            folder=p/f'owner{j}';folder.mkdir();raw=dict(error='',checks=2,packet4_device_checks=1,authority='packet4-core-on-device-v1',teardown=dict(safe_to_exit=True,idle_marker_complete=True,live_bytes=0,in_flight=0,exit_code=0,status='complete',error='',sequence=['context-released']))
            (folder/'a.fixture.core').write_bytes(b'core-output')
            watch=dict(returncode=0,stop_reason=None);w.save(folder/'device.json',raw);w.save(folder/'watch.json',watch)
            e['runs'].append(dict(device=raw,watch=watch,packet4_device_hashes={'a.fixture':w.sha(folder/'a.fixture.core')},device_sha256=w.sha(folder/'device.json'),watch_sha256=w.sha(folder/'watch.json')))
        w.save(p/'window.json',e);return p/'window.json'
    def test_exact_admitted(self):w.check('exactness',self.output)
    def test_cpu_failure_is_diagnostic_only(self):self.m['cpu_exactness_passed']=False;self.write();w.check('exactness',self.output)
    def test_cpu_failure_blocks_timing(self):
        self.m['cpu_exactness_passed']=False;self.write()
        with self.assertRaisesRegex(ValueError,'CPU exactness'):w.check('timing',self.output)
    def test_hash_mutation(self):
        (self.root/'source').write_text('changed')
        with self.assertRaisesRegex(ValueError,'identity changed'):w.check('exactness',self.output)
    def test_existing_output(self):
        self.output.mkdir()
        with self.assertRaises(ValueError):w.check('exactness',self.output)
    def test_fault_latch(self):
        w.LATCH.write_text('{}')
        with self.assertRaisesRegex(ValueError,'latch'):w.check('exactness',self.output)
    def test_missing_coverage(self):
        (self.fixtures/'cases.txt').write_text('')
        with self.assertRaisesRegex(ValueError,'coverage'):w.check('exactness',self.output)
    def test_no_proof(self):
        with self.assertRaisesRegex(ValueError,'needs'):w.check('timing',self.output)
    def test_valid_timing(self):w.check('timing',self.output,self.proof())
    def test_changed_receipt(self):
        p=self.proof();(p.parent/'owner1/a.fixture.core').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'fresh-owner identity'):w.check('timing',self.output,p)
        (p.parent/'owner1/device.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'bytes changed'):w.check('timing',self.output,p)
    def test_incomplete_fresh_owner(self):
        p=self.proof();e=json.loads(p.read_text());e['runs'][0]['device']['packet4_device_checks']=0;w.save(p,e)
        with self.assertRaisesRegex(ValueError,'incomplete exactness'):w.check('timing',self.output,p)
        e['runs'].pop();w.save(p,e)
        with self.assertRaisesRegex(ValueError,'two fresh'):w.check('timing',self.output,p)
    def test_unsafe_teardown(self):
        self.assertFalse(w.teardown_ok(dict(error='',teardown={'safe_to_exit':True})))
    def test_summarize_real_rows(self):
        rows=[dict(kind='layer_census',layer_type=k,M=m,repeat=r,non_gemv_device_ms=.2,wall_ms=.3,kernel_submissions=14) for owner in range(2) for k in ('gdn','qsa') for m in (1,87) for r in range(6)]
        self.assertEqual(len(w.summarize(rows)['rows']),4)
        with self.assertRaises(ValueError):w.summarize(rows[:-1])
    def test_summary_failure_cannot_pass_window(self):
        proof=self.proof()
        raw=json.loads((proof.parent/'owner0/device.json').read_text());raw['checks']=6
        def watch(command,out,journal,fault):
            out.mkdir();(out/'a.fixture.core').write_bytes(b'core-output');w.save(out/'device.json',raw);result=dict(returncode=0,stop_reason=None);w.save(out/'watch.json',result);(out/'timings.jsonl').write_text('');return result
        with patch.object(w,'watch',side_effect=watch):result=w.execute('timing',self.output,proof)
        self.assertFalse(result['passed']);self.assertIn('five timed repeats',result['error'])
    def watch_case(self,kind):
        import re,signal
        from unittest.mock import Mock
        child=Mock();child.pid=1234;child.returncode=0
        child.poll.side_effect=[None,0] if kind!='clean' else [0]
        calls=[0]
        def journal(cursor=None):
            calls[0]+=1
            if calls[0]==2 and kind=='journal':raise RuntimeError('lost')
            return ('Fault response' if calls[0]==2 and kind=='fault' else '', 'cursor')
        with patch.object(w.subprocess,'Popen',return_value=child) as launch,patch.object(w.time,'sleep'),patch.object(w.time,'monotonic',side_effect=[0,901 if kind=='deadline' else 1,902]):
            result=w.watch(['fake-native'],self.build/'watch',journal,re.compile('Fault response'))
        self.assertEqual(launch.call_count,1)
        if kind=='clean':self.assertIsNone(result['stop_reason']);child.send_signal.assert_not_called()
        else:self.assertIsNotNone(result['stop_reason']);child.send_signal.assert_called_once_with(signal.SIGTERM);self.assertTrue(w.LATCH.exists())
    def test_watch_clean(self):self.watch_case('clean')
    def test_watch_fault(self):self.watch_case('fault')
    def test_watch_journal_lost(self):self.watch_case('journal')
    def test_watch_deadline(self):self.watch_case('deadline')
if __name__=='__main__':unittest.main()
