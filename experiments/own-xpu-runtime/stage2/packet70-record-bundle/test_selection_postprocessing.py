"""CPU replay of the real post-device K2 selection path, no native execution."""
import ast
import json
import shutil
from pathlib import Path
from unittest.mock import patch
import unittest
import tempfile

import p49_dispatch as dispatch
import bundle_selection
from storage import B, digest

P = Path(__file__).resolve().parent
ARCHIVE = B / 'device-cards01-a-k2fail-20261017T1933'


class SelectionPostprocessing(unittest.TestCase):
    def test_real_k2_all_experts_and_unknown_key(self):
        pins = json.loads((P/'evidence/k2fix-archive.json').read_text())['files']
        names = ('K2/run0/summary.json', 'K2/run0/dispatch-measured.json',
                 'K2/run0/receipt.json', 'K2/round3-timing/receipt.json',
                 'K2/round3-timing/timings.jsonl')
        for name in names:
            self.assertEqual(digest(ARCHIVE/name), pins[name])
        for expert in bundle_selection.EXPERTS + ('unknown-key-test',):
            with self.subTest(expert=expert), tempfile.TemporaryDirectory() as tmp:
                local = Path(tmp); run = local/'run'; run.mkdir()
                for name in ('summary.json', 'dispatch-measured.json'):
                    shutil.copyfile(ARCHIVE/'K2/run0'/name, run/name)
                for name in ('dispatch-speed6.json', 'dispatch-speed6-provenance.json', 'k2-class-registry.json'):
                    shutil.copyfile(P/name, local/name)
                selection = json.loads((P/'selection.json').read_text())
                selection['choices']['experts'] = expert if expert != 'unknown-key-test' else 'wide64'
                if expert == 'unknown-key-test':
                    selection['choices']['unexpected'] = 'must reject'
                (local/'selection.json').write_text(json.dumps(selection))
                summary = json.loads((run/'summary.json').read_text())
                bundle = dict(json.loads((P/'bundle-selection.json').read_text()), experts=expert)
                with patch.object(dispatch, 'P', local), patch.object(bundle_selection, 'selected', return_value=bundle):
                    if expert == 'unknown-key-test':
                        with self.assertRaisesRegex(ValueError, 'exactly route/recurrence/hc'):
                            dispatch.pin_production_dispatch(run, summary, round3_root=ARCHIVE/'K2/round3-timing')
                        continue
                    result, policy = dispatch.pin_production_dispatch(run, summary, round3_root=ARCHIVE/'K2/round3-timing')
                self.assertTrue(result['passed'])
                self.assertTrue(policy['packet49d_measured_selection']['passed'])
                self.assertEqual(policy['packet49d_measured_selection']['receipt_sha256'], pins['K2/round3-timing/receipt.json'])
                self.assertEqual((run/'dispatch-measured.json').read_bytes(), (P/'dispatch-speed6.json').read_bytes())
                self.assertEqual((run/'summary-k2-measured.json').read_bytes(), (ARCHIVE/'K2/run0/summary.json').read_bytes())
        for name in names:
            self.assertEqual(digest(ARCHIVE/name), pins[name], 'replay changed original evidence')

    def test_every_window_selection_reader_has_replay_coverage(self):
        # Inventory all mapping readers, including ones reached by window.py.
        # A new consumer must get an explicit postprocessing test before this passes.
        readers = set()
        for path in P.glob('*.py'):
            if path.name.startswith('test_'):
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and node.slice.value == 'choices':
                    readers.add(path.name)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'get' and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == 'choices':
                    readers.add(path.name)
        self.assertEqual(readers, {'p49_dispatch.py', 'p49d_k2.py', 'selection_gate.py',
            'chain_seal.py', 'packet56_submission.py', 'prepare_selections.py', 'prepare_packet.py', 'cpu_gate.py'})
        # Every registered window shares this selection identity gate. K2 is the
        # only additional choices-reading postprocessor; it is replayed above.
        from packet56_submission import validate_bundle
        from queue_runner import commands, EARLY, LATE
        bundle = json.loads((P/'bundle-selection.json').read_text())
        for name in commands(B/'device-cards01-a'):
            self.assertIn(name, EARLY + LATE)
            for expert in bundle_selection.EXPERTS:
                selection = json.loads((P/'selections'/('1-draft-hc-batch-'+expert)/'selection.json').read_text())
                validate_bundle(dict(bundle, experts=expert, name='1-draft-hc-batch-'+expert), selection)


if __name__ == '__main__':
    unittest.main()
