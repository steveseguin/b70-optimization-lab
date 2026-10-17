"""CPU-only paired request/reset and attribution selection admission."""
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import common as C
import screen
from tp2_worker import request_schedule, reset_observation


class PairedAttribution(unittest.TestCase):
    def test_order_full_control_then_full_observation(self):
        entries=[dict(prompt_id=p) for p in C.D.CHECK.PROMPT_IDS]
        requests=request_schedule(entries,True)
        self.assertEqual(len(requests),25)
        self.assertEqual(requests[0][0],'incident64')
        self.assertTrue(all(r[3]=='control' for r in requests[:13]))
        self.assertTrue(all(r[3]=='attribution' for r in requests[13:]))
        self.assertEqual([r[1] for r in requests[1:13]],entries)
        self.assertEqual([r[1] for r in requests[13:]],entries)
        self.assertTrue(all(r[2]==128 for r in requests[1:]))

    def test_reset_flag_only_and_restore_on_error(self):
        calls=[]
        def call(*args,**kwargs):calls.append((args,kwargs))
        transport=SimpleNamespace(call=call)
        def reset(t,d):
            t.call(0,11);t.call(1,11)
        suite=SimpleNamespace(RESET=11,reset=reset)
        for arm,flag in [('control',1),('attribution',0)]:
            reset_observation(suite,transport,Path('/unused'),arm)
            self.assertIs(transport.call,call)
            self.assertEqual(calls[-2:],[((0,11),{'token':flag}),((1,11),{'token':flag})])
        suite.reset=lambda t,d:t.call(0,1)
        with self.assertRaises(ValueError):reset_observation(suite,transport,Path('/unused'),'control')
        self.assertIs(transport.call,call)

    def test_lane_b_plan_and_tamper_before_launch(self):
        p=C.HERE.parents[1]/'selections/1-production-control'
        if not (p/'screen-seal.json').exists():self.skipTest('initial seal not yet produced')
        args=['--lane','B','--lineage',str(p),'--seal',str(p/'screen-seal.json'),
              '--placement','1','--timing','attribution','--output',str(C.HERE/'evidence/cpu-attr-plan'),'--plan']
        with (patch.object(screen.subprocess,'Popen',side_effect=AssertionError('device launch')),
              patch.object(C.S,'journal',side_effect=AssertionError('journal read')),
              patch('sys.stdout',new=io.StringIO()) as output):
            self.assertEqual(screen.main(args),0)
            row=json.loads(output.getvalue())
        self.assertEqual(row['physical_cards'],[2,3])
        self.assertEqual(row['identity']['placement']['target_layers'],[24,24])
        self.assertEqual(row['attribution_plan']['requests'],25)
        self.assertFalse(row['device_executed'])
        self.assertFalse((C.HERE/'evidence/cpu-attr-plan').exists())
        original=C.read
        def tamper(path):
            value=original(path)
            if Path(path).name=='attribution-plan.json':value['control_reset_token']=0
            return value
        with patch.object(C,'read',side_effect=tamper):
            with self.assertRaisesRegex(ValueError,'attribution plan changed'):screen.main(args)

if __name__=='__main__':unittest.main()
