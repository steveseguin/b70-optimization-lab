"""CPU-only calibration and coordinator boundary checks; no subprocess launch."""
import json
from pathlib import Path
import tempfile
import struct
import types
import unittest
from unittest.mock import patch

import queue_runner

P = Path(__file__).resolve().parent


class Packet56Tests(unittest.TestCase):
    def test_preregistered_minimal_prefix(self):
        row = json.loads((P/'calibration/selection.json').read_text())
        rule = json.loads((P/'calibration/preregistration.json').read_text())
        hist = {int(k):v for k,v in row['histogram'].items()}
        n = row['draft_vocab_rows']
        total = sum(hist.values())
        covered = sum(v for k,v in hist.items() if k<n)
        previous = sum(v for k,v in hist.items() if k<n-rule['row_alignment'])
        self.assertEqual(n, 91392)
        self.assertEqual(total, 19477)
        self.assertEqual(covered, 19382)
        self.assertLess(previous*1000, total*995)
        self.assertGreaterEqual(covered*1000, total*995)
        self.assertTrue(all(x['path'].startswith(('docs/','scripts/')) for x in rule['sources']))

    def test_chain_retains_scope_and_oracle(self):
        out = Path('/home/steve/own-xpu-runtime-results/packet103-record-bundle/build/device-cards01-a')
        commands = queue_runner.commands(out)
        self.assertEqual(tuple(commands), queue_runner.EARLY+queue_runner.LATE)
        for name, argv in commands.items():
            self.assertEqual(argv[argv.index('--card')+1], '0')
            self.assertEqual(argv[argv.index('--context')+1], '4096')
            self.assertEqual(argv[argv.index('--draft-rank')+1], '1')
            self.assertEqual(argv[argv.index('--target-split')+1], '0')
            self.assertIn('packet103-record-bundle/window.py', ' '.join(argv))
            self.assertNotIn('packet49d-round3', ' '.join(argv))
        self.assertEqual((P/'oracle').resolve(), (P.parent/'packet49-integrate/oracle').resolve())
        self.assertIn('--exactness-window', commands['WS128'])

    def test_requires_two_distinct_head_windows(self):
        for paths in (None, [], [Path('same'),Path('same')]):
            with self.assertRaises(ValueError):
                queue_runner.prefix_prerequisites(paths)

    def test_failed_head_window_blocks_chain(self):
        fake = types.SimpleNamespace(verify_window=lambda _: (_ for _ in ()).throw(ValueError('bad raw events')))
        with patch.dict('sys.modules', {'parent_head':fake}):
            with self.assertRaisesRegex(ValueError,'bad raw events'):
                queue_runner.prefix_prerequisites([Path('first'),Path('second')])

    def test_duplicate_owner_cannot_be_two_windows(self):
        fake = types.SimpleNamespace(verify_window=lambda _: dict(pid=123,process_start_ticks=456,exact_output_identity='abc'))
        with patch.dict('sys.modules', {'parent_head':fake}):
            with self.assertRaisesRegex(ValueError,'fresh process'):
                queue_runner.prefix_prerequisites([Path('first'),Path('second')])

    def test_kd_prefix_proposal_checks_values_and_ties(self):
        from draft_window import prefix_proposals
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'row-3').mkdir()
            logits=root/'row-3/logits.bf16'
            trace=root/'draft-capture.jsonl'
            for values,token in [([0x8000,0,0xbf80],0),([0x3f80,0x4000,0x4000],1),([0xc000,0xbf80,0xc040],1)]:
                logits.write_bytes(struct.pack('<3H',*values))
                trace.write_text(json.dumps(dict(position=3,token=token))+'\n')
                self.assertEqual(prefix_proposals(root,3),{'3':token})
            trace.write_text(json.dumps(dict(position=3,token=0))+'\n')
            with self.assertRaisesRegex(ValueError,'argmax'):
                prefix_proposals(root,3)


if __name__ == '__main__':
    unittest.main()
