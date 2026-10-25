"""Archive admission rejects partial persistent parity and policy overclaims."""
import json
from pathlib import Path
import tempfile
import unittest
import archive_persistent_rolling_proof as archive

class PersistentArchiveAdmissionTests(unittest.TestCase):
    def valid(self, run, policy='qualification'):
        d=dict(schema='ownrt.persistent-rolling-proof.v1',passed=True,source_run=str(run),
            requests=2,check_policy=policy,scripted_oracle_assisted=False,speed_claim=False,
            qualified_reference_parity=True if policy=='measured' else None,
            byte_verification_enabled=policy=='qualification',provider_survival_checks_enabled=policy=='qualification')
        for key in ('target_state_exact','draft_state_exact','output_tokens_exact','all_requests_full_state_parity',
                    'all_cold_resets_checked','mandatory_restore_checks_passed','actual_provider',
                    'actual_proposals_consumed','provenance_passed'):d[key]=True
        return d

    def test_missing_or_mutated_parity_refused_before_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run';proof=Path(tmp)/'proof';run.mkdir();proof.mkdir()
            (run/'persistent-rolling-result.json').write_text('{}')
            valid=self.valid(run)
            for key in [k for k in valid if k!='qualified_reference_parity']:
                for missing in (False,True):
                    with self.subTest(key=key,missing=missing):
                        d=dict(valid)
                        if missing:d.pop(key)
                        elif type(d[key]) is bool:d[key]=not d[key]
                        elif type(d[key]) is int:d[key]+=1
                        else:d[key]='wrong'
                        (proof/'summary.json').write_text(json.dumps(d))
                        with self.assertRaises(ValueError):archive.full(run,proof,Path(tmp)/'out.tgz',Path(tmp)/'receipt.json')
                        self.assertFalse((Path(tmp)/'out.tgz').exists())

    def test_both_policies_pass_summary_gate_but_do_not_borrow_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run';proof=Path(tmp)/'proof';run.mkdir();proof.mkdir()
            (run/'persistent-rolling-result.json').write_text('{}')
            for policy in ('qualification','measured'):
                d=self.valid(run,policy);(proof/'summary.json').write_text(json.dumps(d))
                with self.assertRaises(FileNotFoundError):archive.full(run,proof,Path(tmp)/'out.tgz',Path(tmp)/'receipt.json')
            d['byte_verification_enabled']=True;(proof/'summary.json').write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,'diagnostic policy'):archive.full(run,proof,Path(tmp)/'out.tgz',Path(tmp)/'receipt.json')

if __name__=='__main__':unittest.main()
