#!/usr/bin/env python3
"""Execute actual successor helper AST with stdlib fakes; no native/client import."""
import ast
import hashlib
import json
from pathlib import Path
import unittest

SOURCE=Path(__file__).with_name('run-host-embedding-screen-v2.py')
tree=ast.parse(SOURCE.read_text())
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_with_post_snapshot')
space={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(SOURCE),'exec'),space)
run=space['run_with_post_snapshot']

def fail(error):
    raise error

class Tests(unittest.TestCase):
    def test_primary_failure_survives_missing_server(self):
        primary=RuntimeError('profile helper failed: server disconnected');secondary=FileNotFoundError('/proc/116013/status')
        record={}
        with self.assertRaises(RuntimeError) as caught:run(lambda:fail(primary),lambda:fail(secondary),record)
        self.assertIs(caught.exception,primary);self.assertEqual(record['after_snapshot_error']['error'],repr(secondary))
        self.assertNotIn('after',record)
    def test_successful_request_snapshot_failure_is_fatal(self):
        secondary=FileNotFoundError('missing');record={}
        with self.assertRaises(FileNotFoundError) as caught:run(lambda:None,lambda:fail(secondary),record)
        self.assertIs(caught.exception,secondary);self.assertNotIn('after_snapshot_error',record)
    def test_primary_failure_with_snapshot_preserved(self):
        primary=KeyboardInterrupt();record={}
        with self.assertRaises(KeyboardInterrupt) as caught:run(lambda:fail(primary),lambda:{'cpu':'metadata'},record)
        self.assertIs(caught.exception,primary);self.assertEqual(record['after'],{'cpu':'metadata'})
    def test_success_preserved(self):
        record={};run(lambda:None,lambda:{'success':True},record)
        self.assertEqual(record,{'after':{'success':True}})

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'status':'passed' if result.wasSuccessful() else 'failed','tests_run':result.testsRun,
        'scope':'stdlib actual helper AST with fake request and snapshot callbacks; no endpoint/native/client actions',
        'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
