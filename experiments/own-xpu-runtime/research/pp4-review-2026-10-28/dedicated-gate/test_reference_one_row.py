import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
import reference_one_row as R
from test_colocated_control import adapter

class ReferenceTests(unittest.TestCase):
    def test_actual_native_mode_count_no_overlap_and_captures(self):
        a=adapter()
        with TemporaryDirectory() as tmp:
            p=Path(tmp);calls=[];stages=[]
            rows=[dict(rank=r,op=op,position=n,speculative=False) for n in range(244) for r in (0,1) for op in (a.BASE.HALF,a.BASE.ACCEPT)]
            raw=dict(tokens=[6343],rank_trace=rows,work_start=1,work_end=2,stats=dict(hits=0,guesses=0),decode_intervals=0,decode_wall_ms=0)
            (p/'native-result.json').write_text(json.dumps(raw))
            for rank,(begin,end) in enumerate(((0,23),(23,48))):
                native=p/f'rank{rank}';(native/'step1').mkdir(parents=True)
                for n in range(begin,end):(native/'step1'/f'layer-{n:02d}.bf16').write_bytes(bytes(40960))
                stages.append(dict(native_output=str(native),begin=begin,end=end))
            b=NS(shared_path=p/'shared.bin',trace=[],a=NS(draft_fault='none'),device=True,start=lambda *x:calls.append(('start',*x)),wait=lambda *x:calls.append(('wait',*x)))
            result=R.request(a,b,dict(prompt_tokens=list(range(244)),stages=stages),0)
            self.assertEqual((p/'native-request.txt').read_text(),'0 1 0 0 244 0 0 '+' '.join(map(str,range(244)))+'\n')
            self.assertEqual(calls,[('start',1,10),('start',0,10),('wait',0),('wait',1)])
            self.assertEqual(len(result['layer_captures']),48);self.assertFalse(result['matches_saved_cpu_argmax'])
            # A BF16-sized capture must fail before any qualification claim.
            (p/'rank0/step1/layer-00.bf16').write_bytes(bytes(20480))
            with self.assertRaisesRegex(ValueError,'extent40960'):R.request(a,b,dict(prompt_tokens=list(range(244)),stages=stages),0)
    def test_plan_actual4096_no_runtime_oracle_and_fresh_output(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);cfg=p/'config.json';cfg.write_text(json.dumps(dict(output=str(p/'output'),build_receipt='/dev/shm/engine-build-dedicated-layout-20261028-r1/build-receipt.json')))
            plan=R.make_plan(cfg)
            self.assertEqual((plan['context'],len(plan['prompt_tokens']),plan['max_new']),(4096,244,1))
            for stage in plan['stages']:
                self.assertEqual(R.BASE.option(stage['argv'],'--context'),'4096')
                self.assertEqual(R.BASE.option(stage['argv'],'--retain-steps'),'1')
                self.assertFalse(any(x.startswith('--oracle') or x.startswith('--draft') for x in stage['argv']))
            (p/'output').mkdir()
            with self.assertRaisesRegex(ValueError,'fresh'):R.make_plan(cfg)
if __name__=='__main__':unittest.main()
