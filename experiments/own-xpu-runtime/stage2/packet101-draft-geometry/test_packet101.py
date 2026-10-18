"""Composition and screening regression checks; no device or live queue calls."""
import copy,json,unittest
from bundle_selection import aliases,views,selection,base,name
from screen_jobs import ORDER,choose
from compare import compare
class SelectionTests(unittest.TestCase):
    def test_all_parent_dimensions_preserved(self):
        self.assertEqual(len(views()),256)
        for label,v in views().items():
            with self.subTest(label=label):
                expected=base.selection(v[:10]);actual=selection(v)
                self.assertEqual(actual['choices'],expected['choices'])
                old=expected['draft'].copy();old['qsa_attention']=actual['draft']['qsa_attention']
                self.assertEqual(actual['draft'],old)
                self.assertEqual(actual['draft']['head_format'],'production')
                self.assertEqual(actual['draft']['head_prefix'],'production')
    def test_hc_aliases_are_identical(self):
        a=aliases()
        self.assertEqual(selection(a['control']),selection(a['draft_hc']))
        self.assertEqual(selection(a['draft_attention']),selection(a['combined']))
        self.assertEqual(ORDER,('control','draft_attention','control'))
    def test_unknown_choices_refused(self):
        v=aliases()['control']
        for wrong in ((*v[:10],'other','packet59'),(*v[:11],'production'),(*v[:8],'wide64',*v[9:])):
            with self.subTest(wrong=wrong),self.assertRaises((AssertionError,ValueError)):name(*wrong)
class BracketTests(unittest.TestCase):
    def rows(self):
        return [dict(index=i,choice=c,all_13_exact=True,exact=True,exact_count=13,
                boot_id='same',lane='B',started_utc_ns=i*10+1,finished_utc_ns=i*10+2,
                rate=r,acceptance=.75,acceptance_counts=[{'prompt_id':'a','hits':3,'guesses':4}])
                for i,(c,r) in enumerate(zip(ORDER,(55.,55.11,55.1)))]
    def test_small_win_qualifies_on_first_lane(self):
        rows=self.rows();result=compare(rows)
        self.assertTrue(result['composition_qualified']);self.assertFalse(result['record_ready'])
        self.assertEqual(result['record_lane'],'A');self.assertFalse(result['submission_eligible'])
        self.assertEqual(choose(rows),rows[1])
    def test_mean_win_is_not_enough(self):
        rows=self.rows();rows[1]['rate']=55.08
        self.assertFalse(compare(rows)['composition_qualified'])
        with self.assertRaises(AssertionError):choose(rows)
    def test_equal_stronger_control_is_not_win(self):
        rows=self.rows();rows[1]['rate']=55.1
        with self.assertRaises(AssertionError):choose(rows)
    def test_invalid_brackets_fail_closed(self):
        mutations=[('all_13_exact',False),('exact',False),('exact_count',12),('boot_id','other'),
                   ('lane','A'),('started_utc_ns',0),('rate',float('nan')),
                   ('choice','combined'),('acceptance_counts',[{'prompt_id':'a','hits':6,'guesses':8}])]
        for key,value in mutations:
            rows=self.rows();rows[1][key]=value
            with self.subTest(key=key),self.assertRaises((AssertionError,RuntimeError,ValueError)):compare(rows)
    def test_incomplete_bracket_refused(self):
        with self.assertRaises((AssertionError,RuntimeError,ValueError)):compare(self.rows()[:2])
if __name__=='__main__':unittest.main()
