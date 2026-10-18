"""CPU admission tests; no oracle jobs or weight reads."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import shared_oracle as s

class SharedOracleTests(unittest.TestCase):
    def test_actual_static_authority(self):
        row = s.static_binding()
        self.assertEqual(row['arithmetic'], 'iq3-p49-split32-v1')
        self.assertEqual((s.P/'oracle').resolve(), s.AUTHORITY.resolve())

    def test_changed_static_pin_refuses(self):
        with patch.object(s, 'digest', return_value='changed'):
            with self.assertRaisesRegex(ValueError, 'static input changed'):
                s.static_binding()

    def test_pending_or_failed_never_completes(self):
        with patch.object(s, 'static_binding', return_value={}), patch('oracle.oracle_job.status', return_value=1):
            with self.assertRaisesRegex(ValueError, 'complete full-model oracle'):
                s.completed_binding()

    def test_completion_hash_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'completion.json').write_text(json.dumps(dict(manifest_sha256='manifest',determinism_sha256='repeat',kd_capture_sha256='capture')))
            with patch.object(s, 'RESULTS', root), patch.object(s, 'static_binding', return_value=dict(arithmetic='iq3-p49-split32-v1',unit='same')), patch('oracle.oracle_job.status', return_value=0):
                bound = s.completed_binding()
                self.assertEqual(bound['completion_sha256'], s.digest(root/'completion.json'))
                self.assertEqual(bound['manifest_sha256'], 'manifest')
                self.assertEqual(bound['static_binding_sha256'], s.digest(s.P/'oracle-binding.json'))

if __name__ == '__main__':
    unittest.main()
