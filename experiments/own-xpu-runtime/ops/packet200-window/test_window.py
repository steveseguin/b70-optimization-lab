"""CPU-only packet200 contract checks; no operational helper calls."""
import copy
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('packet200_window_contract',Path(__file__).with_name('window.py'))
W=importlib.util.module_from_spec(spec);spec.loader.exec_module(W)


def terminal(count=2):
    return dict(passed=True,runtime_passed=True,evidence_passed=True,owner_exited=True,
        diagnostics_finished=True,devices_drained=True,retained=False,model_loads=1,native_process_count=1,
        incident_sigterm_count=0,owner_returncode=0,store_closed=True,writers_closed=True,coordination_completed=True,
        ready_for_coordination_completion=True,precompletion_written=True,post_completion_evidence_failure=False,
        plan_sha256='plan',storage_admission_mode='monitored-forecast',storage_bound_proven=False,live_profile_ready=False,
        requests=count,controls=count,stopped=dict(event='stopped',safe_to_exit=True,completed_requests=count,
            completed_controls=count,discarded_pending=False,pending_request_id='',reason='quit'),
        diagnostics=dict(eof=True,retained=False,reader_retained=False,capture_retained=False,
            owned_read_fd_open=False,reader_startup_uncertain=False,incident=False))


class WindowContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.stage=self.root/'stage';self.stage.mkdir(mode=0o700)
        self.source=self.root/'worker.py';self.source.write_text('# synthetic source fixture\n')
        self.patcher=patch.object(W,'ROOT',self.root);self.patcher.start();self.addCleanup(self.patcher.stop)
        self.profile=dict(live_admission_ready=False,submission_eligible=False,
            paths=dict(output=str(self.stage/'output'),owner_output=str(self.stage/'output/owner'),checkpoint_root=str(self.stage/'checkpoints')),
            limits=dict(requests=16,context=4096,max_new=512,parking_bytes=512*1024**2,save_bound_bytes=256*1024**2,
                planned_write_bytes=768*1024**2,disk_floor_bytes=27000000000,
                host_required_available_bytes=98990252032,coordinator_margin_bytes=1024**3),
            source_sha256={'worker.py':W.sha(self.source)})
        self.plan=dict(schema='packet200.bounded-serving-plan.v1',passed=True,device_executed=False,live_admission_ready=False,
            storage_admission_mode='monitored-forecast',storage_bound_proven=False,unit=W.UNIT,native_processes=1,
            activity_mode='launch',terminal_receipt=str(self.stage/'output/terminal/worker.json'),bind_host='127.0.0.1',bind_port=0,
            profile=self.profile,profile_sha256=W.digest(self.profile),native_cpu_affinity=[0,1,2,3,16,17,18,19],native_nice=0,
            helper_cpu_affinity=list(range(8,16))+list(range(24,32)),helper_nice=19,source_sha256={})

    def check_terminal(self,row,**kw):
        pre=copy.deepcopy(row)
        pre.update(passed=False,evidence_passed=False,writers_closed=False,coordination_completed=False,precompletion_written=False)
        return W.validate_terminal(row,plan_sha256='plan',unit_status=kw.get('unit_status',
            dict(ActiveState='inactive',Result='success',ExecMainStatus='0')),passive_drained=kw.get('passive_drained',True),
            precompletion=kw.get('precompletion',pre))

    def test_cpu_plan_hashes_sources_and_records_private_stage_without_creating_children(self):
        result=W.validate_cpu_plan(self.plan,self.stage)
        self.assertTrue(result['read_only']);self.assertFalse(result['operational_entrypoint_enabled'])
        self.assertEqual(list(self.stage.iterdir()),[])
        W.require_same_staging_identity(result['staging_identity'])

    def test_dangling_child_and_nonprivate_stage_refuse(self):
        (self.stage/'output').symlink_to(self.stage/'missing')
        with self.assertRaisesRegex(RuntimeError,'fresh'):W.validate_cpu_plan(self.plan,self.stage)
        (self.stage/'output').unlink();self.stage.chmod(0o755)
        with self.assertRaisesRegex(RuntimeError,'private0700'):W.validate_cpu_plan(self.plan,self.stage)

    def test_stage_replacement_and_source_drift_refuse(self):
        prior=W.staging_identity(self.stage);self.stage.rename(self.root/'retained-stage');self.stage.mkdir(mode=0o700)
        with self.assertRaisesRegex(RuntimeError,'identity changed'):W.require_same_staging_identity(prior)
        self.source.write_text('# changed\n')
        with self.assertRaisesRegex(RuntimeError,'source changed'):W.validate_cpu_plan(self.plan,self.stage)

    def test_forecast_is_not_promoted_to_proven_or_live_admission(self):
        for key in ('storage_bound_proven','live_admission_ready'):
            changed=copy.deepcopy(self.plan);changed[key]=True
            with self.assertRaises(RuntimeError):W.validate_cpu_plan(changed,self.stage)
        changed=copy.deepcopy(self.plan);changed['profile']['limits']['planned_write_bytes']=512*1024**2
        changed['profile_sha256']=W.digest(changed['profile'])
        with self.assertRaisesRegex(RuntimeError,'limits differ'):W.validate_cpu_plan(changed,self.stage)

    def test_zero_and_sixteen_turn_normal_closure_pass_lifecycle_only_contract(self):
        for count in (0,2,16):
            result=self.check_terminal(terminal(count));self.assertTrue(result['passed'])
            self.assertEqual(result['lifecycle_only'],count==0);self.assertFalse(result['restoration_performed'])

    def test_counts_pending_discard_and_signal_cannot_fake_normal_success(self):
        for change in ('count','controls','pending','discard','signal','early-limit'):
            row=terminal()
            if change=='count':row['requests']=17
            if change=='controls':row['controls']=1
            if change=='pending':row['stopped']['pending_request_id']='old'
            if change=='discard':row['stopped']['discarded_pending']=True
            if change=='signal':row['stopped']['reason']='signal'
            if change=='early-limit':row['stopped']['reason']='request-limit'
            with self.assertRaises(RuntimeError):self.check_terminal(row)

    def test_runtime_exit_does_not_override_evidence_or_resource_failure(self):
        for key in ('evidence_passed','store_closed','writers_closed','coordination_completed','owner_exited'):
            row=terminal();row[key]=False
            with self.assertRaises(RuntimeError):self.check_terminal(row)
        for key in ('retained','reader_retained','capture_retained','owned_read_fd_open','reader_startup_uncertain','incident'):
            row=terminal();row['diagnostics'][key]=True
            with self.assertRaises(RuntimeError):self.check_terminal(row)
        row=terminal();row['diagnostics']['eof']=False
        with self.assertRaises(RuntimeError):self.check_terminal(row)

    def test_worker_unit_and_separate_passive_drain_are_mandatory(self):
        with self.assertRaises(RuntimeError):self.check_terminal(terminal(),passive_drained=False)
        with self.assertRaises(RuntimeError):self.check_terminal(terminal(),unit_status=dict(ActiveState='active',Result='success',ExecMainStatus='0'))
        row=terminal();row['plan_sha256']='different'
        with self.assertRaisesRegex(RuntimeError,'plan identity'):self.check_terminal(row)

    def test_future_argv_is_description_only(self):
        command=W.future_worker_argv(self.plan,self.root/'review.json')
        self.assertEqual(command[3:5],['--authorized-device-window','--staging-parent'])
        self.assertIn(str(self.stage/'output'),command)
        self.assertFalse(W.OPERATIONAL_ENTRYPOINT_ENABLED)
        self.assertFalse(hasattr(W,'execute'))

    def test_future_argv_preserves_exact_activity_mode(self):
        for mode in ('launch','mapped-cold-start'):
            plan=copy.deepcopy(self.plan);plan['activity_mode']=mode
            command=W.future_worker_argv(plan,self.root/'review.json')
            self.assertEqual(command.count('--activity-mode'),1)
            self.assertEqual(command[command.index('--activity-mode')+1],mode)
        changed=copy.deepcopy(self.plan);changed['activity_mode']='implicit-ready-time'
        with self.assertRaisesRegex(RuntimeError,'unknown activity'):W.future_worker_argv(changed,self.root/'review.json')

    def test_two_phase_completion_requires_matching_prior_resource_proof(self):
        row=terminal()
        with self.assertRaisesRegex(RuntimeError,'pre-completion'):self.check_terminal(row,precompletion=None)
        pre=copy.deepcopy(row)
        pre.update(passed=False,evidence_passed=False,writers_closed=False,coordination_completed=False,precompletion_written=False)
        pre['plan_sha256']='other'
        with self.assertRaisesRegex(RuntimeError,'identity differs'):self.check_terminal(row,precompletion=pre)
        pre['plan_sha256']='plan';pre['coordination_completed']=True
        with self.assertRaisesRegex(RuntimeError,'phase ordering'):self.check_terminal(row,precompletion=pre)
        row['post_completion_evidence_failure']=True
        with self.assertRaises(RuntimeError):self.check_terminal(row)


if __name__=='__main__':unittest.main(verbosity=2)
