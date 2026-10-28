"""Mocked planning/lifecycle admission only; no device owners or model."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
import dedicated_provider_driver as D
import dedicated_provider_lifecycle as L
from test_dedicated_bulk_plan import BulkPlanTests

class PlanTests(unittest.TestCase):
    def fixture(self,root):
        config,c,plan,_=BulkPlanTests().fixture(root)
        c['boundaries']=[0,16,32,48]
        final=deepcopy(plan['stages'][-1]);final.update(id=2,bdf='0000:03:00.0')
        final['argv']=D.base.replace_options(final['argv'],{'--pipeline-stage':2})
        plan['stages'][-1]['final']=False;plan['stages'].append(final)
        config.write_text(json.dumps(c));return config,c,plan
    def test_defaults_identity_explicit_enable_and_pins(self):
        with TemporaryDirectory() as td:
            config,c,plan=self.fixture(Path(td))
            def make(values):
                config.write_text(json.dumps(values))
                with patch.object(D.base,'make_plan',side_effect=lambda _:deepcopy(plan)):return D.make_plan(config)
            serial=make(c);self.assertIs(serial['dedicated_prefill_pipeline'],False)
            enabled=make(dict(c,dedicated_prefill_pipeline=True))
            self.assertIs(enabled['dedicated_prefill_pipeline'],True)
            self.assertNotEqual(serial['request_sha256'],enabled['request_sha256'])
            self.assertEqual(L.execution_mode(serial),'dedicated-provider-sequential-bulk')
            self.assertEqual(L.execution_mode(enabled),'dedicated-provider-stage-pipeline-bulk')
            self.assertEqual(L.execution_mode({}),'dedicated-provider-per-token')
            self.assertTrue(any(p.endswith('/dedicated_prefill_pipeline.py') for p in enabled['pins']))
            self.assertNotIn('--prefill-rows',enabled['provider']['argv'])
            self.assertIn('--provider-prefill-rows',enabled['provider']['argv'])
            for s in enabled['stages']:self.assertIn('--prefill-rows',s['argv'])
    def test_invalid_types_per_token_and_two_targets_refused(self):
        with TemporaryDirectory() as td:
            config,c,plan=self.fixture(Path(td))
            for value in (0,1,None,'true'):
                config.write_text(json.dumps(dict(c,dedicated_prefill_pipeline=value)))
                with self.assertRaisesRegex(ValueError,'Boolean'):D.make_plan(config)
            config.write_text(json.dumps(dict(c,dedicated_prefill_pipeline=True,dedicated_bulk_prefill=False)))
            with self.assertRaisesRegex(ValueError,'authenticated bulk'):D.make_plan(config)
            config.write_text(json.dumps(dict(c,dedicated_prefill_pipeline=True)))
            plan['stages'].pop()
            with patch.object(D.base,'make_plan',side_effect=lambda _:deepcopy(plan)):
                with self.assertRaisesRegex(ValueError,'three target'):D.make_plan(config)
            for bad in ({'dedicated_prefill_pipeline':1},dict(dedicated_prefill_pipeline=True,dedicated_bulk_prefill=False),
                        dict(dedicated_prefill_pipeline=True,dedicated_bulk_prefill=True,stages=[1,2])):
                with self.assertRaisesRegex(ValueError,'lifecycle admission'):L.execute(bad,{},None)

if __name__=='__main__':unittest.main()
