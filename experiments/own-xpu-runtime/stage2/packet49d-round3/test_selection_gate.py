import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import selection_gate as s


def decision(savings=(17., 17.)):
    selected = {source: {'variant': 'control', 'owner_saved_us': [0., 0.]}
                for source in (*s.CLASS_MAP.values(), 'ffn.combine')}
    selected['route'] = {'variant': 'route-rank4', 'owner_saved_us': list(savings)}
    return dict(schema='own-runtime.packet54.two-owner-timing.v1', passed=True,
                device_executed=True, selected_classes=selected, owner_saved_us=list(savings),
                banked_p53b_owner_us=[23.4385, 23.4375],
                combined_owner_us=[23.4385+savings[0], 23.4375+savings[1]],
                integration_threshold_us=40, packet49d_trigger=True, windows=['T1', 'T2'])


class SelectionTests(unittest.TestCase):
    def test_mutated_verifier_refused_before_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); packet = root/'packet54'; packet.mkdir()
            verifier = packet/'summarize.py'; verifier.write_text('original')
            (packet/'seal.json').write_text(json.dumps({'sources': {
                'packet54/summarize.py': s.digest(verifier)}}))
            seal_sha = s.digest(packet/'seal.json')
            verifier.write_text('mutated')
            with patch.object(s, 'ROOT', root), patch.object(s, 'P54', packet), \
                 patch.object(s, 'P54_SEAL_SHA', seal_sha), patch.object(s.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'source changed'):
                    s.replay([root/'T1', root/'T2'])
                run.assert_not_called()

    def test_census(self):
        for route in s.CHOICES['route']:
            for recurrence in s.CHOICES['recurrence']:
                for hc in s.CHOICES['hc']:
                    s.validate_choices(dict(route=route, recurrence=recurrence, hc=hc))
        for bad in ({}, dict(route='production', recurrence='production', hc='norm-subgroup128'),
                    dict(route='production', recurrence='production', hc='production', extra='x')):
            with self.assertRaises(ValueError):
                s.validate_choices(bad)

    def test_combined_not_independent25us_bar(self):
        choices, values = s.decision_choices(decision())
        self.assertEqual(choices, dict(route='route-rank4', recurrence='production', hc='production'))
        self.assertTrue(all(x >= 40 for x in values))

    def test_both_owners_and_finite(self):
        for values in ((16., 30.), (30., 16.), (float('nan'), 30.), (True, 30.)):
            with self.assertRaises(ValueError):
                s.decision_choices(decision(values))

    def test_forged_total_and_closed_candidate(self):
        base = decision()
        for change in ('owner_saved_us', 'combined_owner_us', 'banked_p53b_owner_us'):
            row = copy.deepcopy(base); row[change] = [999, 999]
            with self.assertRaises(ValueError):
                s.decision_choices(row)
        row = copy.deepcopy(base)
        row['selected_classes']['ffn.combine']['variant'] = 'combine-vector4'
        with self.assertRaises(ValueError):
            s.decision_choices(row)

    def test_pending_selection_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'selection.json').write_text(json.dumps(dict(schema='packet49d.selection.v1',
                choices=dict.fromkeys(s.CHOICES, 'production'), decision=None)))
            with patch.object(s, 'P', root), self.assertRaisesRegex(ValueError, 'pending'):
                s.verify_selection()

    def test_receipt_replay_and_choice_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = decision()
            (root/'selection-decision.json').write_text(json.dumps(row))
            selection = dict(schema='packet49d.selection.v1',
                choices=dict(route='production', recurrence='production', hc='production'),
                decision=dict(path='selection-decision.json', sha256=s.digest(root/'selection-decision.json')))
            (root/'selection.json').write_text(json.dumps(selection))
            with patch.object(s, 'P', root), patch.object(s, 'replay', return_value=row):
                with self.assertRaisesRegex(ValueError, 'differs from common'):
                    s.verify_selection()
            with patch.object(s, 'P', root), patch.object(s, 'replay', return_value={}):
                with self.assertRaisesRegex(ValueError, 'verified device'):
                    s.verify_selection()


    def test_coordinator_amendment_admits_observed_30us_only(self):
        # Real p54 owners: selected 6.5645/6.564 with banked 23.4385/23.4375.
        row = decision((6.5645, 6.564))
        row['packet49d_trigger'] = False
        choices, values = s.decision_choices(row)
        self.assertEqual(choices['route'], 'route-rank4')
        self.assertTrue(all(30 <= x < 40 for x in values))
        low = decision((6.5, 6.5)); low['packet49d_trigger'] = False
        with self.assertRaisesRegex(ValueError, 'reach 30'):
            s.decision_choices(low)
        lied = decision((6.5645, 6.564))  # trigger True although below the original 40
        with self.assertRaisesRegex(ValueError, 'decision differs'):
            s.decision_choices(lied)

    def test_amendment_tamper_and_absence(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)/'coordinator-amendment.json'
            fake.write_text(s.AMENDMENT.read_text().replace('30', '10'))
            with patch.object(s, 'AMENDMENT', fake), self.assertRaisesRegex(ValueError, 'amendment changed'):
                s.integration_threshold()
            with patch.object(s, 'AMENDMENT', Path(tmp)/'missing.json'):
                self.assertEqual(s.integration_threshold(), (40, None))
                row = decision((6.5645, 6.564)); row['packet49d_trigger'] = False
                with self.assertRaisesRegex(ValueError, 'reach 40'):
                    s.decision_choices(row)

if __name__ == '__main__':
    unittest.main()
