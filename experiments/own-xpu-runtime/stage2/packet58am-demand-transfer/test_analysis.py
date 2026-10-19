import copy,json,unittest,tempfile
from pathlib import Path
from analyze import request,stream,demand_stream,close_ms,replay
from prepare import P,AH
class Evidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        f=AH/'evidence/card0-58ah-b/WS128/run/run/incident-retrospective'
        cls.r=json.loads((f/'result.json').read_text());cls.g=stream(f/'timings.jsonl');cls.p=stream(f/'prefill-timings.jsonl')
    def test_real_cold(self):self.assertTrue(request(self.r,self.g,self.p))
    def test_failures(self):
        cases=[]
        for field,value in [('arithmetic','wrong'),('cached_tokens',1),('gpu_count',2)]:
            r=copy.deepcopy(self.r);r[field]=value;cases.append((r,self.g,self.p))
        g=copy.deepcopy(self.g);g[2]['token_id']+=1;cases.append((self.r,g,self.p))
        g=copy.deepcopy(self.g);g[2]=g[1];cases.append((self.r,g,self.p))
        cases.extend([(self.r,self.g[:-1],self.p),(self.r,self.g,[]),(self.r,[],self.p)])
        for case in cases:
            with self.subTest(case=len(case[1])):
                with self.assertRaises(ValueError):request(*case)
    def test_slow_valid_not_deadline(self):
        g=copy.deepcopy(self.g);g[0]['wall_ms']=10000000
        self.assertTrue(request(self.r,g,self.p,offline=False))
        with self.assertRaises(ValueError):request(self.r,g,self.p,offline=True)
    def test_relative_rounding(self):
        self.assertTrue(close_ms(23457.6,23457.612));self.assertFalse(close_ms(1,2))
    def test_inrun_defers_consistency(self):
        g=copy.deepcopy(self.g);g[1]=g[0]
        r=copy.deepcopy(self.r);r['timing_rows'][1]=r['timing_rows'][0]
        self.assertTrue(request(r,g,self.p,offline=False))
        with self.assertRaises(ValueError):request(r,g,self.p)
    def test_first_completed_real_parent(self):
        from check_streams import check
        proposal=json.loads((P/'proposals/v5.json').read_text())
        folder=AH/'evidence/card0-58ah-b/WS128/run/run/incident-retrospective'
        self.assertTrue(check(proposal,folder)['passed'])
    def test_truncated_and_missing_stream(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'stream.jsonl';path.write_text('{"a":1}')
            with self.assertRaises(ValueError):stream(path)
            path.write_text('')
            with self.assertRaises(ValueError):stream(path)
            with self.assertRaises(FileNotFoundError):stream(Path(d)/'missing')
    def test_synthetic_new_schema_separate(self):
        kinds=['router','descriptor','descriptor-D2H','resident-gate','packed-H2D','packed-H2D','packed-H2D','stage-map-H2D','missing-gate','resident-down','missing-down']
        events=[dict(kind=k,id=i+1,start_ns=10*i+1,end_ns=10*i+2) for i,k in enumerate(kinds)]
        row=dict(schema='packet58am.demand.v1',identity='synthetic-not-device',position=0,layer=0,slot_ids=list(range(10)),staged_bytes=1971200,staged_entries=1,copy_engine='copy-only-BCS',descriptor_producer=2,descriptor_readback=3,missing_consumer=9,all_consumers_completed=True,snapshot_disposition='retained-until-policy',clock_domain='same-device-sycl-profiling',events=events)
        rows=[dict(row,layer=i) for i in range(48)]
        self.assertTrue(demand_stream(rows,'synthetic-not-device',1))
        fallback=copy.deepcopy(rows)
        fallback[2].update(layout_supported=False,staged_bytes=0,staged_entries=0,missing_consumer=0)
        fallback[2]['events']=[dict(e,kind={'resident-gate':'original-mixed-gate','resident-down':'original-mixed-down'}.get(e['kind'],e['kind'])) for e in events if e['kind'] in ('router','descriptor','descriptor-D2H','resident-gate','resident-down')]
        self.assertTrue(demand_stream(fallback,'synthetic-not-device',1))
        fallback[2]['staged_entries']=1;fallback[2]['staged_bytes']=1971200
        with self.assertRaises(ValueError):demand_stream(fallback,'synthetic-not-device',1)
        for field,value in [('staged_bytes',1),('identity','edited'),('missing_consumer',1),('slot_ids',[0]*10),('copy_engine','CCS')]:
            changed=copy.deepcopy(rows);changed[0][field]=value
            with self.assertRaises(ValueError):demand_stream(changed,'synthetic-not-device',1)
        with self.assertRaises(ValueError):demand_stream(rows[:-1],'synthetic-not-device',1)
        changed=copy.deepcopy(rows);changed[1]=changed[0]
        with self.assertRaises(ValueError):demand_stream(changed,'synthetic-not-device',1)
        changed=copy.deepcopy(rows);changed[0]['events'][1]['id']=changed[0]['events'][0]['id']
        changed[0]['staged_bytes']=1
        self.assertTrue(demand_stream(changed,'synthetic-not-device',1,offline=False))
        with self.assertRaises(ValueError):demand_stream(changed,'synthetic-not-device',1)
if __name__=='__main__':unittest.main()
