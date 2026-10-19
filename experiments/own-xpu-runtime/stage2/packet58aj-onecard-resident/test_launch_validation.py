"""Refuse the exact-key regression and leaked caps before any native launch."""
import copy
import json
from pathlib import Path
import resource
import tempfile
import unittest
from unittest.mock import patch
import exec_limits as L
import views as V


class LaunchValidationTests(unittest.TestCase):
    def test_exact_tile16_only_keys_and_values(self):
        good=V.validate('down-tile16')
        changes=[]
        for key in good['choices']:
            row=copy.deepcopy(good);row['choices'].pop(key);changes.append(row)
        for key,value in [('extra','production'),('down','production'),('route','route-fast'),('recurrence','rec-both-plus')]:
            row=copy.deepcopy(good);row['choices'][key]=value;changes.append(row)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'selection.json'
            for row in changes:
                path.write_text(json.dumps(row))
                with patch.object(V,'selection',return_value=path),self.assertRaisesRegex(ValueError,'exactly'):
                    V.validate('down-tile16')

    def test_actual_unlimited_preexec_snapshot(self):
        self.assertEqual(L.check(),L.BASELINE)

    def test_finite_as_refused(self):
        original=resource.getrlimit
        def finite(kind):
            return (4*1024**3,4*1024**3) if kind==resource.RLIMIT_AS else original(kind)
        with patch.object(resource,'getrlimit',side_effect=finite),self.assertRaisesRegex(ValueError,'finite RLIMIT_AS'):
            L.check()

    def test_other_limit_drift_refused(self):
        changed=copy.deepcopy(L.BASELINE);changed[str(resource.RLIMIT_NOFILE)][0]-=1
        with patch.object(L,'snapshot',return_value=changed),self.assertRaisesRegex(ValueError,'changed before native exec'):
            L.check()


if __name__=='__main__': unittest.main()
