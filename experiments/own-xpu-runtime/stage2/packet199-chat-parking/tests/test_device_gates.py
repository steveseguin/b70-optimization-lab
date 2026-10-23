"""Readiness failure transitions in temporary files; no executable is launched."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import device_gates as G


class SealFailureTests(unittest.TestCase):
    def test_failed_fresh_process_invalidates_and_preserves_provisional_seal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ready, gate = root / 'READY.json', root / 'gates.json'
            for path in (ready, gate):
                path.write_text('{"passed": true}\n')
            with patch.object(G.W, 'P', root), patch.object(G.W, 'READY', ready), patch.object(G, 'GATE', gate), \
                 patch.object(G.W, 'verify_ready'), patch.object(G.subprocess, 'run',
                    return_value=subprocess.CompletedProcess([], 1, '', 'fixture refusal')) as run:
                with self.assertRaisesRegex(ValueError, 'fixture refusal'):
                    G.finish_seal()
            self.assertEqual(run.call_count, 1)
            self.assertFalse(json.loads(ready.read_text())['passed'])
            self.assertFalse(json.loads(gate.read_text())['passed'])
            self.assertTrue(json.loads((root / 'lineage/fresh-plan-refusal/READY.json').read_text())['passed'])

    def test_failed_verification_invalidates_even_if_lineage_path_is_occupied(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ready, gate = root / 'READY.json', root / 'gates.json'
            for path in (ready, gate):
                path.write_text('{"passed": true}\n')
            (root / 'lineage/fresh-plan-refusal').mkdir(parents=True)
            with patch.object(G.W, 'P', root), patch.object(G.W, 'READY', ready), patch.object(G, 'GATE', gate), \
                 patch.object(G.W, 'verify_ready', side_effect=ValueError('source drift')), \
                 patch.object(G.subprocess, 'run', side_effect=AssertionError('no child')) as run:
                with self.assertRaises(FileExistsError):
                    G.finish_seal()
            run.assert_not_called()
            self.assertFalse(json.loads(ready.read_text())['passed'])


if __name__ == '__main__':
    unittest.main()
