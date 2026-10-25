"""Pending proof admission cannot be satisfied by the old quiescent proof."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import archive_pending_provider_proof as archive


class PendingArchiveAdmissionTests(unittest.TestCase):
    def test_pending_survival_requirements_are_independent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);run=root/'run';proof=root/'proof'
            run.mkdir();proof.mkdir()
            (run/'pending-ring-live-result.json').write_text('{}')
            valid=dict(schema='ownrt.pending-provider-proof.v1',passed=True,source_run=str(run),
                target_state_exact=True,draft_state_exact=True,provider_survival_passed=True,
                output_tokens_exact=True,actual_provider=True,scripted_tentative_inputs=True,
                provider_survival_checks=2,provider_survival_discarded_rows=3,
                provider_survival_advanced_checks=2,pending_borrows={'1':1,'2':2},
                recursive_proposals_consumed=False,speed_claim=False)
            mutations=dict(schema='ownrt.ring-live-proof.v1',passed=False,source_run='/different',
                target_state_exact=False,draft_state_exact=False,provider_survival_passed=False,
                output_tokens_exact=False,actual_provider=False,scripted_tentative_inputs=False,
                provider_survival_checks=1,provider_survival_discarded_rows=2,
                provider_survival_advanced_checks=1,pending_borrows={'1':0,'2':3},
                recursive_proposals_consumed=True,speed_claim=True)
            for key,value in mutations.items():
                for missing in (False,True):
                    with self.subTest(key=key,missing=missing):
                        candidate=copy.deepcopy(valid)
                        if missing:candidate.pop(key)
                        else:candidate[key]=value
                        (proof/'summary.json').write_text(json.dumps(candidate))
                        with self.assertRaisesRegex(ValueError,'PASSED explicit pending-provider'):
                            archive.full(run,proof,root/'out.tgz',root/'receipt.json')
                        self.assertFalse((root/'out.tgz').exists())
                        self.assertFalse((root/'receipt.json').exists())


if __name__=='__main__':unittest.main()
