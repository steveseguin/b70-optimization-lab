#!/usr/bin/env python3
"""CPU-only controller checks. All runtime/HTTP/process operations are mocked."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('screen', HERE / 'screen.py')
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)


class Tests(unittest.TestCase):
    def test_admission_blocks_before_pull_or_gpu(self):
        args = SimpleNamespace(port=19988)
        with patch.object(screen.socket, 'gethostname', return_value='steve-b70s'), \
             patch.object(screen, 'call', return_value=SimpleNamespace(stdout='main\n')), \
             patch.object(screen.shutil, 'disk_usage', return_value=SimpleNamespace(free=54 * 2**30)), \
             patch.object(screen, 'idle') as idle, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'Disk admission'):
                screen.preflight(args)
            idle.assert_not_called()

    def test_static_modes_and_full_precision(self):
        for mode, size in [('mtp0', [1]), ('mtp1', [1, 2]), ('mtp3', [1, 4])]:
            cmd = screen.launch(SimpleNamespace(mode=mode, port=19988), Path('/tmp/test-screen'))
            self.assertEqual(cmd.count('run'), 1)
            self.assertIn('--pull=never', cmd)
            self.assertEqual(cmd[cmd.index('--kv-cache-dtype') + 1], 'auto')
            self.assertEqual(cmd[cmd.index('--dtype') + 1], 'bfloat16')
            self.assertEqual(cmd[cmd.index('--moe-backend') + 1], 'triton')
            self.assertEqual(json.loads(cmd[cmd.index('--compilation-config') + 1])['cudagraph_capture_sizes'], size)
            if mode == 'mtp0':
                self.assertNotIn('--speculative-config', cmd)
            else:
                cfg = json.loads(cmd[cmd.index('--speculative-config') + 1])
                self.assertEqual(cfg['num_speculative_tokens'], int(mode[-1]))
                self.assertEqual(cfg['rejection_sample_method'], 'standard')

    def test_fault_patterns(self):
        for text in ['Job timed out', 'timed-out job', 'Fault response', 'CAT error', 'engine CCS reset', 'device coredump']:
            self.assertIsNotNone(screen.FAULT.search(text))
        self.assertIsNone(screen.FAULT.search('Network link changed'))

    def test_failed_client_stops_single_server_gracefully(self):
        args = SimpleNamespace(mode='mtp1', port=19988)
        commands = []
        class Process:
            returncode = 2
            def __init__(self, server=False): self.server = server
            def poll(self): return None if self.server and not commands else (0 if self.server else 2)
            def wait(self, timeout): return 0
        server, client = Process(True), Process()
        class Response(io.BytesIO):
            status = 200
        responses = [Response(b''), Response(b'{"data":[{"id":"qwen38-flash-next-fp8-tp4"}]}'), Response(b'# metrics\n')]
        def fake_run(command, **kwargs):
            commands.append(command)
            return SimpleNamespace(returncode=0, stdout='false\n', stderr='')
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(screen, 'preflight'), patch.object(screen, 'call'), \
             patch.object(screen, 'MemoryWatchdog') as watchdog, \
             patch.object(screen, 'collect_observations', return_value={}), \
             patch.object(screen, 'check_live'), patch.object(screen, 'idle'), \
             patch.object(screen, 'journal', return_value='clean boot\n'), \
             patch.object(screen.signal, 'signal'), \
             patch.object(screen.subprocess, 'Popen', side_effect=[server, client]), \
             patch.object(screen.subprocess, 'run', side_effect=fake_run), \
             patch.object(screen.urllib.request, 'urlopen', side_effect=responses):
            watchdog.return_value.check.return_value = None
            with self.assertRaisesRegex(RuntimeError, 'Client failed'):
                screen.supervise(args, Path(tmp))
        self.assertEqual(sum(c[:2] == ['docker', 'kill'] for c in commands), 1)
        self.assertIn('--signal=SIGINT', commands[0])
        self.assertFalse(any('SIGKILL' in str(c) or 'restart' in c for c in commands))

    def test_watchdog_and_cleanup_share_one_sigint(self):
        args = SimpleNamespace(mode='mtp1', port=19988)
        commands = []
        class Process:
            def poll(self): return None
            def wait(self, timeout): return 0
        class Watchdog:
            def __init__(self, run, callback): self.callback = callback
            def check(self): return None
            def start(self): self.callback('test pressure trip')
            def close(self): pass
        def fake_run(command, **kwargs):
            commands.append(command)
            return SimpleNamespace(returncode=0, stdout='false\n', stderr='')
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(screen, 'preflight'), patch.object(screen, 'call'), \
             patch.object(screen, 'collect_observations', return_value={}), \
             patch.object(screen, 'MemoryWatchdog', Watchdog), \
             patch.object(screen, 'idle'), \
             patch.object(screen, 'journal', return_value='clean boot\n'), \
             patch.object(screen.signal, 'signal'), \
             patch.object(screen.subprocess, 'Popen', return_value=Process()), \
             patch.object(screen.subprocess, 'run', side_effect=fake_run):
            with self.assertRaisesRegex(RuntimeError, 'Startup stopped'):
                screen.supervise(args, Path(tmp))
            self.assertIn('controller completion', (Path(tmp) / 'STOP').read_text())
            stop = json.loads((Path(tmp) / 'graceful-stop.json').read_text())
            self.assertEqual(stop['reason'], 'test pressure trip')
        self.assertEqual(sum(c[:2] == ['docker', 'kill'] for c in commands), 1)
        self.assertFalse(any('SIGKILL' in str(c) for c in commands))


if __name__ == '__main__':
    unittest.main()
