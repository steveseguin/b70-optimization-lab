"""Fake child/clock and temporary evidence only; never spawn or inspect a process."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

R = load(HERE / 'driver_accounting_runner.py', 'runner_tested')
FIXTURE = load(HERE.parent / '20261007-driver-accounting106/test_collector.py', 'accounting_fixture')


class Child:
    pid = 456
    def __init__(self): self.code = None; self.calls = 0
    def poll(self): self.calls += 1; return self.code
    def terminate(self): raise AssertionError('No signal permitted')
    kill = terminate
    send_signal = terminate
    def wait(self, *args, **kwargs): raise AssertionError('Use bounded polling only')


class Tests(unittest.TestCase):
    def setUp(self):
        f = FIXTURE.Tests(); f.setUp(); self.addCleanup(f.doCleanups)
        self.f = f; self.root = f.root; self.clock = 100.0
        self.run = self.root/'server'; self.output = self.run/'driver-accounting.jsonl'
        self.contract_path = self.run/'driver-accounting-contract.json'
        self.contract_path.write_bytes(FIXTURE.C.canonical(f.c))
        identity = json.loads(Path(f.c['bindings']['server_identity']['path']).read_bytes())
        self.c = {'server_run': str(self.run), 'root': str(self.root),
                  'runtime_manifest_sha256': f.c['runtime_manifest_sha256'],
                  'server_identity_sha256': f.c['bindings']['server_identity']['sha256'],
                  'plan_sha256': f.c['plan_sha256'], 'plan_path': f.c['bindings']['plan']['path'],
                  'driver_accounting_contract_path': str(self.contract_path),
                  'driver_accounting_contract_sha256': R.sha(self.contract_path.read_bytes()),
                  'source_bindings': {str(p): R.sha(p.read_bytes()) for p in
                                      (HERE/'driver_accounting_runner.py',HERE/'driver_accounting.py')}}
        self.client = type('Client', (), {})()
        self.client.run = self.run; self.client.contract_path = self.root/'client.json'
        self.client.identity = identity; self.client.plan = {'qualification_id': f.c['qualification_id']}
        self.save_client(); self.child = Child(); self.calls = []
        self.runner = R.DriverAccounting(self.client)
        self.start_content = None; self.sleep_hook = None
        for obj, name, replacement in [(R.subprocess, 'Popen', self.spawn),
                                        (R.time, 'monotonic', lambda:self.clock),
                                        (R.time, 'monotonic_ns', lambda:int(self.clock*1e9)),
                                        (R.time, 'sleep', self.sleep)]:
            p=patch.object(obj,name,side_effect=replacement);p.start();self.addCleanup(p.stop)

    def save_client(self):
        self.client.contract=self.c
        self.client.contract_path.write_bytes(FIXTURE.C.canonical(self.c))
        self.client.contract_sha=R.sha(self.client.contract_path.read_bytes())

    def header(self):
        c=self.f.c
        return {'schema':'ltx.raw-drm-snapshots.v1','contract_sha256':self.c['driver_accounting_contract_sha256'],
                'collector_sha256':R.COLLECTOR_SHA,'bindings':c['bindings'],'ordered_xpu_mapping':c['ordered_xpu_mapping'],
                **{k:c[k] for k in ('pid','start_ticks','boot_id')},
                'limits':dict(seconds=120,samples=64,bytes=131072,interval=2)}

    def sample(self,complete=True):
        return {'complete':complete,'issues':[] if complete else ['missing-admitted-render-node'],
                'clients':{'0000:23:00.0/99':{'pci':'0000:23:00.0'}},
                'monotonic_start_ns':int(self.clock*1e9),'monotonic_end_ns':int(self.clock*1e9)+1,
                'scheduled_sample':0}

    def write(self,rows,mode='wb'):
        with self.output.open(mode) as stream:
            for row in rows:stream.write(FIXTURE.C.canonical(row)+b'\n')

    def spawn(self,args,**kwargs):
        self.calls.append((args,kwargs))
        if self.start_content is None:self.write([self.header(),self.sample()])
        else:self.start_content()
        return self.child

    def sleep(self,seconds):
        self.clock+=seconds
        if self.sleep_hook:self.sleep_hook()

    def finish_file(self,status='duration-cap',samples=1,missed=0,code=0):
        self.write([dict(terminal=status,samples_recorded=samples,missed_slots=missed)],'ab')
        self.child.code=code

    def test_exact_one_child_and_raw_success(self):
        ready=self.runner.start();self.assertTrue(ready['ready']);self.assertEqual(len(self.calls),1)
        args,kw=self.calls[0]
        self.assertEqual(args,[sys.executable,'-B',str(HERE/'driver_accounting.py'),'--contract',str(self.contract_path),
                               '--contract-sha256',self.c['driver_accounting_contract_sha256'],'--output',str(self.output)])
        self.assertIs(kw['shell'],False);self.assertTrue(kw['close_fds'])
        self.finish_file();result=self.runner.finish()
        self.assertTrue(result['valid']);self.assertFalse(result['child_running'])
        self.assertEqual(result['complete_samples'],1)
        self.assertEqual(result['files']['output']['sha256'],R.sha(self.output.read_bytes()))
        self.assertIn('no utilization',result['claim_scope'])
        self.assertIs(self.runner.finish(),result)
        with self.assertRaisesRegex(R.AccountingError,'already owned'):self.runner.start()
        self.assertEqual(len(self.calls),1)

    def test_existing_output_and_unbound_source_refuse_before_spawn(self):
        self.output.write_bytes(b'keep')
        with self.assertRaisesRegex(R.AccountingError,'already exists'):self.runner.start()
        self.assertEqual(self.calls,[]);self.assertEqual(self.output.read_bytes(),b'keep')
        self.output.unlink();self.runner=R.DriverAccounting(self.client)
        self.c['source_bindings'][str(HERE/'driver_accounting.py')]='0'*64;self.save_client()
        with self.assertRaisesRegex(R.AccountingError,'Unbound'):self.runner.start()
        self.assertEqual(self.calls,[])

    def test_contract_path_and_server_plan_cannot_be_substituted(self):
        self.c['driver_accounting_contract_path']=str(self.root/'other.json');self.save_client()
        with self.assertRaisesRegex(R.AccountingError,'contract path'):self.runner.start()
        self.assertEqual(self.calls,[])
        self.c['driver_accounting_contract_path']=str(self.contract_path)
        self.c['plan_sha256']='0'*64;self.save_client();self.runner=R.DriverAccounting(self.client)
        with self.assertRaisesRegex(R.AccountingError,'server identity'):self.runner.start()
        self.assertEqual(self.calls,[])

    def test_header_identity_mismatch_and_unowned_child_refused(self):
        def bad_header():
            h=self.header();h['pid']=999;self.write([h,self.sample()])
        self.start_content=bad_header
        with self.assertRaisesRegex(R.AccountingError,'header identity'):self.runner.start()
        self.assertEqual(len(self.calls),1)
        self.output.unlink();self.runner=R.DriverAccounting(self.client);self.start_content=None
        self.child.pid=self.client.identity['pid']
        with self.assertRaisesRegex(R.AccountingError,'child ownership'):self.runner.start()
        result=self.runner.finish();self.assertFalse(result['valid']);self.assertFalse(result['child_owned'])

    def test_readiness_needs_complete_sample_not_header_or_partial_line(self):
        partial=FIXTURE.C.canonical(self.sample())+b'\n'
        def partial_start():
            self.write([self.header()])
            with self.output.open('ab') as stream:stream.write(partial[:-2])
        self.start_content=partial_start
        def complete_later():
            if self.clock>=100.6 and not getattr(self,'appended',False):
                self.appended=True
                with self.output.open('ab') as stream:stream.write(partial[-2:])
        self.sleep_hook=complete_later
        self.assertTrue(self.runner.start()['ready']);self.assertGreaterEqual(self.clock,100.6)
        self.assertEqual(len(self.calls),1)

    def test_readiness_timeout_and_early_exit_never_retry_or_signal(self):
        self.start_content=lambda:self.write([self.header()])
        with self.assertRaisesRegex(R.AccountingError,'readiness timeout'):self.runner.start()
        self.assertAlmostEqual(self.clock,110);self.assertEqual(len(self.calls),1)
        result=self.runner.finish();self.assertFalse(result['valid']);self.assertTrue(result['child_running'])
        self.output.unlink();self.runner=R.DriverAccounting(self.client);self.child.code=1
        with self.assertRaisesRegex(R.AccountingError,'exited before readiness'):self.runner.start()
        self.assertEqual(len(self.calls),2)

    def test_finish_waits_only_original_deadline_and_leaves_child_unsignalled(self):
        self.runner.start();self.clock=225
        result=self.runner.finish()
        self.assertFalse(result['valid']);self.assertTrue(result['child_running']);self.assertEqual(self.clock,230)
        self.assertIn('original deadline',result['reason']);self.assertEqual(len(self.calls),1)

    def test_finish_waits_for_normal_child_then_records_terminal(self):
        self.runner.start();self.clock=219
        def done():
            if self.clock>=220 and self.child.code is None:self.finish_file()
        self.sleep_hook=done
        result=self.runner.finish();self.assertTrue(result['valid']);self.assertEqual(self.clock,220)

    def test_incomplete_samples_and_terminal_counts_fail_diagnostic_only(self):
        self.runner.start();self.clock+=2;self.write([self.sample(False)],'ab');self.finish_file(samples=2)
        result=self.runner.finish();self.assertFalse(result['valid']);self.assertEqual(result['incomplete_samples'],1)
        self.assertIn('coverage incomplete',result['reason'])

    def test_terminal_error_bad_counts_and_truncated_tail_refused(self):
        for status,count,tail in [('observation-stopped',1,b''),('duration-cap',2,b''),('duration-cap',1,b'{')]:
            with self.subTest(status=status,count=count,tail=tail):
                if self.output.exists():self.output.unlink()
                self.runner=R.DriverAccounting(self.client);self.child=Child();self.runner.start()
                self.finish_file(status=status,samples=count)
                if tail:
                    with self.output.open('ab') as stream:stream.write(tail)
                result=self.runner.finish();self.assertFalse(result['valid'])

    def test_poststart_source_or_output_rewrite_invalidates(self):
        self.runner.start();self.finish_file()
        self.c['source_bindings'][str(HERE/'driver_accounting_runner.py')]='0'*64;self.save_client()
        result=self.runner.finish();self.assertFalse(result['valid']);self.assertIn('Unbound',result['reason'])
        self.c['source_bindings'][str(HERE/'driver_accounting_runner.py')]=R.sha((HERE/'driver_accounting_runner.py').read_bytes())
        self.save_client();self.output.unlink();self.child=Child();self.runner=R.DriverAccounting(self.client)
        self.runner.start();self.finish_file();raw=self.output.read_bytes();self.output.unlink();self.output.write_bytes(raw)
        result=self.runner.finish();self.assertFalse(result['valid']);self.assertIn('replaced',result['reason'])

    def test_never_started_finish_is_invalid_without_process_operations(self):
        result=self.runner.finish();self.assertFalse(result['valid']);self.assertFalse(result['child_owned'])
        self.assertIsNone(result['child_running']);self.assertEqual(self.calls,[])

    def test_child_poll_failure_becomes_invalid_result(self):
        self.runner.start()
        with patch.object(self.child,'poll',side_effect=OSError('synthetic child failure')):
            result=self.runner.finish()
        self.assertFalse(result['valid']);self.assertIn('synthetic child failure',result['reason'])
        self.assertEqual(len(self.calls),1)

    def test_readiness_rejects_counter_sample_before_owned_start(self):
        def old_sample():
            sample=self.sample();sample['monotonic_start_ns']=1;sample['monotonic_end_ns']=2
            self.write([self.header(),sample])
        self.start_content=old_sample
        with self.assertRaisesRegex(R.AccountingError,'chronology'):self.runner.start()
        self.assertEqual(len(self.calls),1)


if __name__=='__main__':unittest.main(verbosity=2)
