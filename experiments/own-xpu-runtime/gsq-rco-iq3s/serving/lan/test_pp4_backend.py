"""CPU-only depth-three PP4 request/reset/streaming tests; no GPU or native process."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

import pp4_backend as backend


class Stage:
    def __init__(self, index):
        self.spec = dict(id=index)
        self.sequence = 10 + index
        self.proc = mock.Mock()
        self.proc.poll.return_value = None
        self.command_pending = None
        self.transmit = b''
        self.received = b''
        self.pending_rows = []
        self.physical = self.committed = 0
        self.command = mock.Mock()


class RequestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        output = Path(self.tmp.name)
        (output / 'requests').mkdir()
        self.plan = dict(output=str(output), vocab=100, context=32, max_new=8,
                         evidence_floor_bytes=0, grace_seconds=10, speculative_depth=3,
                         request_sha256='a' * 64, suite_sha256='b' * 64,
                         model_identity_sha256='c' * 64, draft_model_sha256='d' * 64,
                         draft_experts='fp8', activation_dtype='F32', eos_token_ids=[99],
                         check_policy='measured', full_trace_required=False, ring_trace_limit=100000,
                         dump_each=False)
        self.engine = backend.Engine(self.plan, {}, {})
        self.engine.stages = [Stage(i) for i in range(4)]
        self.engine.guard = mock.Mock()
        self.engine.t = True
        self.resets = []
        self.drives = []

        def reset(stages, plan, guard, destination, **epoch):
            self.resets.append((destination, dict(epoch), tuple(stage.sequence for stage in stages)))
            for stage in stages:
                stage.sequence += 1
            return [dict(receipt=dict(allocation_inventory_after_sha256='e' * 64)) for _ in stages]

        def drive(stages, plan, guard, destination, *, epoch, stop_requested=None):
            self.drives.append((plan, epoch, tuple(stage.sequence for stage in stages)))
            outputs = [plan['prompt_tokens'][-1] + 1, 99]
            with (destination / 'tokens.jsonl').open('x') as stream:
                for index, token in enumerate(outputs):
                    stream.write(json.dumps(dict(index=index, token=token,
                                                 committed_monotonic_s=time.monotonic())) + '\n')
                    stream.flush()
                    time.sleep(0.002)
            position = len(plan['prompt_tokens']) + 1
            return dict(output_ids=outputs, input_position=position,
                        provider_pairs=position - 1, provider_serial=position - 1,
                        cancelled=False, cancelled_provider_incomplete=False,
                        issued_proposals=[dict(row=1)], rejected_proposals=[], events=[])

        self.reset = reset
        self.drive = drive

    def test_every_caller_request_resets_same_resident_stages_before_depth3_drive(self):
        with mock.patch.object(backend.rolling, 'reset', side_effect=self.reset), \
             mock.patch.object(backend.bridge, 'drive', side_effect=self.drive):
            streamed = []
            first, summary1 = self.engine.generate([3, 4], 2, 'client', on_token=streamed.append,
                                                   continue_ok=True)
            second, summary2 = self.engine.generate([8, 9, 10], 5, 'client')
        self.assertEqual(first, [5, 99])
        self.assertEqual(second, [11, 99])
        self.assertEqual(streamed, first)
        self.assertEqual(len(self.resets), 2)
        self.assertEqual([call[0]['prompt_tokens'] for call in self.drives], [[3, 4], [8, 9, 10]])
        self.assertEqual([call[0]['max_new'] for call in self.drives], [2, 5])
        self.assertEqual([call[0]['speculative_depth'] for call in self.drives], [3, 3])
        self.assertEqual([call[1] for call in self.drives], [1, 2])
        self.assertNotEqual(self.resets[0][1]['request'], self.resets[1][1]['request'])
        self.assertEqual(self.resets[1][1]['previous_request'], self.resets[0][1]['request'])
        self.assertEqual((summary1['continued_from'], summary2['continued_from']), (0, 0))
        self.assertEqual(summary1['mode'], 'live-mtp-depth3')
        for number in (1, 2):
            record = json.loads((Path(self.tmp.name) / 'requests' / f'request-{number:06d}' / 'result.json').read_text())
            self.assertFalse(record['prompt_state_reused'])
            self.assertNotIn('expected_output_ids', record)
            self.assertGreater(record['initial_sequences'][0], record['previous_sequences'][0])

    def test_invalid_caller_bounds_never_reset_or_drive(self):
        with mock.patch.object(backend.rolling, 'reset', side_effect=self.reset) as reset, \
             mock.patch.object(backend.bridge, 'drive', side_effect=self.drive) as drive:
            with self.assertRaisesRegex(ValueError, 'max_new'):
                self.engine.generate([1, 2], 9, 'client')
            with self.assertRaisesRegex(ValueError, 'prompt token bounds'):
                self.engine.generate([], 1, 'client')
        reset.assert_not_called()
        drive.assert_not_called()
        self.assertEqual(self.engine.count, 0)

    def test_callback_error_propagates_and_does_not_write_success(self):
        def fail(_token):
            raise RuntimeError('stream consumer failed')
        with mock.patch.object(backend.rolling, 'reset', side_effect=self.reset), \
             mock.patch.object(backend.bridge, 'drive', side_effect=self.drive):
            with self.assertRaisesRegex(RuntimeError, 'stream consumer failed'):
                self.engine.generate([3], 2, 'client', on_token=fail)
        self.assertFalse((Path(self.tmp.name) / 'requests/request-000001/result.json').exists())

    def test_qualification_dump_flag_executes_after_committed_result(self):
        self.engine.plan['dump_each'] = True
        for stage in self.engine.stages:
            stage.command.side_effect = lambda *args, _stage=stage, **kwargs: setattr(_stage, 'sequence', _stage.sequence + 1)
        with mock.patch.object(backend.rolling, 'reset', side_effect=self.reset), \
             mock.patch.object(backend.bridge, 'drive', side_effect=self.drive):
            self.engine.generate([3], 2, 'client')
        for stage in self.engine.stages:
            stage.command.assert_called_once_with(4, position=2000000000)
        record = json.loads((Path(self.tmp.name) / 'requests/request-000001/result.json').read_text())
        self.assertEqual(len(record['dump_sequences']), 4)
        self.assertGreater(record['post_dump_sequences'][0], record['final_sequences'][0])

    def prepare_close(self):
        self.engine.guard.failed = None
        self.engine.guard.tracked_processes = []
        self.engine.guard.thread.is_alive.return_value = False

        def fail(reason):
            self.engine.guard.failed = str(reason)

        self.engine.guard.fail.side_effect = fail

    def test_clean_close_reaches_native_finish_and_terminal(self):
        self.prepare_close()
        result = self.engine.close(True)
        self.assertTrue(result['passed'])
        for stage in self.engine.stages:
            stage.command.assert_called_once_with(5)
        self.engine.guard.fail.assert_not_called()
        self.assertTrue((Path(self.tmp.name) / 'terminal.json').exists())

    def test_error_close_preserves_original_fault_cause(self):
        self.prepare_close()
        result = self.engine.close(False, reason='original native failure')
        self.engine.guard.fail.assert_called_once_with('original native failure')
        self.assertEqual(result['error'], 'original native failure')
        self.assertFalse(result['passed'])
        for stage in self.engine.stages:
            stage.command.assert_not_called()


class PlanTests(unittest.TestCase):
    def test_pp4_enables_per_stage_native_prefill_maps(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/'config.json'
            config.write_text(json.dumps(dict(pp4_http_service=True,bdfs=list(backend.BDFS),
                boundaries=backend.BOUNDARIES,context=backend.CONTEXT,vocab=backend.VOCAB,
                eos_token_ids=backend.EOS,speculative_depth=3,capture_ready_overlap=True)))
            plan=dict(stages=[dict(id=i,argv=[]) for i in range(4)],output=str(Path(tmp)/'run'),
                speculative_depth=3,capture_ready_overlap=True,use_proposals=True,pins={},
                check_policy='measured',coordinator_trace_limit=10000)
            with mock.patch.dict(os.environ,{'SC117_CONTEXT':str(backend.CONTEXT)}), \
                 mock.patch.object(backend.rolling_driver,'make_plan',return_value=plan):
                result=backend.make_plan(config)
            self.assertEqual(result['prefill_rows'],256)
            self.assertEqual(result['prefill_stream_bytes'],backend.base.PREFILL_STREAM_BYTES)
            for stage in result['stages']:
                self.assertEqual(backend.base.option(stage['argv'],'--prefill-rows'),'256')
                self.assertEqual(backend.base.option(stage['argv'],'--prefill-shared'),
                    str(Path(result['output'])/f"stage{stage['id']}"/'prefill.bin'))

if __name__ == '__main__':
    unittest.main()
