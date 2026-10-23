"""CPU mocks only: no operational manifest, journal, service or owner launch."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('p201_test_run_adapter',Path(__file__).with_name('run.py'))
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.manifest=self.root/'absent-manifest.json'
        p=patch.object(A,'MANIFEST',self.manifest);p.start();self.addCleanup(p.stop)

    def test_missing_manifest_refuses_both_operations_before_plan_capture_or_owner(self):
        for option in ('--authorized-device-window','--capture-fault-review','--verify-admission'):
            with self.subTest(option=option),patch.object(A,'plan') as plan,patch.object(A,'capture_fault_review') as capture,patch.object(A.W,'execute') as execute:
                with self.assertRaises(FileNotFoundError):A.main([option])
                plan.assert_not_called();capture.assert_not_called();execute.assert_not_called()

    def test_wrong_paths_refuse_before_admission(self):
        with patch.object(A,'admitted_plan') as admit:
            with self.assertRaisesRegex(RuntimeError,'fixed'):A.main(['--authorized-device-window','--output',str(self.root)])
            admit.assert_not_called()

    def test_readonly_plan_never_enters_admission(self):
        with patch.object(A,'plan',return_value={'cpu':True}),patch.object(A,'admitted_plan') as admit:
            self.assertEqual(A.main(['--plan']),0);admit.assert_not_called()

    def write_manifest(self):
        source=self.root/'source.py';source.write_text('# synthetic fixture\n')
        row=dict(schema='packet201.execution-admission.v1',passed=True,operational_launch_authorized=True,
                 storage_admission_mode='monitored-forecast',storage_bound_proven=False,
                 source_sha256={'source.py':A.sha(source)})
        self.manifest.write_text(json.dumps(row));return source,row

    def test_required_source_and_exact_hash_binding(self):
        source,row=self.write_manifest()
        with patch.object(A,'ROOT',self.root),patch.object(A,'required_sources',return_value=[source]),patch.object(A.W,'integration_origins'):
            _,digest=A.verify_manifest();self.assertEqual(A.verify_manifest(digest)[0],row)
            with self.assertRaisesRegex(RuntimeError,'manifest changed'):A.verify_manifest('0'*64)
            source.write_text('# drift\n')
            with self.assertRaisesRegex(RuntimeError,'source drift'):A.verify_manifest()

    def test_missing_adapter_or_claim_promotion_refused(self):
        source,row=self.write_manifest()
        with patch.object(A,'ROOT',self.root),patch.object(A,'required_sources',return_value=[source,self.root/'missing.py']):
            with self.assertRaisesRegex(RuntimeError,'closure incomplete'):A.verify_manifest()
        row['storage_bound_proven']=True;self.manifest.write_text(json.dumps(row))
        with self.assertRaisesRegex(RuntimeError,'certified'):A.verify_manifest()

    def test_exact_execute_wrapper_not_a_second_native_launcher(self):
        with patch.object(A,'admitted_plan',return_value=({'mock':True},'hash')),patch.object(A,'verify_manifest'),patch.object(A.W,'execute',return_value=0) as execute:
            self.assertEqual(A.main(['--authorized-device-window']),0)
            execute.assert_called_once_with({'mock':True},fault_review=A.REVIEW,manifest=self.manifest)

    def test_stage_replacement_refuses_before_plan_or_worker_authorization(self):
        from types import SimpleNamespace
        contract=SimpleNamespace(staging_identity=lambda p:{'inode':2})
        with patch.object(A,'verify_manifest',return_value=({'controller':{'staging_identity':{'inode':1}}},'hash')),patch.object(A,'load',return_value=contract),patch.object(A,'plan') as plan,patch.object(A.W,'authorize') as auth:
            with self.assertRaisesRegex(RuntimeError,'staging identity changed'):A.admitted_plan()
            plan.assert_not_called();auth.assert_not_called()

    def test_full_worker_authorization_required_for_admitted_plan(self):
        from types import SimpleNamespace
        contract=SimpleNamespace(staging_identity=lambda p:{'inode':1})
        with patch.object(A,'verify_manifest',return_value=({'controller':{'staging_identity':{'inode':1}}},'hash')),patch.object(A,'load',return_value=contract),patch.object(A,'plan',return_value={}),patch.object(A.W,'authorize',side_effect=RuntimeError('core closure missing')):
            with self.assertRaisesRegex(RuntimeError,'core closure missing'):A.admitted_plan()

    def test_existing_capture_refuses_without_journal(self):
        review=self.root/'review.json';review.write_text('retained')
        with patch.object(A,'REVIEW',review),patch.object(A.W,'Safety') as safety:
            with self.assertRaisesRegex(RuntimeError,'fresh'):A.capture_fault_review({})
            safety.assert_not_called();self.assertEqual(review.read_text(),'retained')

    def test_fixed_argv_and_complete_additive_sources(self):
        argv=A.worker_argv()
        self.assertEqual(argv[:3],[A.PYTHON,'-B',str(A.P/'run.py')])
        self.assertEqual(argv[argv.index('--activity-mode')+1],'launch')
        self.assertEqual({p.name for p in A.required_sources()},
                         {'run.py','test_run.py','client_pilot.py','test_client_pilot.py','client-vectors.json','CLIENT.md','client-cpu-tests.json','driver.py','helpers.py','restore_guard.py','test_driver.py','DRIVER.md','window.py','test_window.py','helper-pins.json'}|
                         {f'{i:02d}-{kind}.json' for i in range(1,17) for kind in ('http','native')})
        self.assertEqual(len(A.required_sources()),48)


if __name__=='__main__':unittest.main()
