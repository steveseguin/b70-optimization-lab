#!/usr/bin/env python3
"""Source identity and guard regression only; never import the native fixture."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
DRIVER=HERE/'test-host-embedding-resident-lifecycle-cpu.py'
FIXTURE=HERE/'test-host-embedding-resident-lifecycle-cpu-fixture.py'
PREVIOUS=HERE/'test-host-embedding-integration-cpu.py'
spec=importlib.util.spec_from_file_location('resident_lifecycle_source_driver',DRIVER)
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)

def definition(path,name):
    return next(n for n in ast.parse(path.read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)

class Tests(unittest.TestCase):
    def test_all_frozen_helper_and_native_source_pins(self):
        for name,digest in driver.HELPERS.items():
            self.assertEqual(driver.sha(driver.LANE/name),digest,name)
        self.assertEqual(driver.sha(driver.SOURCE/'comfy/model_management.py'),driver.COMFY_MANAGEMENT_SHA)
        self.assertEqual(driver.sha(driver.TRITON_UTILS),driver.TRITON_SHA)
        original=ast.parse((HERE/'test-host-embedding-candidate-cpu-fixture-v2.py').read_text())
        pins=ast.literal_eval(next(n.value for n in original.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='PINS' for x in n.targets)))
        for name,digest in pins.items():self.assertEqual(driver.sha(driver.SOURCE/name),digest)
        self.assertEqual(driver.sha(driver.SOURCE/'comfy/sd.py'),'41cbf195657cc81a60173f13f192966c4276bf7931a6c10f75870a66c59546b0')
    def test_actual_previous_cpu_qualification_bound(self):
        self.assertEqual(driver.sha(driver.INTEGRATION_QUALIFICATION),driver.INTEGRATION_QUALIFICATION_SHA)
        receipt=json.loads(driver.INTEGRATION_QUALIFICATION.read_text())
        self.assertEqual(receipt['status'],'passed-guarded-cpu-integration')
        self.assertEqual(receipt['tests_run'],6)
        for name in ['host_embedding_clip_v2.py','host_embedding_placement_node_v2.py']:
            self.assertEqual(receipt['helper_sha256s']['scripts/'+name],driver.HELPERS['scripts/'+name])
    def test_fault_guard_is_exact_first_operation(self):
        old=definition(PREVIOUS,'source_gate');new=definition(DRIVER,'source_gate')
        self.assertEqual(ast.dump(old.body[0]),ast.dump(new.body[0]))
        self.assertIn("ROOT / 'FAULT.json'",ast.unparse(new.body[0]))
        # If a real latch exists, exercise its actual refusal without masking it.
        if (driver.ROOT/'FAULT.json').exists():
            with self.assertRaisesRegex(RuntimeError,'Fault latch'):driver.source_gate()
        self.assertNotIn('torch',sys.modules)
    def test_backend_and_failure_guards_unchanged(self):
        for name in ['install_backend_refusals','StopOnFailureResult','write_exclusive']:
            self.assertEqual(ast.dump(definition(DRIVER,name)),ast.dump(definition(PREVIOUS,name)),name)
    def test_import_startup_and_guard_order_unchanged(self):
        old=PREVIOUS.read_text();new=DRIVER.read_text()
        start="        report['phase'] = 'torch-import'"
        end="        fixture = load("
        self.assertEqual(old[old.index(start):old.index(end)],new[new.index(start):new.index(end)])
        for text in [old,new]:
            self.assertLess(text.index("write_exclusive(directory / 'startup-identity.json'"),text.index('import torch as imported_torch'))
            self.assertLess(text.index('if args.check_only:'),text.index('import torch as imported_torch'))
            self.assertLess(text.index('report[\'source_pins\'] = source_gate()'),text.index('import torch as imported_torch'))
    def test_actual_registry_functions_not_mocked(self):
        text=FIXTURE.read_text();tree=ast.parse(text)
        targets=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='object' and len(n.args)>1 and isinstance(n.args[1],ast.Constant):
                targets.append(n.args[1].value)
        self.assertFalse({'load_models_gpu','loaded_models','cleanup_models','ModelPatcher','CLIP','retirement_refs','require_dead'} & set(targets))
        self.assertIn('base.adapted',text);self.assertIn('mm.loaded_models()',text)
        self.assertIn('mm.cleanup_models()',text);self.assertIn("clip.clone()",text)
        self.assertIn("clip.cond_stage_model",text);self.assertIn("held=outputs",text)
        self.assertNotIn('current_loaded_models',text)
    def test_six_cases_raw_bytes_and_receipt_evidence(self):
        cls=definition(FIXTURE,'Tests')
        names=[n.name for n in cls.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
        self.assertEqual(len(names),6)
        text=FIXTURE.read_text()
        for expected in ['base.base.raw(actual)','tuple(actual.stride())',"release['retired_patcher_ids_absent_from_registry']",
                         'all(ref() is None for ref in old_refs.values())',"self.assertEqual(a.constructed,3)"]:
            self.assertIn(expected,text)
        d=DRIVER.read_text();self.assertIn("write_exclusive(directory / 'fixture-evidence.json', fixture.EVIDENCE)",d)
        self.assertIn('result.testsRun == 6 and not result.skipped',d)
        self.assertIn('passed-guarded-cpu-resident-lifecycle',d)
    def test_memory_fakes_only_no_native_import_by_preparation(self):
        text=FIXTURE.read_text()
        self.assertIn("'fixture_geometry_only':True",text)
        self.assertIn("'source':'synthetic fixture MemAvailable; no large allocation'",text)
        self.assertNotIn('torch.empty(',text);self.assertNotIn('torch.zeros(',text)
        self.assertNotIn('torch',sys.modules);self.assertFalse(any(k.startswith('comfy.') for k in sys.modules))

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'status':'passed' if result.wasSuccessful() else 'failed','tests_run':result.testsRun,
        'scope':'stdlib hashes/AST and existing fault refusal only; actual CPU fixture not imported or run',
        'torch_imported':'torch' in sys.modules,'native_cpu_tests_executed':False,'endpoint_calls':0,
        'fault_latch_present':(driver.ROOT/'FAULT.json').exists(),
        'source_sha256s':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [DRIVER,FIXTURE,Path(__file__)]}}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
