"""CPU regression against the retained passing and failed device receipts."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from common import HERE, ROOT, read
import smoke_precondition as gate


class SmokePreconditionTests(unittest.TestCase):
    def proposal(self, output):
        job = read(ROOT / 'experiments/own-xpu-runtime/ops/lane-queue/proposed-p151-smoke-B.txt')
        job['argv'][job['argv'].index('--output') + 1] = str(output)
        return job

    def check_proposal(self, job):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'proposal.json'
            path.write_text(json.dumps(job))
            return gate.checked_smoke('sibling', 'B', path)

    def test_current_p151d_smoke_admitted(self):
        self.assertTrue(gate.checked_smoke('sibling', 'B')['passed'])

    def test_old_failed_smoke_refused(self):
        output = HERE / 'evidence/device-sibling-smoke-B'
        with self.assertRaisesRegex(ValueError, 'qualified completed window'):
            self.check_proposal(self.proposal(output))
        with self.assertRaisesRegex(ValueError, 'device phase incomplete'):
            gate.load(output)

    def test_missing_smoke_refused(self):
        with self.assertRaises(FileNotFoundError):
            self.check_proposal(self.proposal(HERE / 'evidence/missing-p151e-smoke'))

    def test_failed_result_refused(self):
        with patch.object(gate, 'load', return_value={'passed': False}):
            with self.assertRaisesRegex(ValueError, 'exact matching'):
                gate.checked_smoke('sibling', 'B')


if __name__ == '__main__':
    unittest.main()
