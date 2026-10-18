"""The Python admission boundary agrees with the deliberately narrow native ABI."""
import copy
import itertools
import unittest
from pathlib import Path
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

if __name__=='__main__':unittest.main()
