"""Interception/fixture checks only: never execute the HOST_ONLY owner."""
import io
import unittest
from unittest.mock import patch

import session_lifecycle_host_probe as P


class PreparedHostProbe(unittest.TestCase):
    def test_actual_plan_preserves_pinned_eight_request_native_argv(self):
        spec = P.plan()
        self.assertEqual(spec['argv'], P.B.plan(P.OUTPUT)['argv'])
        self.assertEqual(spec['soft_request_limit'], 2)
        self.assertEqual(spec['native_request_limit'], 8)
        self.assertEqual(spec['expected_stop_reason'], 'quit')
        self.assertEqual(len(spec['base']['synthetic_identity_text'].splitlines()), 3)
        self.assertEqual(spec['base']['expected_identity']['geometry']['context'], 64)
        self.assertEqual(spec['native_stop_token_ids'],
                         [spec['base']['expected_identity']['geometry']['eos']])

    def test_actual_production_launch_is_intercepted_before_exec(self):
        spec = P.plan()
        _, parent = P.B.modules()
        environment = parent.parent_environment()
        calls = []
        class Intercept(Exception):
            pass
        def stop(argv, **kwargs):
            calls.append((argv, kwargs))
            raise Intercept()
        with self.assertRaises(Intercept):
            P.start_owner(spec, environment, io.BytesIO(), popen=stop)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], spec['argv'])
        self.assertEqual(calls[0][1]['env'], environment)
        self.assertEqual(calls[0][1]['stdin'], P.subprocess.PIPE)
        self.assertEqual(calls[0][1]['stdout'], P.subprocess.PIPE)

    def test_wrong_native_limit_refuses_without_exec(self):
        spec = P.plan()
        spec['native_request_limit'] = 2
        with patch.object(P.subprocess, 'Popen', side_effect=AssertionError('no launch')) as launch:
            with self.assertRaisesRegex(RuntimeError, 'unchanged pinned'):
                P.start_owner(spec, {}, io.BytesIO(), popen=launch)
            launch.assert_not_called()

    def test_synthetic_codec_exact_round_trip_and_two_prompt_vectors(self):
        spec = P.plan()
        codec = P.SyntheticCodec(spec['base']['expected_identity'])
        self.assertEqual(codec.encode(codec.decode(list(range(16)))), list(range(16)))
        for row in spec['requests']:
            messages = [dict(role='user', content=row['content'])]
            self.assertEqual(codec.encode(codec.render(messages)), row['tokens'])
        with self.assertRaises(RuntimeError):
            codec.encode('real text is not this synthetic alphabet')

    def test_plan_refuses_occupied_path_without_execution(self):
        with patch.object(P.os.path, 'lexists', return_value=True):
            with self.assertRaisesRegex(RuntimeError, 'fixed fresh'):
                P.plan()


if __name__ == '__main__':
    unittest.main(verbosity=2)
