import copy
import unittest
from finalize_ring_proof import audit_native


class TraceTests(unittest.TestCase):
    def fixture(self):
        created={1:dict(parent=0,position=0,token=4),2:dict(parent=1,position=1,token=9),
                 3:dict(parent=2,position=2,token=8),4:dict(parent=1,position=1,token=5)}
        rows=[]
        for seq,(op,rid,physical,committed,pending,tentative,discarded) in enumerate([
            (24,1,1,0,1,False,[]),(25,1,1,1,0,False,[]),(24,2,2,1,1,True,[]),
            (24,3,3,1,2,True,[]),(26,2,1,1,0,True,[2,3]),(24,4,2,1,1,False,[]),(25,4,2,2,0,False,[])],1):
            r=created[rid];rows.append(dict(op=op,sequence=seq,row_id=rid,parent_id=r['parent'],position=r['position'],token=r['token'],
                physical=physical,committed=committed,pending=pending,tentative=tentative,discarded=discarded))
        sent=[dict(op=r['op'],sequence=r['sequence'],row=r['row_id'],position=r['position']) for r in rows]
        att=dict(rows=4,tentative_rows=2,commits=2,abort_count=1,discarded_rows=2,accepted_tentative_rows=0,
                 max_pending=2,trace_records=7,trace_omitted=0)
        return rows,sent,created,[4,5],att,False

    def test_two_row_restore_and_correction_replay(self):
        result=audit_native(*self.fixture())
        self.assertTrue(result['passed']);self.assertEqual(result['suffix_restores'][0]['row_ids'],[2,3])

    def test_wrong_depth_stale_parent_or_rewind_refused(self):
        for index,field,value in [(4,'discarded',[3]),(5,'parent_id',3),(1,'physical',0),(4,'tentative',False),(3,'pending',3)]:
            args=list(self.fixture());args[0]=copy.deepcopy(args[0]);args[0][index][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):audit_native(*args)

    def test_incomplete_trace_and_final_stage_speculation_refused(self):
        args=list(self.fixture());args[4]['trace_omitted']=1
        with self.assertRaises(ValueError):audit_native(*args)
        args=list(self.fixture());args[-1]=True
        with self.assertRaises(ValueError):audit_native(*args)


if __name__=='__main__':unittest.main()
