"""Invented timing protocol tests. These are never benchmark measurements."""
import unittest
from micro_gate import analyze,CANDIDATES,SHAPES
class Gate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows=[]
        for name in CANDIDATES:
            nr,k,count,experts,wg,_=SHAPES[name]
            shape=dict(rows=nr,columns=k,count=count,experts=experts)
            for route in range(384):
                rows.append(dict(kind='correctness',view=name,route=route,fp32_exact=True,bf16_exact=True,status_exact=True,**shape))
                for rep in range(40):
                    for pos in range(2):
                        changed=bool(pos^(rep&1))
                        rows.append(dict(kind='sample',pair=name,view=name if changed else 'production',route=route,repeat=rep,position=pos,event_ns=80 if changed else 100,sg=32,wg=wg,scrub_bytes=536870912,diagnostic_only=True,**shape))
        rows.append(dict(kind='summary',passed=True,drained=True,diagnostic_only=True,candidate_count=2,route_count=384));cls.rows=rows
    def reject(self,index,key,value):
        row=self.rows[index];old=row[key];row[key]=value
        try:
            with self.assertRaises(ValueError):analyze(self.rows,384)
        finally:row[key]=old
    def test_complete(self):self.assertEqual(analyze(self.rows,384)['qualified'],list(CANDIDATES))
    def test_missing_route(self):
        with self.assertRaises(ValueError):analyze(self.rows[:-81]+self.rows[-1:],384)
    def test_duplicate_route(self):self.reject(81,'route',0)
    def test_wrong_order(self):self.reject(1,'view',CANDIDATES[0])
    def test_nonfinite(self):self.reject(1,'event_ns',float('nan'))
    def test_zero_duration(self):self.reject(1,'event_ns',0)
    def test_wrong_shape(self):self.reject(1,'columns',640)
    def test_wrong_geometry(self):self.reject(1,'wg',64)
    def test_no_scrub(self):self.reject(1,'scrub_bytes',0)
    def test_inexact(self):self.reject(0,'fp32_exact',False)
    def test_no_drain(self):self.reject(-1,'drained',False)
    def change_first_stratum(self,values):
        indices=[i for i,r in enumerate(self.rows[:81]) if r.get('kind')=='sample' and r.get('view')==CANDIDATES[0]]
        for i in indices:self.rows[i]['event_ns']=values[self.rows[i]['repeat']%2]
        try:self.assertNotIn(CANDIDATES[0],analyze(self.rows,384)['qualified'])
        finally:
            for i in indices:self.rows[i]['event_ns']=80
    def test_one_stratum_blocks(self):self.change_first_stratum([90,90])
    def test_one_order_blocks(self):self.change_first_stratum([50,90])
if __name__=='__main__':unittest.main()
