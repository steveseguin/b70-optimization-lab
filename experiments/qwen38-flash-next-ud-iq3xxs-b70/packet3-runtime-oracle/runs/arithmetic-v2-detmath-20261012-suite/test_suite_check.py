#!/usr/bin/env python3
"""Exact checker regressions, using a copied sealed oracle and genuine fixture bytes."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import suite_check as check

class ExactChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference=check.HERE.parent/'arithmetic-v2-detmath-20261011/incident-retrospective'
        cls.temp=tempfile.TemporaryDirectory(prefix='.checker.partial-',dir=check.HERE)
        cls.copy=Path(cls.temp.name)/'incident-retrospective'
        cls.copy.mkdir()
        shutil.copyfile(cls.reference/'result.json',cls.copy/'result.json')
        for source in cls.reference.glob('step*'):
            shutil.copytree(source,cls.copy/source.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_oracle_own_files(self):
        self.assertEqual(check.check_prompt(self.reference,self.reference),(64,384))

    def test_copied_oracle(self):
        self.assertEqual(check.check_prompt(self.copy,self.reference),(64,384))

    def test_corrupted_fixture(self):
        path=self.copy/'step3/layer-09.bf16'
        original=path.read_bytes()
        try:
            corrupt=bytearray(original);corrupt[31]^=1;path.write_bytes(corrupt)
            with self.assertRaisesRegex(ValueError,'hash differs'):
                check.check_prompt(self.copy,self.reference)
        finally:
            path.write_bytes(original)

    def test_corruption_with_updated_hash(self):
        path=self.copy/'step3/layer-09.bf16';ledger=path.parent/'layers.jsonl'
        original,original_ledger=path.read_bytes(),ledger.read_bytes()
        try:
            corrupt=bytearray(original);corrupt[31]^=1;path.write_bytes(corrupt)
            rows=[json.loads(line) for line in ledger.read_text().splitlines()]
            rows[9]['sha256']=check.sha(path)
            ledger.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError,'byte mismatch'):
                check.check_prompt(self.copy,self.reference)
        finally:
            path.write_bytes(original);ledger.write_bytes(original_ledger)

    def test_tokens_changed_truncated_extra(self):
        path=self.copy/'result.json';original=path.read_bytes()
        try:
            for tokens in ([0]+check.read(path)['tokens'][1:],check.read(path)['tokens'][:-1],check.read(path)['tokens']+[1]):
                result=json.loads(original);result['tokens']=tokens;path.write_text(json.dumps(result))
                with self.assertRaisesRegex(ValueError,'tokens differ|non-EOS oracle truncated'):
                    check.check_prompt(self.copy,self.reference)
        finally:
            path.write_bytes(original)

    def test_missing_fixture(self):
        path=self.copy/'step8/layer-47.bf16';backup=path.with_suffix('.saved')
        try:
            path.rename(backup)
            with self.assertRaisesRegex(ValueError,'fixture filenames'):
                check.check_prompt(self.copy,self.reference)
        finally:
            backup.rename(path)

    def test_manifest_binding(self):
        # All writes remain inside this test's private directory under the new suite.
        d=self.copy
        bundle=check.ROOT/'experiments/own-xpu-runtime/stage2/suite-inputs-20261012/incident-retrospective'
        input_path=d/'input.json';validation_path=d/'validation.json';receipt_path=d/'receipt.json'
        try:
            shutil.copyfile(bundle/'input.json',input_path)
            validation_path.write_text(json.dumps(dict(fixture_hashes=check.fixture_inventory(d,64))))
            receipt=dict(verified=True,result_sha256=check.sha(d/'result.json'),input_sha256=check.sha(input_path),validation_sha256=check.sha(validation_path))
            receipt_path.write_text(json.dumps(receipt))
            entry=dict(oracle_receipt_sha256=check.sha(receipt_path),input_bundle=str(bundle),
                       input_bundle_hashes={f.name:check.sha(f) for f in bundle.iterdir() if f.is_file()},
                       prompt_tokens=87,generated_tokens=64,ended_early=False)
            self.assertEqual(check.check_prompt(d,d,entry),(64,384))
            original=validation_path.read_bytes();validation_path.write_bytes(original+b' ')
            with self.assertRaisesRegex(ValueError,'fixture binding differs'):
                check.check_prompt(d,d,entry)
            validation_path.write_bytes(original)
            entry['input_bundle_hashes'].pop('tokens.txt')
            with self.assertRaisesRegex(ValueError,'bundle file coverage'):
                check.check_prompt(d,d,entry)
        finally:
            for p in (input_path,validation_path,receipt_path):
                p.unlink(missing_ok=True)

    def test_early_eos(self):
        d=Path(self.temp.name)/'eos-case';d.mkdir()
        try:
            shutil.copytree(self.reference/'step1',d/'step1')
            result=dict(schema='iq3-runtime-cpu-oracle.v1',status='eos',error='',arithmetic=check.IDENTITY,tokens=[248044])
            (d/'result.json').write_text(json.dumps(result))
            self.assertEqual(check.check_prompt(d,d),(1,48))
            result['tokens']=[248044,1];(d/'result.json').write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError,'EOS status mismatch'):
                check.check_prompt(d,d)
            result['tokens']=[248044,248046];(d/'result.json').write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError,'continued after EOG'):
                check.check_prompt(d,d)
            result['tokens']=[248046];(d/'result.json').write_text(json.dumps(result))
            (d/'step1/layer-00.bf16').unlink()
            with self.assertRaisesRegex(ValueError,'fixture filenames'):
                check.check_prompt(d,d)
        finally:
            shutil.rmtree(d)

    def test_run_wrapper(self):
        wrapper=Path(self.temp.name)/'wrapper';wrapper.mkdir()
        target=wrapper/'run'
        try:
            self.copy.rename(target)
            self.assertEqual(check.check_prompt(wrapper,self.reference),(64,384))
        finally:
            target.rename(self.copy);wrapper.rmdir()

    def test_runtime_receipt(self):
        path=self.copy/'receipt.json'
        try:
            path.write_text(json.dumps(dict(schema='own-runtime.iq3.packet26.run.v1',passed=True,arithmetic=check.IDENTITY,tokens=check.read(self.reference/'result.json')['tokens'])))
            self.assertEqual(check.check_prompt(self.copy,self.reference),(64,384))
            row=check.read(path);row['passed']=False;path.write_text(json.dumps(row))
            with self.assertRaisesRegex(ValueError,'runtime receipt failed'):
                check.check_prompt(self.copy,self.reference)
        finally:
            path.unlink()

if __name__=='__main__':
    unittest.main()
