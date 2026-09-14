#!/usr/bin/env python3
"""Synthetic stdlib tests only; no endpoint, profiler, Torch or native request."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch, Mock

sys.dont_write_bytecode = True
SOURCE = Path(__file__).with_name('record-retained-multiblock-profile.py')
spec = importlib.util.spec_from_file_location('profile_client_tested', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def parity():
    return {'status': 'passed', 'comparisons': {key: {'bitwise_equal': True}
            for key in ('images', 'video_latent', 'audio_latent', 'waveform')}}


def trace():
    return {'$schema': 'https://www.speedscope.app/file-format-schema.json',
        'shared': {'frames': [{'name': 'prompt_worker', 'file': '/source/main.py'},
                             {'name': '_call_native', 'file': '/source/ltx_multiblock_compile.py'}]},
        'profiles': [{'name': 'Thread1', 'type': 'sampled', 'unit': 'seconds', 'startValue': 0,
                      'endValue': 1, 'samples': [[0, 1]], 'weights': [1.0]}]}


class Tests(unittest.TestCase):
    def test_closed_schedule(self):
        rows = m.schedule('retained-profile-01')
        self.assertEqual([x['mode'] for x in rows], ['compiled', 'restored'])
        self.assertTrue(all(x['qualified_before'] == 2 and x['selection'] == 'all48' and
                            not x['initialization'] and x['fixture'] == 'boat' for x in rows))
        for name in ('', '../escape', 'A', '-leading', 'x' * 65):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                m.schedule(name)

    def test_strict_four_output_parity(self):
        self.assertTrue(m.passed_parity(parity()))
        for key in parity()['comparisons']:
            value = parity()
            value['comparisons'][key]['bitwise_equal'] = 1
            self.assertFalse(m.passed_parity(value))
        value = parity()
        value['comparisons'].pop('waveform')
        self.assertFalse(m.passed_parity(value))
        value = parity()
        value['status'] = 'passed-offline-evidence'
        self.assertFalse(m.passed_parity(value))

    def test_exact_profiler_command(self):
        cmd = m.profiler_command(12345, Path('/tmp/diagnostic'))
        self.assertEqual(cmd.count('record'), 1)
        self.assertEqual(cmd[cmd.index('--duration') + 1], '15')
        self.assertEqual(cmd[cmd.index('--rate') + 1], '100')
        self.assertTrue({'--threads', '--idle', '--nonblocking', '--full-filenames'} <= set(cmd))
        self.assertNotIn(str(m.CREDENTIAL), cmd)
        for pid in (True, 1, '12345'):
            with self.assertRaises(RuntimeError):
                m.profiler_command(pid, Path('/tmp/diagnostic'))

    def test_trace_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'trace.json'
            path.write_text(json.dumps(trace()))
            result = m.profile_summary(path)
            self.assertEqual(result['threads'][0]['sample_count'], 1)
            self.assertTrue(result['threads'][0]['contains_selected_block_call'])
            self.assertIn('never sum', result['time_semantics'])
            for alter in (lambda x: x.update({'$schema': 'wrong'}),
                          lambda x: x['profiles'][0].update(weights=[float('nan')]),
                          lambda x: x['profiles'][0].update(samples=[[0, 20]]),
                          lambda x: x['profiles'][0].update(samples=[[0]]),
                          lambda x: x['profiles'][0].update(samples=[[1]]),
                          lambda x: x['profiles'][0].update(endValue=0)):
                value = trace()
                alter(value)
                path.write_text(json.dumps(value))
                with self.subTest(value=value), self.assertRaises(RuntimeError):
                    m.profile_summary(path)
            linked = Path(temp) / 'linked'
            linked.symlink_to(path)
            with self.assertRaises(RuntimeError):
                m.profile_summary(linked)

    def test_attachment_failure_has_no_request(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            (out / 'profiler.log').write_text('permission refused')
            worker = NS(pid=123, poll=lambda: 1)
            with self.assertRaises(RuntimeError):
                m.confirm_attachment(worker, {}, out)
            self.assertTrue((out / 'profiler-attachment-failure.json').is_file())

    def test_cli_modes_do_not_need_terminal(self):
        with self.assertRaises(SystemExit) as caught:
            m.parse_args(['--help'])
        self.assertEqual(caught.exception.code, 0)
        args = m.parse_args(['--campaign', 'retained-profile-01', '--packet', '/p',
                             '--manifest-sha256', m.PACKET_SHA, '--server-run', '/s', '--check-only'])
        self.assertTrue(args.check_only)
        self.assertFalse(args.ready_check)

    def test_terminal_process_and_status_gates(self):
        sealed = m.load_client()  # Frozen stdlib helper imports only.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / m.QUALIFICATION
            directory.mkdir()
            identity = {'pid': 123, 'start_ticks': 456}
            plans = sealed.schedule(m.QUALIFICATION)
            prereg = {'campaign': m.QUALIFICATION, 'client_sha256': m.CLIENT_SHA,
                'receipt_validator_sha256': m.HELPER_SHA, 'packet_manifest_sha256': m.PACKET_SHA,
                'identity': identity, 'schedule': plans}
            rows = [{**plan, 'status': 'passed'} for plan in plans]
            progress = {'status': 'passed', 'completed_requests': 12, 'rows': rows}
            (directory / 'preregistration.json').write_text(json.dumps(prereg))
            args = NS(server_run=root / 'server')
            with patch.object(m, 'ROOT', root):
                for changed in ({**progress, 'status': 'running'},
                                {**progress, 'completed_requests': 11},
                                {**progress, 'rows': rows[:-1]}):
                    (directory / 'progress.json').write_text(json.dumps(changed))
                    with self.assertRaises(RuntimeError):
                        m.terminal_binding(sealed, args, identity)
                (directory / 'progress.json').write_text(json.dumps(progress))
                with self.assertRaises(RuntimeError):
                    m.terminal_binding(sealed, args, {'pid': 123, 'start_ticks': 457})

    def test_diagnostic_success_and_failure_order(self):
        for failing in ('none', 'attach', 'compiled', 'profiler', 'profile-schema', 'restored'):
            with self.subTest(failing=failing), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                server = root / 'server'
                server.mkdir()
                args = NS(campaign='test-profile', server_run=server, packet=root / 'packet',
                          manifest_sha256=m.PACKET_SHA)
                events = []
                worker = Mock(pid=123)
                worker.poll.return_value = 0
                # First poll after attachment must be live; later polls are finished.
                worker.poll.side_effect = [None, 0, 0, 0, 0]
                worker.wait.return_value = 1 if failing == 'profiler' else 0
                safe = lambda base, relative, **kw: Path(base) / relative
                retention = NS(safe_path=safe, delete_owned=lambda *a, **k: events.append('delete'))
                client = NS(retention=retention, identity_binding=lambda *a: ({'pid': 88}, {}))
                binding = {'owners': {}, 'components': {}, 'graphs': {}}
                def attach(*args):
                    events.append('attach')
                    if failing == 'attach':
                        raise RuntimeError('attach failed')
                def request(client, common, args, identity, binding, base, planned, output, **kw):
                    events.append(planned['mode'])
                    if failing == planned['mode']:
                        raise RuntimeError('request/quality failed')
                    return {**planned, 'request_launch_before': {}, 'request_complete_observed': {},
                            'profiler_exit_at_request_completion': 0, 'output_inventory': [{}]}
                def profile(*args):
                    events.append('profile-schema')
                    if failing == 'profile-schema':
                        raise RuntimeError('profile failed')
                    return {}
                def start(*args):
                    events.append('start')
                    return worker, {}
                with patch.object(m, 'ROOT', root), patch.object(m, 'terminal_binding', return_value=binding), \
                     patch.object(m, 'start_profiler', side_effect=start), \
                     patch.object(m, 'confirm_attachment', side_effect=attach), \
                     patch.object(m, 'run_one', side_effect=request), \
                     patch.object(m, 'profile_summary', side_effect=profile), patch.object(m, 'sha', return_value='a'*64):
                    if failing == 'none':
                        m.run_diagnostic(client, None, args, {})
                        self.assertEqual(events, ['start', 'attach', 'compiled', 'profile-schema', 'restored', 'delete', 'delete'])
                    else:
                        with self.assertRaises(RuntimeError):
                            m.run_diagnostic(client, None, args, {})
                        self.assertTrue((root / args.campaign / 'failure.json').is_file())
                        self.assertNotIn('delete', events)
                        if failing != 'restored':
                            self.assertNotIn('restored', events)
                self.assertLessEqual(events.count('start'), 1)
                self.assertLessEqual(events.count('compiled'), 1)
                self.assertLessEqual(events.count('restored'), 1)
                worker.terminate.assert_not_called()
                worker.kill.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
