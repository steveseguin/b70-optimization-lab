"""The 26 reviewed exception checks plus identity/receipt mutation regressions."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import submit_localmaxxing_results as submit

DATA = Path(__file__).resolve().parents[2] / 'experiments/qwen38-flash-next-ud-iq3xxs-b70/data'

def item(config):
    return json.loads((DATA / f'20261015-own-rt-iq3-tp2-c4096-{config}-localmaxxing-payload-queue.json').read_text())[0]

class Reviewed26Checks(unittest.TestCase):
    pass

# 13 independently reported tests per pinned identity, exactly the reviewed 26.
def reviewed(config, case):
    def test(self):
        value = item(config)
        flags = value['payload']['engineFlags']
        if case == 'authorized':
            self.assertIs(flags['realisticSuiteGatePassed'], False)
            self.assertEqual(submit.preflight_payload(value), [])
            return
        changes = {
            'authorization': ('realisticSuiteScopeException', None),
            'cap': ('requestedMaxNew', 512),
            'split': ('targetSplit', [25, 23]),
            'draft': ('draftRank', 2),
            'seal': ('buildReceiptSha256', '0' * 64),
            'nonqualifying': ('qualifying', False),
            'diagnostic': ('diagnostic_unsealed', True),
            'flipped_marker': ('realisticSuiteGatePassed', True),
            'intervals': ('metricWindowIntervals', 100),
        }
        if case in changes:
            key, change = changes[case]
            flags[key] = change
        elif case.startswith('missing_authorization_'):
            del flags['realisticSuiteScopeException']
            flags['realisticSuiteGatePassed'] = case.endswith('true')
        elif case == 'altered_headline':
            value['payload']['tokSOut'] += 0.01
        else:
            self.fail(case)
        self.assertTrue(submit.preflight_payload(value))
    return test

for config in ('s24dr0', 's23dr1'):
    for case in ('authorized', 'authorization', 'cap', 'split', 'draft', 'seal',
                 'nonqualifying', 'diagnostic', 'flipped_marker', 'intervals',
                 'missing_authorization_false', 'missing_authorization_true',
                 'altered_headline'):
        setattr(Reviewed26Checks, f'test_{config}_{case}', reviewed(config, case))

class ExactIdentityChecks(unittest.TestCase):
    def test_only_two_registered_identities(self):
        self.assertEqual(set(submit.OWNER_128_RESULTS), {'75d2c459d', '34c62b433'})

    def test_changed_identity_or_scope_cannot_escape_without_authorization(self):
        for config in ('s24dr0', 's23dr1'):
            for change in ('runtime', 'cap'):
                value = item(config)
                flags = value['payload']['engineFlags']
                del flags['realisticSuiteScopeException']
                flags['realisticSuiteGatePassed'] = True
                if change == 'runtime':
                    flags['promotionIdentity']['runtime_revision'] = 'unapproved'
                else:
                    flags['requestedMaxNew'] = 512
                with self.subTest(config=config, change=change):
                    self.assertTrue(submit.preflight_payload(value))

    def test_other_identity_fields_are_pinned(self):
        for config in ('s24dr0', 's23dr1'):
            for field in ('runtime_revision', 'optimization_identity', 'model_revision', 'suite_sha256'):
                value = item(config)
                value['payload']['engineFlags']['promotionIdentity'][field] = 'unapproved'
                with self.subTest(config=config, field=field):
                    self.assertTrue(submit.preflight_payload(value))
            for field, replacement in [('deviceCards', [2, 3]), ('strict512TokenFinalGatePassed', True),
                                        ('freshRealisticSuiteGatePassed', True)]:
                value = item(config)
                value['payload']['engineFlags'][field] = replacement
                self.assertTrue(submit.preflight_payload(value))
            value = item(config)
            value['payload']['engineVersion'] += '-other-binary'
            self.assertTrue(submit.preflight_payload(value))

    def test_diagnostic_device_receipt_refused_even_with_updated_hashes(self):
        value = item('s23dr1')
        flags = value['payload']['engineFlags']
        attpath = submit.REPO_ROOT / flags['promotionAttestation']
        att = json.loads(attpath.read_bytes())
        entry = att['quality_evidence'][0]
        path = submit.REPO_ROOT / entry['path']
        window = json.loads(path.read_bytes())
        window['diagnostic_unsealed'] = True
        raw = json.dumps(window).encode()
        entry['sha256'] = hashlib.sha256(raw).hexdigest()
        attraw = json.dumps(att).encode()
        flags['promotionAttestationSha256'] = hashlib.sha256(attraw).hexdigest()
        import promotion_evidence
        original = Path.read_bytes
        original_text = Path.read_text
        original_sha = promotion_evidence.sha256_file
        with patch.object(Path, 'read_bytes', lambda p: attraw if p == attpath else raw if p == path else original(p)), \
             patch.object(Path, 'read_text', lambda p, *a, **k: raw.decode() if p == path else original_text(p, *a, **k)), \
             patch.object(promotion_evidence, 'sha256_file', lambda p: hashlib.sha256(raw).hexdigest() if p == path else original_sha(p)):
            self.assertTrue(any('diagnostic/unqualified' in message for message in submit.preflight_payload(value)))

    def test_compact_snippet_and_confirmations_never_change_headline(self):
        value = item('s23dr1')
        self.assertEqual(value['payload']['tokSOut'], 39.42200890284251)
        self.assertLessEqual(len(value['payload']['engineFlags']['commandSnippet']), 600)
        for headline in (39.385607501240855, 39.377848367958954):
            changed = copy.deepcopy(value)
            changed['payload']['tokSOut'] = headline
            self.assertTrue(submit.preflight_payload(changed))

if __name__ == '__main__':
    unittest.main()
