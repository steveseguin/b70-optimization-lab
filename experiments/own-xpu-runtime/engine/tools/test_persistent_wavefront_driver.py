"""CLI planning contract only: no worker spawn, observer, model read or GPU."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import persistent_wavefront_driver as driver


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.receipt=self.root/'receipt.json'
        self.receipt.write_text(json.dumps(dict(schema='ownrt.engine.build.v1',binary='/fixture/engine',binary_sha256='b'*64,sources={'pipeline/request_reset.hpp':'a'*64})))
        self.suite=self.root/'suite.json'
        row=dict(id='first',prompt_tokens=[1,2],max_new=3,cached_tokens=0,expected_output_ids=[3,248046],expected_output_sha256=driver.suite_tools.token_sha([3,248046]))
        self.data=dict(schema='ownrt.persistent-cold-suite.v1',model_identity_sha256='auth',activation_dtype='F32',prompts=[row,dict(row,id='second')])
        self.suite.write_text(json.dumps(self.data))
        self.config=self.root/'config.json'
        self.settings=dict(persistent_requests=True,build_receipt=str(self.receipt),suite=str(self.suite),suite_sha256=driver.base.digest(self.suite),suite_prompt_count=2,dump_each=False)
        self.plan=dict(config=str(self.config),model_identity_sha256='auth',activation_dtype='F32',max_new=3,context=64,vocab=248320,eos=248044,eos_token_ids=[248044,248046],prompt_tokens=[1,2],
                       pins={str(self.receipt):driver.base.digest(self.receipt),'/fixture/engine':'b'*64},
                       stages=[dict(argv=['engine','--pipeline-wavefront','--pipeline-live-draft']) for _ in range(2)])
    def make(self):
        self.config.write_text(json.dumps(self.settings))
        with mock.patch.object(driver.live,'make_plan',return_value=copy.deepcopy(self.plan)):
            return driver.make_plan(self.config)
    def test_plan_pins_suite_helpers_and_reset_capability(self):
        result=self.make()
        self.assertEqual(result['schema'],'ownrt.persistent-wavefront-driver-plan.v1')
        self.assertFalse(result['dump_each'])
        self.assertEqual(result['pins'][str(self.suite)],self.settings['suite_sha256'])
        self.assertEqual(result['pins'][str(Path(driver.__file__).resolve())],driver.base.digest(driver.__file__))
        self.assertEqual(result['pins'][str(Path(driver.suite_tools.__file__).resolve())],driver.base.digest(driver.suite_tools.__file__))
        self.assertTrue(all('--pipeline-persistent-requests' in s['argv'] for s in result['stages']))
    def test_suite_digest_change_or_uncached_identity_refuses(self):
        self.suite.write_text('{}')
        with self.assertRaisesRegex(ValueError,'pinned cold suite'):self.make()
        self.data['prompts'][1]['cached_tokens']=1
        self.suite.write_text(json.dumps(self.data));self.settings['suite_sha256']=driver.base.digest(self.suite)
        with self.assertRaisesRegex(ValueError,'uncached'):self.make()
    def test_explicit_optin_and_first_prompt_identity(self):
        self.settings['persistent_requests']=False
        with self.assertRaisesRegex(ValueError,'explicit persistent'):self.make()
        self.settings['persistent_requests']=True;self.plan['prompt_tokens']=[9]
        with self.assertRaisesRegex(ValueError,'first cold request'):self.make()
    def test_twelve_prompt_measurement_cannot_enable_raw_dumps(self):
        self.data['prompts']=[dict(self.data['prompts'][0],id=f'prompt{i}') for i in range(12)]
        self.suite.write_text(json.dumps(self.data));self.settings.update(suite_sha256=driver.base.digest(self.suite),suite_prompt_count=12,dump_each=True)
        with self.assertRaisesRegex(ValueError,'limited to two'):self.make()
        self.settings['dump_each']=False
        self.assertEqual(self.make()['suite_prompt_count'],12)
    def test_run_rechecks_suite_hash_before_touching_workers(self):
        plan=self.make();self.suite.write_text('{}')
        with mock.patch.object(driver.suite_tools,'run_suite') as run:
            with self.assertRaisesRegex(ValueError,'changed before execution'):
                driver.run([],plan,None,self.root)
            run.assert_not_called()


if __name__=='__main__':unittest.main()
