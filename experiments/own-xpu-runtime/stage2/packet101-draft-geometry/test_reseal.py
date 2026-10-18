"""Regression: mutable parent outputs cannot invalidate a descendant screen."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import reseal
from build_engine import sha


class LineageTests(unittest.TestCase):
    def test_parent_orchestration_outputs_excluded(self):
        for leaf in ('selection.json', 'submission-pins.json', 'ready.json',
                     'bundle-selection.json', 'composition-selection.json',
                     'screen-seal.json', 'screen-jobs-seal.json', 'memory-plan.json',
                     'evidence/new-report.json', 'decisions/new/selection.json',
                     'selections/new/selection.json', 'new-orchestration-output.json'):
            with self.subTest(leaf=leaf):
                self.assertEqual(reseal.parent_policy(reseal.PARENT + leaf), 'exclude')

    def test_build_inputs_kept_and_evidence_localized(self):
        for leaf in ('main.cpp', 'p28/submit.hpp', 'p42_gdn.inc',
                     'build/device/own-rt-iq3', 'build/device/p60_submit.o',
                     'build-device-receipt.json', 'bundle_selection.py'):
            self.assertEqual(reseal.parent_policy(reseal.PARENT + leaf), 'keep')
        self.assertEqual(reseal.parent_policy(reseal.PARENT + 'evidence/object-identity.json'), 'snapshot')

    def test_mutable_change_ignored_but_source_change_refused(self):
        with tempfile.TemporaryDirectory(dir=reseal.P / 'build/tmp') as tmp:
            root = Path(tmp)
            source = root / reseal.PARENT / 'main.cpp'
            source.parent.mkdir(parents=True)
            source.write_text('original kernel')
            rows = {reseal.PARENT + 'main.cpp': sha(source),
                    reseal.PARENT + 'selection.json': 'old mutable hash'}
            with patch.object(reseal, 'ROOT', root):
                active, excluded, _ = reseal.project_sources(rows)
                self.assertEqual(list(active), [reseal.PARENT + 'main.cpp'])
                self.assertEqual(list(excluded), [reseal.PARENT + 'selection.json'])
                source.write_text('changed kernel')
                with self.assertRaises(AssertionError):
                    reseal.project_sources(rows)

    def test_active_seals_have_local_selection_and_unchanged_artifacts(self):
        for label in ('control', 'draft_attention'):
            path = reseal.DEST / (label + '-' + reseal.ROUND)
            old = reseal.P / 'selections' / label
            seal = json.loads((path / 'screen-seal.json').read_text())
            original = json.loads((old / 'screen-seal.json').read_text())
            self.assertEqual(seal['artifacts'], original['artifacts'])
            self.assertEqual((path / 'selection.json').read_bytes(), (old / 'selection.json').read_bytes())
            self.assertEqual(seal['sources'][str((path / 'selection.json').relative_to(reseal.ROOT))], sha(path / 'selection.json'))
            self.assertTrue(all(reseal.parent_policy(p) == 'keep' for p in seal['sources']))

    def test_jobs_are_fresh_and_bracket_is_complete(self):
        from screen_jobs import jobs as old_jobs, output as old_output
        from screen_jobs_reseal import jobs, output, verify
        verify()
        for lane in ('A', 'B'):
            rows = jobs(lane)
            self.assertEqual([r['choice'] for r in rows], ['control', 'draft_attention', 'control'])
            self.assertTrue({output(r) for r in rows}.isdisjoint({old_output(r) for r in old_jobs(lane)}))
            self.assertTrue(all(not output(r).exists() for r in rows))


if __name__ == '__main__':
    unittest.main()
