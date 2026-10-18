"""The Python admission boundary agrees with the deliberately narrow native ABI."""
import copy
import itertools
import unittest
from pathlib import Path
from unittest.mock import patch
import bracket
from common import HERE, read

class NativeSwitchTests(unittest.TestCase):
    def setUp(self):
        self.base=read(HERE/'lineage/selection.json')

    def test_all_24_kernel_only_combinations(self):
        for route,recurrence,hc,attention in itertools.product(
            bracket.DOMAINS['route'],bracket.DOMAINS['recurrence'],
            bracket.DOMAINS['hc_gate'],('production','packet59')):
            with self.subTest(route=route,recurrence=recurrence,hc=hc,attention=attention):
                row=copy.deepcopy(self.base)
                row['choices'].update(route=route,recurrence=recurrence,hc_gate=hc)
                row['draft']['qsa_attention']=attention
                self.assertTrue(bracket.compatible([self.base,row,self.base]))

    def test_every_other_choice_is_fixed(self):
        for key in self.base['choices']:
            if key in bracket.DOMAINS:continue
            row=copy.deepcopy(self.base);row['choices'][key]='other'
            with self.subTest(key=key),self.assertRaises(ValueError):
                bracket.compatible([self.base,row])
        for key in self.base['draft']:
            if key=='qsa_attention':continue
            row=copy.deepcopy(self.base);row['draft'][key]='other'
            with self.subTest(key=key),self.assertRaises(ValueError):
                bracket.compatible([self.base,row])

    def test_invalid_initial_selection_also_refused(self):
        for key in bracket.DOMAINS:
            row=copy.deepcopy(self.base);row['choices'][key]='production-invalid'
            with self.subTest(key=key),self.assertRaises(ValueError):
                bracket.compatible([row,row])

    def test_layout_and_constructor_fields_refused(self):
        for section,key,value in (
            ('choices','experts','exp-halfcache'),('choices','head','head-transpose'),
            ('choices','hc_gate','hc-weightcache'),('choices','hc_norm','consumer'),
            ('choices','host_retire','reply-first'),('choices','miss','banks-batch'),
            ('draft','head_format','q4-g32'),('draft','head_prefix','coverage985')):
            row=copy.deepcopy(self.base);row[section][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):bracket.compatible([self.base,row])

    def test_proposed_smoke_and_two_full_brackets(self):
        smoke=bracket.load_config(HERE/'configs/smoke.json')
        self.assertEqual([v['choice'] for v in smoke['views']],['control','candidate','control'])
        for name in ('bracket','attention'):
            config=bracket.load_config(HERE/'configs'/(name+'.json'))
            self.assertEqual(len(config['views']),5)
            for view in config['views']:
                self.assertEqual(read(view['selection'])['choices']['experts'],'wide64')

    def test_copy_has_no_parent_orchestration_dependency(self):
        for name in ('build','full-shape','reset-bytes','protocol'):
            path=HERE/'evidence'/(name+'.json')
            if not path.exists():continue
            for source in read(path).get('sources',{}):
                self.assertNotIn('/ops/',source)
                self.assertFalse(source.endswith('/packet97-record-bundle/selection.json'))

    def test_smoke_lane_a_refused_before_worker(self):
        import bracket_job
        with patch('cpu_seal.verify'),patch.object(bracket_job.screen,'main') as launch:
            with self.assertRaisesRegex(ValueError,'lane B only'):
                bracket_job.main(['--kind','smoke','--lane','A','--output','/unused','--plan'])
            launch.assert_not_called()

    def test_plan_needs_no_completed_device_smoke(self):
        import bracket_job
        with patch('cpu_seal.verify'),patch('compare.load',side_effect=AssertionError('device receipt read')),patch.object(bracket_job.screen,'main',return_value=0) as launch:
            self.assertEqual(bracket_job.main(['--kind','attention','--lane','A','--output','/unused','--plan']),0)
            self.assertIn('--plan',launch.call_args.args[0])

    def test_missing_or_incomplete_smoke_never_launches_full_job(self):
        import bracket_job
        for result in (None,dict(kind='smoke',timing_equal_within_control_drift=False)):
            with self.subTest(result=result),patch('cpu_seal.verify'),patch.object(bracket_job,'read',return_value={}),patch.object(bracket_job.screen,'main') as launch:
                if result is None:
                    with patch('compare.load',side_effect=FileNotFoundError('smoke missing')):
                        with self.assertRaises(FileNotFoundError):bracket_job.main(['--kind','bracket','--lane','A','--output','/unused'])
                else:
                    with patch('compare.load',return_value=result):
                        with self.assertRaisesRegex(ValueError,'must pass'):bracket_job.main(['--kind','bracket','--lane','A','--output','/unused'])
                launch.assert_not_called()

if __name__=='__main__':unittest.main()
