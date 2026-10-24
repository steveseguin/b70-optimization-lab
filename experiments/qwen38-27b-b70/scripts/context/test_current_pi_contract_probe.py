"""C66 CPU proofs, including the unchanged C64 lifecycle/refusal suite."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import current_pi_contract_probe as p
import history_contract_keeper as launcher
import test_current_pi_probe as baseline_tests


class ContractLifecycleTests(baseline_tests.PiProbeTests):
    """Run all existing refusal, cleanup, receipt and finalization tests as C66."""
    def setUp(self):
        self.config = p.configured()
        self.config.__enter__()
        super().setUp()

    def tearDown(self):
        try:
            super().tearDown()
        finally:
            self.config.__exit__(None, None, None)


class ContractWrapperTests(unittest.TestCase):
    def test_paths_change_while_task_image_caps_and_names_stay(self):
        preserved = {name: getattr(p.base, name) for name in (
            'TASK', 'JOB', 'CONTAINER', 'IMAGE_ID', 'IMAGE_TAG', 'MIN_AVAILABLE_MIB',
            'PROXY_UNIT', 'SERVER_UNIT', 'PROXY_URL', 'MODEL', 'RUNNER', 'HISTORY')}
        original_control = p.base.CONTROL
        with p.configured():
            self.assertEqual(p.base.CONTROL, p.CONTROL)
            self.assertEqual(p.base.RUNS, p.RUNS)
            self.assertEqual(p.base.STATE, p.STATE)
            self.assertEqual(p.base.TRIAL, p.RUNS / 'jobs' / p.base.JOB / 'trial')
            self.assertEqual({name: getattr(p.base, name) for name in preserved}, preserved)
            self.assertEqual(p.base.MIN_AVAILABLE_MIB, 2706)
        self.assertEqual(p.base.CONTROL, original_control)

    def test_proxy_argv_diff_is_only_launcher_and_state_path(self):
        before = p.BASE_PROXY_COMMAND('http://127.0.0.1:18196/v1')
        with p.configured():
            after = p.base.proxy_command('http://127.0.0.1:18196/v1')
        self.assertEqual(len(before), len(after))
        changes = [(a, b) for a, b in zip(before, after) if a != b]
        self.assertEqual(changes, [(str(p.base.LAB / 'tools/ctxkeeper/ctxkeeper.py'), str(p.LAUNCHER)),
                                   (str(p.base.STATE), str(p.STATE))])
        self.assertEqual(after[after.index('--notes-thinking') + 1], 'on')
        self.assertEqual(after[after.index('--upstream-retries') + 1], '0')

    def test_extra_pins_include_all_source_dependencies(self):
        baseline = p.BASE_INPUT_PINS()
        with p.configured():
            pins = p.base.input_pins()
        self.assertEqual(pins['task'], baseline['task'])
        self.assertTrue(set(baseline['scripts']) <= set(pins['scripts']))
        for path in (Path(p.__file__).resolve(), p.LAUNCHER, p.CONTRACT_SOURCE,
                     Path(p.base.__file__).resolve()):
            self.assertEqual(pins['scripts'][str(path)], p.base.sha(path))
        self.assertEqual(len(pins['scripts']) - len(baseline['scripts']), 3)

    def test_changed_launcher_pin_is_rejected_before_client_or_finalize(self):
        with tempfile.TemporaryDirectory(prefix='c66-pin-test-') as temp:
            receipt_path = Path(temp) / 'pins.json'
            with p.configured():
                pins = p.base.input_pins()
                pins['scripts'][str(p.LAUNCHER)] = 'wrong'
                p.base.dump(receipt_path, {'preflight_ok': True, 'image_id': p.base.IMAGE_ID, 'pins': pins})
                with self.assertRaisesRegex(RuntimeError, 'pinned task or client source changed'):
                    p.base.verify_pins(receipt_path)

    def test_suffix_once_and_shared_main_notes_header(self):
        original = launcher.ck.MEMORY_NOTE
        with patch.object(launcher.ck, 'MEMORY_NOTE', original):
            launcher.install_contract()
            launcher.install_contract()
            self.assertEqual(launcher.ck.MEMORY_NOTE, original + launcher.proposal.CONTRACT)
            messages = [{'role': 'system', 'content': 'Original task policy'}, {'role': 'user', 'content': 'Continue work'}]
            main = launcher.ck.with_memory_note(copy.deepcopy(messages))
            self.assertEqual(main[0]['content'].count(launcher.proposal.CONTRACT), 1)
            self.assertEqual(launcher.ck.with_memory_note(main), main)
            with tempfile.TemporaryDirectory(prefix='c66-header-test-') as temp:
                root = Path(temp)
                keeper = launcher.proposal.new_keeper(lambda _: {}, root)
                session = launcher.ck.Session(root, 'test')
                session.state.update(cut=1, notes='RULES\n(none)\nSTATE\nitem: known\nOPEN\n')
                notes, _ = keeper.inplace_request(session, main, 2,
                    [{'role': 'assistant', 'content': 'Observed work'}], {'tools': []})
                self.assertEqual(notes[0], main[0])
                self.assertEqual(keeper.budget, 32768)
                self.assertEqual(keeper.inplace_tokens, 15000)
                self.assertTrue(keeper.notes_thinking)
        self.assertEqual(launcher.ck.MEMORY_NOTE, original)

    def test_launcher_delegates_to_unchanged_production_main(self):
        original = launcher.ck.MEMORY_NOTE
        with patch.object(launcher.ck, 'MEMORY_NOTE', original), patch.object(launcher.ck, 'main') as main:
            launcher.main()
            main.assert_called_once_with()
            self.assertEqual(launcher.ck.MEMORY_NOTE, original + launcher.proposal.CONTRACT)

    def test_configuration_restored_on_failure(self):
        old = p.base.proxy_command
        with self.assertRaisesRegex(RuntimeError, 'failure'):
            with p.configured():
                raise RuntimeError('failure')
        self.assertIs(p.base.proxy_command, old)
        self.assertFalse(p._CONFIGURED)


if __name__ == '__main__':
    unittest.main()
