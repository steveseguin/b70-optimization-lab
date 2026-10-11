"""Exercise the real staged controller through admission, stopping before Docker.

Reads this lab's installed model config/index and bounded shard headers only.
No tensor payload, native runtime, device, journal, listener or service access.
"""
import contextlib
import datetime
import importlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import build_patch as builder


class BeforeDocker(Exception):
    pass


@contextlib.contextmanager
def staged_modules(stage, repo):
    # Import complete modules, including their actual module-level roots.
    names = [p.stem for p in stage.glob('*.py')]
    with patch.dict(os.environ, SCREEN1B_SOURCE_REPO=str(repo), SCREEN1B_MOE_BOUNDARY='1'), \
            patch.object(sys, 'path', [str(stage), *sys.path]), patch.dict(sys.modules):
        for name in names:
            sys.modules.pop(name, None)
        yield importlib.import_module('screen')


class StagedPaths(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='moe-source-paths-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        with patch.dict(os.environ, SCREEN1B_MOE_BOUNDARY='1'):
            self.stage = builder.stage(self.root / 'external-package')

    def test_controller_admission_and_complete_prediction_before_docker(self):
        with staged_modules(self.stage, builder.REPO) as screen:
            memory = sys.modules['memory_plan']
            paths = sys.modules['source_paths']
            placement = sys.modules['placement_plan']
            self.assertEqual(screen.REPO, builder.REPO)
            self.assertEqual(placement.LANE, builder.LANE.parent)
            self.assertEqual(memory.HERE, self.stage)
            self.assertEqual(paths.repo_input('data/example.json'), builder.REPO / 'data/example.json')
            run = self.root / 'never-launched'
            receipt = self.root / 'synthetic-health.json'
            now = datetime.datetime.now(datetime.timezone.utc)
            utc = lambda seconds: (now - datetime.timedelta(seconds=seconds)).strftime('%Y-%m-%d %H:%M:%S UTC')
            receipt.write_text(json.dumps(dict(
                schema=screen.HEALTH_SCHEMA, passed=True, kernel='CPU fixture', torch='CPU fixture',
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                start_utc=utc(20), end_utc=utc(10), journal_fault_lines_during_probe=[], device_count=4,
                cards=[dict(device=f'xpu:{r}', name='synthetic admission card', **{'pass': True},
                            copy_roundtrip_exact=True, gemm_repeat_exact=True, staged_from_previous_exact=True,
                            gemm_fp32_max_abs_err=0, gemm_bf16_max_abs_err=0) for r in range(4)])))
            argv = [str(self.stage / 'screen.py'), 'run', '--mode', 'calibrate-load',
                    '--loading-ram-guard-gb', '96', '--health-receipt', os.path.relpath(receipt, builder.REPO),
                    '--previous-stop-utc', utc(400), '--run-dir', str(run), '--execute']
            opened = set()
            active = [False]
            def audit(event, args):
                if active[0] and event == 'open' and isinstance(args[0], (str, bytes)):
                    path = Path(os.fsdecode(args[0])).resolve()
                    self.assertTrue(path.is_file(), f'missing staged input: {path}')
                    opened.add(path)
            sys.addaudithook(audit)
            real_call = screen.call
            def call(command, **kwargs):
                if str(command[0]) == 'git':
                    return real_call(command, **kwargs)
                self.assertEqual(command[:3], ['docker', 'image', 'inspect'])
                raise BeforeDocker('stopped before the first Docker/service operation')
            prediction = Mock(wraps=screen.build_prediction)
            fake_socket = Mock()
            fake_socket.return_value.__enter__ = Mock(return_value=Mock())
            fake_socket.return_value.__exit__ = Mock(return_value=False)
            # Hardware/disk availability and clean journal are synthetic;
            # admission logic, health validation, seals and prediction are real.
            cwd = Path.cwd()
            try:
                os.chdir(self.root)
                with patch.object(sys, 'argv', argv), patch.object(screen, 'call', side_effect=call), \
                        patch.object(screen, 'idle') as idle, \
                        patch.object(screen.socket, 'socket', fake_socket), \
                        patch.object(screen.socket, 'gethostname', return_value='steve-b70s'), \
                        patch.object(screen.shutil, 'disk_usage', return_value=Mock(free=200 * 2**30)), \
                        patch.object(screen, 'journal', return_value='CPU fixture: clean journal\n'), \
                        patch.object(screen.calibration, 'trip_reason', return_value=None), \
                        patch.object(screen, 'build_prediction', prediction), \
                        contextlib.redirect_stdout(io.StringIO()):
                    active[0] = True
                    with self.assertRaises(BeforeDocker):
                        screen.main()
                    idle.assert_called_once()
            finally:
                active[0] = False
                os.chdir(cwd)
            prediction.assert_called_once()
            self.assertFalse(run.exists())
            manifest = json.loads((self.stage / 'overlay-manifest.json').read_text())
            required = {self.stage / rel for rel in manifest['support_files']}
            required |= {self.stage / manifest['source'] / rel for rel in manifest['files']}
            required |= {self.stage / 'overlay-manifest.json', receipt,
                         placement.LANE / 'data/20260913-q38-expert-host-placement-a315-census-5gib-mc2-per-rank.json',
                         screen.MODEL / 'config.json', screen.MODEL / 'model.safetensors.index.json'}
            index = json.loads((screen.MODEL / 'model.safetensors.index.json').read_text())
            required |= {screen.MODEL / name for name in index['weight_map'].values()}
            bounds = json.loads((self.stage / 'memory-bounds.json').read_text())
            required |= {Path(bounds['source_root']) / rel for rel in bounds['source_sha256']}
            self.assertFalse(required - opened, f'unexercised inputs: {required - opened}')
            self.assertFalse(any(self.root / 'data' in p.parents for p in opened))
            # Tuned/placement map and all container inputs belong to the stage;
            # /screen is output, and is intentionally not created by this test.
            command = screen.launch(screen.argparse.Namespace(mode='calibrate-load', port=19988,
                                                               loading_ram_guard_gb=96), run)
            for i, arg in enumerate(command[:-1]):
                if arg == '-v' and not command[i+1].endswith(':/screen'):
                    self.assertTrue(Path(command[i+1].split(':')[0]).exists())
            self.assertIn('Q38_EXPERT_HOST_PLACEMENT=/screen-package/placement-attempt6-v5.json', command)

    def test_relative_metadata_and_input_paths_use_source_repo(self):
        repo = self.root / 'source-repo'
        model = repo / 'data/model'
        model.mkdir(parents=True)
        (model / 'config.json').write_text('{}')
        (model / 'model.safetensors.index.json').write_text(json.dumps(
            {'weight_map': {'w': 'tiny.safetensors'}, 'metadata': {'total_size': 2}}))
        header = json.dumps({'w': {'shape': [1], 'dtype': 'BF16', 'data_offsets': [0, 2]}}).encode()
        (model / 'tiny.safetensors').write_bytes(struct.pack('<Q', len(header)) + header + b'\0\0')
        with staged_modules(self.stage, repo):
            memory = sys.modules['memory_plan']
            paths = sys.modules['source_paths']
            config, tensors, metadata = memory.read_metadata('data/model')
            self.assertEqual(tensors['w']['bytes'], 2)
            self.assertEqual(metadata['header_bytes_read'], len(header))
            self.assertEqual(paths.repo_input('data/receipt.json'), repo / 'data/receipt.json')
            self.assertEqual(paths.repo_input(model), model)
            self.assertEqual(sys.modules['placement_plan'].LANE, repo / 'experiments/qwen38-flash-next-fp8-b70')

    def test_protocol_and_routing_inputs_use_source_repo(self):
        with staged_modules(self.stage, builder.REPO):
            protocol = importlib.import_module('protocol')
            vram = sys.modules['vram_plan']
            self.assertEqual(protocol.ROOT, builder.REPO)
            for path in protocol.FILE_PINS:
                self.assertTrue(path.is_file(), path)
                self.assertTrue(path.is_relative_to(builder.REPO), path)
            self.assertEqual(vram.LANE, builder.LANE.parent)
            for rank in range(4):
                self.assertTrue((vram.LANE / f'data/20260907-tp4-mtp1-a315-routing-census-rank{rank}.json').is_file())

    def test_stage_without_source_repo_fails_closed(self):
        with staged_modules(self.stage, builder.REPO), patch.dict(os.environ):
            os.environ.pop('SCREEN1B_SOURCE_REPO')
            sys.modules.pop('source_paths')
            with self.assertRaisesRegex(RuntimeError, 'requires SCREEN1B_SOURCE_REPO'):
                importlib.import_module('source_paths')
