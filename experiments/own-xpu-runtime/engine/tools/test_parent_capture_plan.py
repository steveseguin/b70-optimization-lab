"""Explicit opt-in and unchanged legacy wire admission; CPU only."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import persistent_rolling_driver as driver
import test_persistent_rolling as prior

class CapturePlanTests(unittest.TestCase):
    def test_opt_in_capability_first_owner_only_and_default_off(self):
        for policy in ('qualification','measured'):
            with tempfile.TemporaryDirectory() as tmp:
                path,config,inputs,baseline=prior.PersistentPlanTests().fixture(Path(tmp),policy)
                with patch.object(driver.base,'make_plan',side_effect=baseline):old=driver.make_plan(path)
                self.assertNotIn('capture_ready_overlap',old)
                self.assertTrue(all('--pipeline-ring-parent-capture-ack' not in s['argv'] for s in old['stages']))
                config['capture_ready_overlap']=True;path.write_text(json.dumps(config))
                with patch.object(driver.base,'make_plan',side_effect=baseline),self.assertRaisesRegex(ValueError,'capability'):
                    driver.make_plan(path)
                receipt=Path(config['build_receipt']);data=json.loads(receipt.read_text())
                data['sources']['pipeline/recursive_provider/capture_ready.hpp']='fixture';receipt.write_text(json.dumps(data))
                with patch.object(driver.base,'make_plan',side_effect=baseline):new=driver.make_plan(path)
                self.assertIs(new['capture_ready_overlap'],True)
                self.assertEqual([s['argv'].count('--pipeline-ring-parent-capture-ack') for s in new['stages']], [1,0,0,0])
                self.assertTrue(any(p.endswith('/rolling_provider/capture_ready.py') for p in new['pins']))

    def test_nonboolean_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,config,inputs,baseline=prior.PersistentPlanTests().fixture(Path(tmp))
            for value in (1,'true',None):
                config['capture_ready_overlap']=value;path.write_text(json.dumps(config))
                with patch.object(driver.base,'make_plan'),self.assertRaisesRegex(ValueError,'boolean'):
                    driver.make_plan(path)
