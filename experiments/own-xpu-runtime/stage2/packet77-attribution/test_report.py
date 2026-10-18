import ast
import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import report
import summarize
from byte_formulas import accounting

P=Path(__file__).resolve().parent


class ReportTests(unittest.TestCase):
    def test_zero_transfer_only(self):
        from test_attribution import event
        e=event('blk.23',0,9,'attention')
        e.update(end_ns=e['start_ns'],device_ms=0)
        with self.assertRaisesRegex(ValueError,'timestamps'):
            summarize.validate_event(e,0)
        e.update(label='transfer.upload',layer_boundary='',**{'class':'transfers'})
        summarize.validate_event(e,0)
        e['end_ns']-=1
        with self.assertRaises(ValueError):
            summarize.validate_event(e,0)

    def test_formulas_are_packet72_and_actual_tensor_types(self):
        source=(P.parent/'packet72-occupancy/bandwidth.py').read_text()
        main=next(n for n in ast.parse(source).body if getattr(n,'name',None)=='main')
        local=ast.parse((P/'byte_formulas.py').read_text())
        factory=next(n for n in local.body if getattr(n,'name',None)=='accounting')
        for name in ('weights','account'):
            a=next(n for n in main.body if getattr(n,'name',None)==name)
            b=next(n for n in factory.body if getattr(n,'name',None)==name)
            self.assertEqual(ast.dump(a),ast.dump(b))
        tensors=json.loads((P.parent/'packet72-occupancy/header-census.json').read_text())['tensors']
        account=accounting(tensors)
        q=account(22,'gdn.qkv',109)
        self.assertEqual(q['runtime_weight_read_bytes'],32768000)
        self.assertGreater(q['runtime_weight_read_bytes'],q['gguf_weight_bytes'])
        for layer in (22,23,24,27):
            for site in ('expsgate','expsdown','route','hc.a.gate','hc.f.gate'):
                self.assertGreater(account(layer,site,109)['read_bytes'],0)

    def test_sum_multistage_before_median_and_occurrence_ranking(self):
        tensors=json.loads((P.parent/'packet72-occupancy/header-census.json').read_text())['tensors']
        events=[]
        for layer,rank in ((22,0),(23,0),(24,1),(27,1)):
            for site,us in (('route',2),('route',3),('ffn.combine',7)):
                events.append(dict(rank=rank,fixture=9,position=109,speculative=False,
                    label=f'blk.{layer}.{site}',start_ns=1000,end_ns=1000+us*1000))
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'attribution/prompt').mkdir(parents=True)
            (root/'attribution/prompt/receipt.json').write_text('{}')
            with patch.object(report,'read_events',return_value=events):
                rows,ranked,_=report.site_rows(root,tensors)
        route=[r for r in ranked if r['site']=='route']
        self.assertEqual(len(route),2)
        self.assertTrue(all(r['estimated_us_per_half']==5*24 for r in route))
        self.assertTrue(all(r['occurrences_per_half']==24 for r in route))
        self.assertTrue(all(r['events_per_call']==[2] for r in rows if r['site']=='route'))


class IntegrationTests(unittest.TestCase):
    def test_closed_environment_imports_and_real_admission(self):
        code='''import sys
sys.path.insert(0,sys.argv[1])
import worker,run_screen
from lane_admission import admission_scope,Reservation
from placement import admission_gate
assert admission_scope('B','screen')=='lane-B'
assert admission_scope('A','screen')=='lane-A'
import tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as d:
    assert Reservation('B',window='screen',root=Path(d)).scope=='lane-B'
run_screen.verify_dependencies()
print('closed worker imports, shared seal, real lane B screen predicate PASS')
'''
        subprocess.run(['/usr/bin/python3','-B','-c',code,str(P)],
            env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},stdin=subprocess.DEVNULL,
            check=True,timeout=120)

    def test_workload_hook_cannot_change_lane_or_placement(self):
        import run_screen as r
        args=SimpleNamespace(lane='B',placement='1',timing='attribution',lineage=r.VIEW,
                             pair_dir=None,output=r.OUTPUT)
        command=r.worker_command(args,{},None)
        self.assertEqual(command[2],str(P/'worker.py'))
        self.assertEqual(command[-1],'3600')
        for field,bad in (('lane','A'),('placement','1-split23'),('timing','token'),('lineage',P)):
            changed=SimpleNamespace(**vars(args));setattr(changed,field,bad)
            with self.assertRaises(ValueError):r.worker_command(changed,{},None)


if __name__=='__main__':unittest.main()
