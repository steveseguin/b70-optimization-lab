"""CPU-only missing-input regressions; mutations are confined to temporary files."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import check_inputs as check
import queue_runner as queue


class InputTests(unittest.TestCase):
    def fixture_tree(self, root):
        fixtures = root / 'build/fusion-fixtures'
        fixtures.mkdir(parents=True)
        names = [f'case-{i}.fixture' for i in range(72)]
        for name in names:
            (fixtures / name).write_bytes(name.encode())
        (fixtures / 'cases.txt').write_text('\n'.join(names) + '\n')
        files = {p.name: dict(bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                 for p in fixtures.iterdir()}
        (root / 'input-fixtures.json').write_text(json.dumps(dict(files=files)))
        return fixtures

    def test_missing_list_and_nested_fixture_refuse(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixtures = self.fixture_tree(root)
            with patch.object(check, 'P', root):
                good = check.Inventory()
                check.fixture_files(good)
                self.assertEqual(good.errors, [])
                for name in ('cases.txt', 'case-71.fixture'):
                    raw = (fixtures / name).read_bytes()
                    (fixtures / name).unlink()
                    bad = check.Inventory()
                    check.fixture_files(bad)
                    self.assertTrue(any(name in error for error in bad.errors), bad.errors)
                    (fixtures / name).write_bytes(raw)

    def test_fixture_corruption_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixtures = self.fixture_tree(root)
            (fixtures / 'case-0.fixture').write_bytes(b'bad')
            with patch.object(check, 'P', root):
                inv = check.Inventory()
                check.fixture_files(inv)
                self.assertTrue(any('case-0.fixture' in error for error in inv.errors))

    def test_missing_nested_bundle_and_model_refuse_without_payload_read(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model = root / 'model'
            model.mkdir()
            (model / 'weights.gguf').write_bytes(b'abcd')
            (root / 'input.json').write_text(json.dumps(dict(model_dir=str(model), files={})))
            (root / 'identity.tsv').write_text('weights.gguf 4\n')
            (root / 'plan.tsv').write_text('weights.gguf tensor cls 14 0 4\n')
            (root / 'tokens.txt').write_text('1 2\n')
            (root / 'vocab.bin').write_bytes(b'vocab')
            inv = check.Inventory()
            check.bundle(inv, root, ['KD'])
            self.assertEqual(inv.errors, [])
            self.assertFalse(inv.files[str(model / 'weights.gguf')]['payload_read'])
            (root / 'tokens.txt').unlink()
            (model / 'weights.gguf').unlink()
            inv = check.Inventory()
            check.bundle(inv, root, ['KD'])
            self.assertTrue(any('tokens.txt' in error for error in inv.errors))
            self.assertTrue(any('weights.gguf' in error for error in inv.errors))

    def test_generated_dependency_is_future_only_until_consumer_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / 'K2/run0/dispatch-measured.json'
            inv = check.Inventory()
            inv.produced(missing, 'K2', 'KD')
            self.assertEqual(inv.errors, [])
            inv.produced(missing, 'K2', 'KD', require_now=True)
            self.assertTrue(inv.errors)
            inv = check.Inventory()
            inv.produced(missing, 'KD', 'K2')
            self.assertTrue(inv.errors)

    def test_plan_propagates_input_refusal_without_launch(self):
        args = ['queue_runner.py', '--plan', '--phase', 'all', '--output-root', '/test']
        with patch('sys.argv', args), patch.object(queue, 'input_preflight',
                  side_effect=subprocess.CalledProcessError(1, ['check_inputs.py'])), patch.object(queue, 'run') as launch:
            with self.assertRaises(subprocess.CalledProcessError):
                queue.main()
            launch.assert_not_called()

    def test_preflight_is_cpu_helper_and_checks_requested_window(self):
        args = SimpleNamespace(output_root=Path('/test'), prefix_windows=[Path('/a'), Path('/b')])
        with patch.object(queue.subprocess, 'run') as run:
            queue.input_preflight(args, 'KD')
            command = run.call_args.args[0]
            self.assertEqual(command[:8], ['nice', '-n', '19', 'taskset', '-c', '8-15,24-31', 'python3', '-B'])
            self.assertEqual(command[-2:], ['--window', 'KD'])
            self.assertNotIn('--authorized-device-window', command)


if __name__ == '__main__':
    unittest.main()
