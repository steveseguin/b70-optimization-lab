"""CPU-only ownership and launch-isolation checks for the persistent FP8 server."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, MagicMock

SOURCE = Path(__file__).resolve().parents[1] / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
spec = importlib.util.spec_from_file_location('fp8_serve', SOURCE)
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)


class ServingTests(unittest.TestCase):
    def record(self):
        return {'container_id': 'a' * 64, 'container_name': 'neural-fp8-example', 'image_id': serve.IMAGE_ID}

    def container(self):
        return {'Id': 'a' * 64, 'Name': '/neural-fp8-example', 'Image': serve.IMAGE_ID,
                'State': {'Running': True}}

    def test_launch_is_pinned_and_ignores_the_caller_environment(self):
        with patch.dict(os.environ, {'IMAGE': 'bad', 'EXTRA_SERVE_ARGS': '--enable-prefix-caching',
                                    'VLLM_USE_V2_MODEL_RUNNER': '1', 'VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST': '/bad',
                                    'DOCKER_HOST': 'tcp://unrelated-host:1234', 'BASH_ENV': '/bad'}):
            argv = serve.docker_argv('recommended', Path('/model'), Path('/state'), 18124, 'owned')
            env = serve.clean_env()
        self.assertEqual(env['DOCKER_HOST'], 'unix:///var/run/docker.sock')
        self.assertNotIn('BASH_ENV', env)
        self.assertIn(serve.IMAGE, argv)
        self.assertNotIn('bad', argv)
        self.assertNotIn('--enable-prefix-caching', argv)
        self.assertIn('--no-enable-prefix-caching', argv)
        container_env = dict(argv[i + 1].split('=', 1) for i in range(len(argv)) if argv[i] == '--env')
        self.assertEqual(container_env['VLLM_USE_V2_MODEL_RUNNER'], '0')
        self.assertEqual(container_env['VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST'], serve.SHORTLIST)
        self.assertEqual(container_env['ZE_AFFINITY_MASK'], '0,1')
        for flag, value in (('--tensor-parallel-size', '2'), ('--max-model-len', '33024'), ('--max-num-seqs', '1'),
                            ('--max-num-batched-tokens', '4096'), ('--gpu-memory-utilization', '0.95')):
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertIn('"num_speculative_tokens": 5', argv[argv.index('--speculative-config') + 1])
        depth1 = serve.docker_argv('depth-1', Path('/model'), Path('/state'), 18124, 'owned')
        self.assertIn('"num_speculative_tokens": 1', depth1[depth1.index('--speculative-config') + 1])
        self.assertNotIn('VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST', dict(a.split('=', 1) for a in depth1 if '=' in a and a.startswith('VLLM')))

    def test_pinned_image_accepted_under_both_docker_image_stores(self):
        registry = {'Id': serve.IMAGE_ID, 'RepoDigests': [serve.IMAGE]}
        classic = {'Id': 'sha256:' + 'c' * 64, 'RepoDigests': [serve.IMAGE]}
        other = {'Id': 'sha256:' + 'd' * 64, 'RepoDigests': ['ghcr.io/x/y@sha256:' + 'e' * 64]}
        for image, expected in ((registry, serve.IMAGE_ID), (classic, classic['Id'])):
            with patch.object(serve, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps([image]), '')):
                self.assertEqual(serve.local_image_id(), expected)
        with patch.object(serve, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps([other]), '')):
            with self.assertRaisesRegex(RuntimeError, 'not the pinned runtime'):
                serve.local_image_id()
        with patch.object(serve, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'No such image')):
            with self.assertRaisesRegex(RuntimeError, 'Pull the pinned runtime'):
                serve.local_image_id()

    def test_replacement_id_name_and_image_are_rejected(self):
        for key in ('Id', 'Name', 'Image'):
            candidate = self.container()
            candidate[key] = 'unrelated'
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'ownership'):
                serve.owned(self.record(), candidate)

    def test_stop_never_stops_same_named_replacement(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(serve, 'inspect_container') as inspect, patch.object(serve, 'run') as run:
            wrong = self.container()
            wrong['Id'] = 'b' * 64
            inspect.return_value = wrong
            with self.assertRaises(RuntimeError):
                serve.stop_owned(Path(directory), self.record())
            run.assert_not_called()
            self.assertFalse((Path(directory) / 'stop-request.json').exists())

    def test_stop_once_by_exact_id(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(serve, 'inspect_container', return_value=self.container()), patch.object(serve, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, 'stopped\n', '')
            for _ in range(2):
                serve.stop_owned(Path(directory), self.record())
            run.assert_called_once_with(['docker', 'stop', '--time', '30', 'a' * 64], check=False, timeout=45)

    def test_failed_stop_is_retained_without_retry(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(serve, 'inspect_container', return_value=self.container()), patch.object(serve, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 1, '', 'stop failed')
            with self.assertRaisesRegex(RuntimeError, 'No retry'):
                serve.stop_owned(Path(directory), self.record())
            serve.stop_owned(Path(directory), self.record())
            self.assertEqual(run.call_count, 1)
            self.assertIn('stop failed', (Path(directory) / 'stop.log').read_text())

    def test_absent_owned_container_requires_no_mutation(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(serve, 'inspect_container', return_value=None), patch.object(serve, 'run') as run:
            serve.stop_owned(Path(directory), self.record())
            run.assert_not_called()
            self.assertTrue(json.loads((Path(directory) / 'stop-request.json').read_text())['already_absent'])

    def test_gpu_owner_blocks_launch(self):
        with patch.object(serve.socket, 'socket'), patch.object(serve, 'inspect_container', return_value=None), patch.object(serve.Path, 'glob', return_value=[Path('/dev/dri/renderD128'), Path('/dev/dri/renderD129')]), patch.object(serve, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, '12345', '')
            with self.assertRaisesRegex(RuntimeError, 'render device is in use'):
                serve.check_available(18124, 'owned')
            self.assertEqual(run.call_count, 1)

    def test_container_with_gpu_access_blocks_before_device_open(self):
        with patch.object(serve.socket, 'socket'), patch.object(serve, 'inspect_container', return_value=None), patch.object(serve.Path, 'glob', return_value=[Path('/dev/dri/renderD128'), Path('/dev/dri/renderD129')]), patch.object(serve, 'run') as run:
            run.side_effect = [subprocess.CompletedProcess([], 1, '', ''),
                               subprocess.CompletedProcess([], 0, 'other', ''),
                               subprocess.CompletedProcess([], 0, json.dumps([{'HostConfig': {'Devices': [{'PathOnHost': '/dev/dri'}]}}]), '')]
            with self.assertRaisesRegex(RuntimeError, 'Another running container'):
                serve.check_available(18124, 'owned')

    def test_permission_failure_blocks_fault_monitor(self):
        with patch.object(serve, 'run', return_value=subprocess.CompletedProcess([], 0, '', 'not seeing messages from other users')):
            with self.assertRaisesRegex(RuntimeError, 'kernel journal'):
                serve.journal('2026-09-14T00:00:00+00:00')

    def test_gpu_fault_detection(self):
        self.assertIsNotNone(serve.FAULT.search('xe 0000:03:00.0: GPU reset'))
        self.assertIsNone(serve.FAULT.search('xe 0000:03:00.0: Finished initialization'))

    def test_status_rechecks_api_despite_saved_ready_state(self):
        record = dict(self.record(), status='ready', port=18124)
        with patch.object(serve, 'inspect_container', return_value=self.container()), patch.object(serve, 'healthy', return_value=False) as health:
            current = serve.status(Path('/state'), record)
            self.assertEqual(current['status'], 'ready')
            self.assertTrue(current['container_running'])
            self.assertFalse(current['api_healthy'])
            health.assert_called_once_with(18124)

    def test_status_does_not_probe_endpoint_for_absent_owned_container(self):
        record = dict(self.record(), status='ready', port=18124)
        with patch.object(serve, 'inspect_container', return_value=None), patch.object(serve, 'healthy') as health:
            current = serve.status(Path('/state'), record)
            self.assertFalse(current['api_healthy'])
            health.assert_not_called()

    def test_health_request_is_bounded(self):
        with patch.object(serve.urllib.request, 'urlopen') as request:
            request.return_value.__enter__.return_value.status = 200
            self.assertTrue(serve.healthy(18124))
            request.assert_called_once_with('http://127.0.0.1:18124/health', timeout=2)

    def test_new_fault_stops_once_and_leaves_durable_failed_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'model').mkdir()
            args = SimpleNamespace(model_dir=root / 'model', state_dir=root / 'state', port=18124, startup_timeout=1800, profile='recommended')
            child = MagicMock()
            with patch('builtins.open', unittest.mock.mock_open()), patch.object(serve.fcntl, 'flock'), patch.object(serve, 'check_available'), patch.object(serve, 'local_image_id', return_value=serve.IMAGE_ID), patch.object(serve.shutil, 'copytree'), patch.object(serve, 'inspect_container', return_value=None), patch.object(serve, 'journal', side_effect=['', 'xe 0000:03:00.0: GPU reset']), patch.object(serve, 'capture_owned') as capture, patch.object(serve, 'stop_owned') as stop, patch.object(serve.subprocess, 'Popen', return_value=child) as launch:
                def remember(state, record):
                    record['container_id'] = 'a' * 64
                capture.side_effect = remember
                with self.assertRaisesRegex(RuntimeError, 'New GPU fault'):
                    serve.start(args)
                launch.assert_called_once()
                stop.assert_called_once()
            record = json.loads((root / 'state/state.json').read_text())
            self.assertEqual(record['status'], 'failed')
            self.assertIn('GPU fault', record['error'])
            self.assertTrue((root / 'state/kernel.log').exists())

    def test_child_failure_is_not_restarted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'model').mkdir()
            args = SimpleNamespace(model_dir=root / 'model', state_dir=root / 'state', port=18124, startup_timeout=1800, profile='recommended')
            child = MagicMock(returncode=7)
            child.poll.return_value = 7
            with patch('builtins.open', unittest.mock.mock_open()), patch.object(serve.fcntl, 'flock'), patch.object(serve, 'check_available'), patch.object(serve, 'local_image_id', return_value=serve.IMAGE_ID), patch.object(serve.shutil, 'copytree'), patch.object(serve, 'journal', return_value=''), patch.object(serve, 'capture_owned'), patch.object(serve.subprocess, 'Popen', return_value=child) as launch:
                with self.assertRaisesRegex(RuntimeError, 'exited'):
                    serve.start(args)
                launch.assert_called_once()
            self.assertEqual(json.loads((root / 'state/state.json').read_text())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
