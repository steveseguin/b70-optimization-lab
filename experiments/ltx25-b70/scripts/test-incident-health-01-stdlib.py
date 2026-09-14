#!/usr/bin/env python3
"""Pure historical-journal/source tests; obsolete diagnostic is never executed."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

LANE = Path(__file__).resolve().parents[1]
SOURCE = LANE / 'scripts/check-incident-health-01.py'
ADMISSION = LANE / 'data/incident-health-01/admission.json'
JOURNAL = LANE / 'data/incident-health-01/journal-baseline.jsonl'
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
    def test_exact_historical_prefix_accepts_known_incident_only(self):
        report=namespace['check_journal_records'](self.records,self.a)
        self.assertEqual(report['historical_records'],2403)
        self.assertEqual(report['new_records'],0)
        self.assertEqual(len(self.a['historical_faults']),5)
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
        self.records.append(copy.deepcopy(self.a['historical_faults'][-1]))
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
        self.a['boot_id']='5414a640-c223-4a67-baa2-ec2f4c4c5917'
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

if __name__=='__main__':unittest.main()
