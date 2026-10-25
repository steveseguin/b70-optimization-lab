"""Planner-only provenance budget admission; no processes/devices or model reads."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import persistent_rolling_driver as driver
import test_persistent_rolling as prior

base=driver.base


class TraceBudgetTests(unittest.TestCase):
    def fixture(self,folder):
        return prior.PersistentPlanTests().fixture(folder,'measured',512)

    def save(self,path,config,inputs):
        suite=Path(config['suite']);suite.write_text(json.dumps(inputs))
        config['suite_sha256']=base.digest(suite);path.write_text(json.dumps(config))

    def test_short_qualification_default_keeps4096_and_native_exactly_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,config,inputs,baseline=prior.PersistentPlanTests().fixture(Path(tmp))
            with patch.object(base,'make_plan',side_effect=baseline):plan=driver.make_plan(path)
            self.assertEqual(plan['ring_trace_limit'],4096)
            self.assertEqual(plan['ring_trace_required'],6*(4+32-1))
            self.assertFalse(plan['ring_trace_limit_explicit'])
            for stage in plan['stages']:
                self.assertEqual(stage['argv'].count('--pipeline-ring-trace-limit'),1)
                self.assertEqual(base.option(stage['argv'],'--pipeline-ring-trace-limit'),'4096')

    def test_largest_later_prompt_controls_bound_and_exact_boundary_is_admitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,config,inputs,baseline=self.fixture(Path(tmp))
            inputs['prompts'][1]['prompt_tokens']=[1]*3000;required=6*(3000+512-1)
            for value in (required-1,required,100000):
                config['ring_trace_limit']=value;self.save(path,config,inputs)
                with patch.object(base,'make_plan',side_effect=baseline):
                    if value<required:
                        with self.assertRaisesRegex(ValueError,'below worst-case'):driver.make_plan(path)
                    else:
                        plan=driver.make_plan(path)
                        self.assertEqual(plan['ring_trace_required'],required)
                        self.assertEqual(plan['ring_trace_budget'][1]['provider_commands'],3510)
                        self.assertTrue(all(base.option(s['argv'],'--pipeline-ring-trace-limit')==str(value)
                                            for s in plan['stages']))
            config.pop('ring_trace_limit');self.save(path,config,inputs)
            with patch.object(base,'make_plan',side_effect=baseline),self.assertRaisesRegex(ValueError,'explicit ring_trace_limit'):
                driver.make_plan(path)

    def test_twelve_requests_require_explicit_budget_even_when_short(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,config,inputs,baseline=self.fixture(Path(tmp))
            inputs['prompts']=[dict(id=str(i),prompt_tokens=[3,5,8,11],max_new=512) for i in range(12)]
            config.update(suite_prompt_count=12,dump_each=False)
            self.save(path,config,inputs)
            with patch.object(base,'make_plan',side_effect=baseline),self.assertRaisesRegex(ValueError,'explicit ring_trace_limit'):
                driver.make_plan(path)
            config['ring_trace_limit']=4096;self.save(path,config,inputs)
            with patch.object(base,'make_plan',side_effect=baseline):plan=driver.make_plan(path)
            self.assertEqual(len(plan['ring_trace_budget']),12)
            self.assertEqual(plan['ring_trace_required'],3090)

    def test_noninteger_limit_and_native_ceiling_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,config,inputs,baseline=self.fixture(Path(tmp))
            for value in (0,-1,True,1.0,'4096',100001):
                config['ring_trace_limit']=value;self.save(path,config,inputs)
                with self.subTest(value=value),patch.object(base,'make_plan',side_effect=baseline),self.assertRaisesRegex(ValueError,'integer bound'):
                    driver.make_plan(path)
            inputs['prompts'][1]['prompt_tokens']=[1]*17000;config['ring_trace_limit']=100000
            self.save(path,config,inputs)
            def large(p):
                plan=baseline(p);plan['context']=32768;return plan
            with patch.object(base,'make_plan',side_effect=large),self.assertRaisesRegex(ValueError,'exceeds native100000'):
                driver.make_plan(path)

    def test_duplicate_native_trace_flags_refused_and_single_inherited_value_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,config,inputs,baseline=self.fixture(Path(tmp));config['ring_trace_limit']=4096
            self.save(path,config,inputs)
            def inherited(p):
                plan=baseline(p)
                for stage in plan['stages']:stage['argv']+=['--pipeline-ring-trace-limit','128']
                return plan
            with patch.object(base,'make_plan',side_effect=inherited):plan=driver.make_plan(path)
            self.assertTrue(all(s['argv'].count('--pipeline-ring-trace-limit')==1 and
                base.option(s['argv'],'--pipeline-ring-trace-limit')=='4096' for s in plan['stages']))
            def duplicate(p):
                plan=inherited(p);plan['stages'][0]['argv']+=['--pipeline-ring-trace-limit','128'];return plan
            with patch.object(base,'make_plan',side_effect=duplicate),self.assertRaisesRegex(ValueError,'duplicate'):
                driver.make_plan(path)


if __name__=='__main__':unittest.main()
