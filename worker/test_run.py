"""CPU-only regression checks for acceptance binding to the exported workspace."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


SPEC=importlib.util.spec_from_file_location('worker_run',Path(__file__).with_name('run.py'))
RUN=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)


class Submitted(Exception):
    pass


class FakeSandbox:
    def __init__(self,root,validation_effect=None,returncode=0):
        self.run_dir=root;self.stopped=False;self.validation_effect=validation_effect
        self.returncode=returncode;self.calls=[]
    def execute(self,action):
        self.calls.append(action['command'])
        if action['command']==RUN.FINISH:raise Submitted()
        if self.validation_effect:self.validation_effect()
        return {'returncode':self.returncode,'output':'acceptance output'}


class AcceptanceTreeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.workspace=self.root/'workspace';self.workspace.mkdir()
        (self.workspace/'answer.py').write_text('answer = 42\n')

    def environment(self,**kwargs):
        sandbox=FakeSandbox(self.root,**kwargs)
        return sandbox,RUN.CheckedEnvironment(sandbox,'python3 /acceptance/check.py',self.root,3)

    def test_stable_passing_tree_submits_and_matches_after_stop(self):
        sandbox,env=self.environment()
        with self.assertRaises(Submitted):env.execute({'command':RUN.FINISH})
        self.assertTrue(env.validations[-1]['accepted'])
        self.assertEqual(env.passing_tree_sha256,RUN.workspace_tree_sha256(self.workspace))
        sandbox.stopped=True
        self.assertTrue(env.verify_final_tree())

    def test_change_after_pass_rejects_final_workspace(self):
        sandbox,env=self.environment()
        with self.assertRaises(Submitted):env.execute({'command':RUN.FINISH})
        (self.workspace/'answer.py').write_text('answer = "wrong after validation"\n')
        sandbox.stopped=True
        with self.assertRaisesRegex(RuntimeError,'does not match'):env.verify_final_tree()
        self.assertNotEqual(env.passing_tree_sha256,env.final_tree_sha256)

    def test_build_output_requires_second_stable_passing_check(self):
        sandbox,env=self.environment(validation_effect=lambda:(self.workspace/'build.txt').write_text('built\n'))
        feedback=env.execute({'command':RUN.FINISH})
        self.assertEqual(feedback['returncode'],1)
        self.assertIn('stabilized tree',feedback['output'])
        self.assertIsNone(env.passing_tree_sha256)
        self.assertFalse(env.validations[-1]['accepted'])
        self.assertNotIn(RUN.FINISH,sandbox.calls)
        with self.assertRaises(Submitted):env.execute({'command':RUN.FINISH})
        self.assertTrue(env.validations[-1]['accepted'])
        sandbox.stopped=True
        self.assertTrue(env.verify_final_tree())

    def test_failed_check_has_no_accepted_tree(self):
        sandbox,env=self.environment(returncode=1)
        feedback=env.execute({'command':RUN.FINISH})
        self.assertIn('checks failed',feedback['output'])
        self.assertIsNone(env.passing_tree_sha256)
        self.assertNotIn(RUN.FINISH,sandbox.calls)

    def test_followup_action_invalidates_prior_acceptance(self):
        _,env=self.environment()
        with self.assertRaises(Submitted):env.execute({'command':RUN.FINISH})
        env.execute({'command':'echo another action'})
        self.assertIsNone(env.passing_tree_sha256)

    def test_final_tree_check_requires_stopped_sandbox(self):
        _,env=self.environment()
        with self.assertRaises(Submitted):env.execute({'command':RUN.FINISH})
        with self.assertRaisesRegex(RuntimeError,'Stop the CPU'):env.verify_final_tree()

    def test_final_symlink_is_rejected_without_following(self):
        sandbox,env=self.environment()
        with self.assertRaises(Submitted):env.execute({'command':RUN.FINISH})
        (self.workspace/'secret').symlink_to('/etc/passwd');sandbox.stopped=True
        with self.assertRaises(RuntimeError):env.verify_final_tree()


if __name__=='__main__':unittest.main()

class BaselineTests(unittest.TestCase):
    def test_environment_failure_cannot_substitute_for_issue_failure(self):
        task={'expected_baseline_failure':True,'expected_baseline_error':'expected bug'}
        with self.assertRaisesRegex(RuntimeError,'unexpected reason'):
            RUN.validate_baseline(task,{'returncode':1,'output':'TimeoutExpired'})
        RUN.validate_baseline(task,{'returncode':1,'output':'AssertionError: expected bug'})
        with self.assertRaisesRegex(RuntimeError,'already passes'):
            RUN.validate_baseline(task,{'returncode':0,'output':''})
