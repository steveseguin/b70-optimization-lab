"""Actual rolling archive admission must not accept scripted/quiescent evidence."""
import json
from pathlib import Path
import tempfile
import unittest

import archive_rolling_provider_proof as archive


class RollingArchiveAdmissionTests(unittest.TestCase):
    def test_actual_consumption_and_provenance_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);run=root/'run';proof=root/'proof'
            run.mkdir();proof.mkdir()
            (run/'rolling-ring-live-result.json').write_text('{}')
            valid=dict(schema='ownrt.rolling-provider-proof.v1',passed=True,source_run=str(run),
                target_state_exact=True,draft_state_exact=True,output_tokens_exact=True,
                actual_provider=True,actual_proposals_consumed=True,scripted_oracle_assisted=False,
                scripted_tentative_inputs=False,provenance_passed=True,provider_survival_passed=True,
                actual_proposal_rows=1,speed_claim=False)
            mutations=dict(schema='ownrt.pending-provider-proof.v1',passed=False,source_run='/different',
                target_state_exact=False,draft_state_exact=False,output_tokens_exact=False,
                actual_provider=False,actual_proposals_consumed=False,scripted_oracle_assisted=True,
                scripted_tentative_inputs=True,provenance_passed=False,provider_survival_passed=False,
                actual_proposal_rows=0,speed_claim=True)
            for key,value in mutations.items():
                for missing in (False,True):
                    with self.subTest(key=key,missing=missing):
                        candidate=dict(valid)
                        if missing:candidate.pop(key)
                        else:candidate[key]=value
                        (proof/'summary.json').write_text(json.dumps(candidate))
                        with self.assertRaisesRegex(ValueError,'PASSED explicit actual rolling-provider'):
                            archive.full(run,proof,root/'out.tgz',root/'receipt.json')
                        self.assertFalse((root/'out.tgz').exists())
                        self.assertFalse((root/'receipt.json').exists())


if __name__=='__main__':unittest.main()
