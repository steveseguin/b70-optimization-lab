"""Fast reseal verifies existing bindings; no compiler or fixture execution."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import p49_seal as seal


class ResealTests(unittest.TestCase):
    def test_cpu_seal_rejects_changed_bindings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=dict(passed=True,sources={'source':'hash'})
            (root/'cpu-preparation-seal.json').write_text(json.dumps(base))
            with patch.object(seal,'P',root),patch.object(seal,'checked',return_value=base):
                self.assertEqual(seal.verify_cpu(),base)
            with patch.object(seal,'P',root),patch.object(seal,'checked',return_value=dict(base,sources={})):
                with self.assertRaises(AssertionError):seal.verify_cpu()

    def test_selection_changes_final_seal_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);packet=root/'packet';packet.mkdir()
            base=dict(passed=True,sources={'code':'fixed'},artifacts_sha256={'device/engine':'fixed'})
            (packet/'cpu-preparation-seal.json').write_text(json.dumps(base))
            (packet/'selection.json').write_text('{}')
            (packet/'selection-decision.json').write_text('{}')
            with patch.object(seal,'P',packet),patch.object(seal,'ROOT',root),patch.object(seal,'verify_cpu',return_value=base),patch('selection_gate.verify_selection',return_value={'selected':'bound'}):
                first=seal.selected_seal()
                (packet/'selection.json').write_text('{"changed":true}')
                second=seal.selected_seal()
            self.assertEqual(first['artifacts_sha256'],second['artifacts_sha256'])
            self.assertEqual(first['cpu_preparation_seal_sha256'],second['cpu_preparation_seal_sha256'])
            self.assertNotEqual(first['sources'],second['sources'])
            self.assertTrue(first['device_admission_ready'])
            self.assertEqual(base['sources'],{'code':'fixed'})

    def test_no_rebuild_in_fast_path(self):
        import inspect
        text=inspect.getsource(seal.selected_seal)+inspect.getsource(seal.verify_cpu)
        for forbidden in ('subprocess','configure(', 'run(', 'cpu_gate.main'):
            self.assertNotIn(forbidden,text)


if __name__=='__main__':unittest.main()
