"""CPU-only regressions against the finished packet136 chain; no writes."""
import base64
import copy
import importlib.util
import json
from pathlib import Path
import unittest

from chain_adapter import install
install()
import submission_evidence as fixed

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.with_name('packet136-orchestration')
spec = importlib.util.spec_from_file_location('packet136_original_submission', ORIGINAL / 'submission_evidence.py')
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)


def replace(evidence, key, raw):
    member = evidence.members[key]
    member['raw_base64'] = base64.b64encode(raw).decode()
    member['sha256'] = fixed.sha(raw)


class OracleBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chain = fixed.ROOT / fixed.STAGE / fixed.P56_PACKET / 'build/device-cards01-a'
        oracle = fixed.ROOT / fixed.STAGE / 'packet49-integrate/oracle/results'
        cls.evidence = fixed.collect(fixed.P56_PACKET, chain.resolve(), oracle.resolve())

    def test_original_reproduces_missing_direct_checker(self):
        key = str(fixed.STAGE / fixed.P56_PACKET / 'oracle/suite_check.py')
        with self.assertRaises(KeyError) as caught:
            original.derive(self.evidence, original.P56_PACKET)
        self.assertEqual(caught.exception.args, (key,))

    def test_copy_passes_complete_real_chain(self):
        result = fixed.derive(self.evidence, fixed.P56_PACKET)
        self.assertGreater(result['primary_metric']['value_tok_s'], 58.223834)
        self.assertFalse(result['realistic_final_gate']['passed'])
        self.assertTrue(result['submission_scope']['prepared_only'])

    def test_tampered_checker_with_rehashed_member_refuses(self):
        e = fixed.Evidence(copy.deepcopy(self.evidence.members))
        replace(e, 'oracle-source/suite_check.py', e.raw('oracle-source/suite_check.py') + b'\n# tampered\n')
        with self.assertRaisesRegex(ValueError, '^oracle checker changed$'):
            fixed.derive(e, fixed.P56_PACKET)

    def test_tampered_binding_with_rehashed_member_refuses(self):
        e = fixed.Evidence(copy.deepcopy(self.evidence.members))
        row = e.read('oracle-binding.json')
        row['files_sha256'][str(fixed.STAGE / 'packet49-integrate/oracle/suite_check.py')] = '0' * 64
        replace(e, 'oracle-binding.json', fixed.encoded(row))
        with self.assertRaisesRegex(ValueError, 'bound receipt hash mismatch: oracle-binding.json'):
            fixed.derive(e, fixed.P56_PACKET)

    def test_direct_binding_still_has_priority(self):
        e = fixed.Evidence(copy.deepcopy(self.evidence.members))
        seal = e.read('seal.json')
        seal['sources'][str(fixed.STAGE / fixed.P56_PACKET / 'oracle/suite_check.py')] = '0' * 64
        replace(e, 'seal.json', fixed.encoded(seal))
        pins = e.read('submission-pins.json')
        pins['lineages'][fixed.P56_PACKET]['build_receipt_sha256'] = fixed.sha(e.raw('seal.json'))
        replace(e, 'submission-pins.json', fixed.encoded(pins))
        with self.assertRaisesRegex(ValueError, '^oracle checker changed$'):
            fixed.derive(e, fixed.P56_PACKET)

    def test_authority_build_pin_independently_refuses_changed_checker(self):
        e = fixed.Evidence(copy.deepcopy(self.evidence.members))
        replace(e, 'oracle-source/suite_check.py', e.raw('oracle-source/suite_check.py') + b'\n# tampered\n')
        binding = e.read('oracle-binding.json')
        binding['files_sha256'][str(fixed.STAGE / 'packet49-integrate/oracle/suite_check.py')] = fixed.sha(e.raw('oracle-source/suite_check.py'))
        replace(e, 'oracle-binding.json', fixed.encoded(binding))
        seal = e.read('seal.json')
        seal['shared_oracle'] = binding
        seal['sources'][str(fixed.STAGE / fixed.P56_PACKET / 'oracle-binding.json')] = fixed.sha(e.raw('oracle-binding.json'))
        replace(e, 'seal.json', fixed.encoded(seal))
        pins = e.read('submission-pins.json')
        pins['lineages'][fixed.P56_PACKET]['build_receipt_sha256'] = fixed.sha(e.raw('seal.json'))
        replace(e, 'submission-pins.json', fixed.encoded(pins))
        with self.assertRaisesRegex(ValueError, '^oracle checker authority/build binding differs$'):
            fixed.derive(e, fixed.P56_PACKET)

    def test_only_checker_block_changed(self):
        before = (ORIGINAL / 'submission_evidence.py').read_text()
        after = (HERE / 'submission_evidence.py').read_text()
        start = after.index('    checker_key = str(STAGE / packet /')
        end = after.index("    if packet != 'packet49-integrate':", start)
        old = "    require(sha(e.raw('oracle-source/suite_check.py')) == seal['sources'][str(STAGE / packet / 'oracle/suite_check.py')], 'oracle checker changed')\n"
        self.assertEqual(after[:start] + old + after[end:], before)
        for name, digest in json.loads((HERE / 'copied-sources.json').read_text()).items():
            self.assertEqual(fixed.sha((ORIGINAL / name).read_bytes()), digest)
            if name != 'submission_evidence.py':
                self.assertEqual((HERE / name).read_bytes(), (ORIGINAL / name).read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
