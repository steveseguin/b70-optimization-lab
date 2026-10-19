"""Full-composition identity refusals, independent of the performance gate."""
import unittest,copy
from unittest.mock import patch
import composition as C
import packet58_submission as S
import test_submission as T
class CompositionTests(unittest.TestCase):
    def test_each_dimension_required_exactly_once(self):
        C.check(C.ARGV)
        for flag,value in C.FLAGS.items():
            i=C.ARGV.index(flag)
            for bad in (C.ARGV[:i]+C.ARGV[i+2:], C.ARGV+[flag,value], C.ARGV[:i+1]+['production']+C.ARGV[i+2:], C.ARGV[:i]+[flag]):
                with self.subTest(flag=flag,bad=bad),self.assertRaises(ValueError):C.check(bad)
    def test_no_bracket_record(self):
        with self.assertRaises(ValueError):C.check(C.ARGV+['--bracket-inputs','fixture'])
    def test_submission_refuses_each_downgraded_dimension(self):
        original,seal=T.synthetic()
        for flag in C.FLAGS:
            e=copy.deepcopy(original);key='WS128/run/receipt.json'
            def change(row):row['command'][row['command'].index(flag)+1]='production'
            digest=T.changed(e,key,change)
            T.changed(e,'WS128/window.json',lambda r:r['native_files'].update({'run/receipt.json':digest}))
            with self.subTest(flag=flag),patch.object(S,'SEAL_SHA',seal),self.assertRaisesRegex(ValueError,'composition'):
                S.derive(e)

class CensusTests(unittest.TestCase):
    def test_exact_table_and_refusals(self):
        row=dict(label='card0:exact-half-decode-table',bytes=262144,memory='device',category='weights',live=True)
        self.assertEqual(C.check_census([dict(allocations=[row])]),262144)
        for rows in ([],[row,row],[dict(row,bytes=262143)],[dict(row,memory='host-pinned')],[dict(row,live=False)]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):C.check_census([dict(allocations=rows)])

    def test_submission_replays_bound_census(self):
        e,seal=T.synthetic();key='WS128/run/run/census.json'
        row=e.read(key);row[0]['allocations'][0]['bytes']=262143
        digest=T.put(e,key,row)
        T.changed(e,'WS128/window.json',lambda r:r['native_files'].update({'run/run/census.json':digest}))
        with patch.object(S,'SEAL_SHA',seal),self.assertRaisesRegex(ValueError,'half-decode-table'):
            S.derive(e)
