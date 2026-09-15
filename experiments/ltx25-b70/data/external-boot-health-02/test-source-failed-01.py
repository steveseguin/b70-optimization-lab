#!/usr/bin/env python3
"""Pure new-boot journal/source tests; diagnostic is never executed."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

LANE = Path(__file__).resolve().parents[1]
SOURCE = LANE / 'scripts/check-external-boot-health-02.py'
ADMISSION = LANE / 'data/external-boot-health-02/admission.json'
JOURNAL = LANE / 'data/external-boot-health-02/journal-baseline.jsonl'
TREE = ast.parse(SOURCE.read_text())
FUNCTIONS = {node.name: node for node in TREE.body if isinstance(node, ast.FunctionDef)}
# Load only the existing pure detector. Never import the diagnostic/common module.
spec = importlib.util.spec_from_file_location('incident_journal_detector', LANE / 'scripts/kernel_fault_detector.py')
detector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(detector)
namespace = {'hashlib': hashlib, 'json': json, 'matching_lines': detector.matching_lines}
exec(compile(ast.Module(body=[FUNCTIONS[name] for name in ('require','canonical_sha','new_fault','check_journal_records')],
                       type_ignores=[]), '<pure-journal-functions>', 'exec'), namespace)
fields = ('__CURSOR','_BOOT_ID','__MONOTONIC_TIMESTAMP','__REALTIME_TIMESTAMP','MESSAGE','PRIORITY')
BASELINE = [{key: row[key] for key in fields} for row in map(json.loads, JOURNAL.read_text().splitlines())]

class Tests(unittest.TestCase):
    def setUp(self):
        self.a=json.loads(ADMISSION.read_text())
        self.records=copy.deepcopy(BASELINE)
    def append(self,message,priority='6'):
        value=dict(self.records[-1],MESSAGE=message,PRIORITY=priority,__CURSOR='synthetic-new-record')
        self.records.append(value)
    def test_exact_fault_free_historical_prefix(self):
        report=namespace['check_journal_records'](self.records,self.a)
        self.assertEqual(report['historical_records'],2261)
        self.assertEqual(report['new_records'],0)
        self.assertEqual(len(self.a['historical_faults']),0)
        self.assertFalse(any(namespace['new_fault'](r) for r in self.records))
        self.assertTrue(all(value in self.records for value in self.a['historical_faults']))
    def test_missing_or_changed_historical_record_refused(self):
        for changed in (self.records[1:],self.records[:-1]):
            with self.assertRaises(RuntimeError):namespace['check_journal_records'](changed,self.a)
        self.records[0]['MESSAGE']+='changed'
        with self.assertRaises(RuntimeError):namespace['check_journal_records'](self.records,self.a)
    def test_new_benign_record_allowed(self):
        self.append('benign informational test fixture')
        self.assertEqual(namespace['check_journal_records'](self.records,self.a)['new_records'],1)
    def test_replayed_historical_fault_after_prefix_refused(self):
        self.append('xe fixture Engine reset: historical incident replay')
        with self.assertRaises(RuntimeError):namespace['check_journal_records'](self.records,self.a)
    def test_new_oom_forms_refused(self):
        for message in ('systemd invoked oom-killer: fixture','oom-kill: global_oom','Out of memory: Killed process 1'):
            self.records=copy.deepcopy(BASELINE);self.append(message)
            with self.subTest(message=message),self.assertRaises(RuntimeError):namespace['check_journal_records'](self.records,self.a)
    def test_new_device_or_host_fault_refused(self):
        for message in ('xe fixture Engine reset: test','Fault response: Unsuccessful -ENOENT',
                        'BUG: soft lockup - CPU#1 stuck for 23s!','INFO: task python:123 blocked for more than 122 seconds.'):
            self.records=copy.deepcopy(BASELINE);self.append(message)
            with self.subTest(message=message),self.assertRaises(RuntimeError):namespace['check_journal_records'](self.records,self.a)
    def test_unrecognized_error_priority_refused(self):
        self.append('Unrecognized kernel error','3')
        with self.assertRaises(RuntimeError):namespace['check_journal_records'](self.records,self.a)
    def test_new_boot_never_reuses_old_admission(self):
        self.a['boot_id']='8e4b1b65-1c38-47bb-8ca5-e4fd6bbdf94a'
        with self.assertRaises(RuntimeError):namespace['check_journal_records'](self.records,self.a)
    def test_peer_source_gate_precedes_allocation(self):
        worker=FUNCTIONS['worker']
        source_loop=next(node for node in ast.walk(worker) if isinstance(node,ast.For) and ast.unparse(node.target)=='source')
        first=[ast.unparse(node) for node in source_loop.body[:3]]
        self.assertEqual(first[0],'identity()')
        self.assertTrue(first[1].startswith('journal('))
        self.assertTrue(first[2].startswith('value = torch.full('))
    def test_one_native_child_and_inherited_locks(self):
        calls=[node for node in ast.walk(TREE) if isinstance(node,ast.Call) and ast.unparse(node.func)=='subprocess.Popen']
        self.assertEqual(len(calls),1)
        self.assertIn(('pass_fds','fds'),[(k.arg,ast.unparse(k.value)) for k in calls[0].keywords])
        self.assertIn("'one_graceful_interrupt_sent'",ast.unparse(FUNCTIONS['main']))
    def test_no_reset_kill_retry_or_fault_clear_operations(self):
        calls=[ast.unparse(node.func) for node in ast.walk(TREE) if isinstance(node,ast.Call)]
        self.assertFalse(any(name.endswith(('.kill','.terminate','.unlink','.rmdir','.rename')) for name in calls))
        self.assertNotIn('SIGKILL',SOURCE.read_text())
        self.assertEqual(sum(isinstance(node,ast.Import) and any(x.name=='torch' for x in node.names) for node in ast.walk(TREE)),1)
    def test_old_source_still_uses_exact_admission_pin(self):
        pin=next(node.value.value for node in TREE.body if isinstance(node,ast.Assign)
                 and any(isinstance(x,ast.Name) and x.id=='ADMISSION_SHA' for x in node.targets))
        self.assertEqual(hashlib.sha256(ADMISSION.read_bytes()).hexdigest(),pin)

    def test_helpers_and_admission_are_exactly_pinned(self):
        pins=next(ast.literal_eval(node.value) for node in TREE.body if isinstance(node,ast.Assign)
                  and any(isinstance(x,ast.Name) and x.id=='HELPER_PINS' for x in node.targets))
        self.assertEqual(set(pins),{'encoder_runtime_common.py','kernel_fault_detector.py'})
        for name,pin in pins.items():
            self.assertEqual(hashlib.sha256((LANE/'scripts'/name).read_bytes()).hexdigest(),pin)
        identity=ast.unparse(FUNCTIONS['identity'])
        for term in ('HELPER_PINS.items()', 'common.sha(ADMISSION) == ADMISSION_SHA',
                     "common.sha(common.ROOT / 'FAULT.json') == a['fault_sha256']", 'common.verify_runtime'):
            self.assertIn(term,identity)
    def test_parent_closure_and_exclusive_worker_receipt_precede_torch(self):
        worker=FUNCTIONS['worker']
        text=ast.unparse(worker)
        for term in ("parent['pid'] == parent_pid", "parent['boot_id'] == a['boot_id']",
                     "parent['admission_sha256'] == ADMISSION_SHA", "parent['source_sha256'] == common.sha(Path(__file__))"):
            self.assertIn(term,text)
        self.assertLess(text.index("write(OUT / 'worker-started.json'"),text.index('import torch'))
        self.assertIn("path.open('x')",ast.unparse(FUNCTIONS['write']))
    def test_card_and_peer_copy_phase_gates(self):
        worker=FUNCTIONS['worker']
        card=next(n for n in ast.walk(worker) if isinstance(n,ast.For) and ast.unparse(n.target)=='i')
        text=ast.unparse(card)
        self.assertLess(text.index('identity()'),text.index('torch.ones('))
        self.assertLess(text.index('journal('),text.index('torch.ones('))
        self.assertLess(text.index("properties == a['expected_devices'][i]['properties']"),text.index('torch.ones('))
        target=next(n for n in ast.walk(worker) if isinstance(n,ast.For) and ast.unparse(n.target)=='target')
        text=ast.unparse(target)
        self.assertLess(text.index('identity()'),text.index('copied = value.to('))
        self.assertLess(text.index('journal('),text.index('copied = value.to('))
        self.assertEqual([d['ordinal'] for d in self.a['expected_devices']],list(range(4)))
        self.assertTrue(all('uuid=' in d['properties'] and 'driver_version=' in d['properties'] for d in self.a['expected_devices']))
    def test_timeout_remains_bounded_without_retry(self):
        text=ast.unparse(FUNCTIONS['main'])
        self.assertIn("child.wait(timeout=a['native_worker_timeout_seconds'])",text)
        self.assertEqual(self.a['native_worker_timeout_seconds'],60)
        self.assertEqual(self.a['active_probe_limit'],1)
        self.assertEqual(text.count('child.wait(timeout=10)'),2)
        self.assertIn("not report.get('one_graceful_interrupt_sent')",text)
        self.assertFalse(any(isinstance(n,ast.While) for n in ast.walk(FUNCTIONS['main'])))

if __name__=='__main__':unittest.main()
