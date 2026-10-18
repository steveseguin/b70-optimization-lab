"""CPU synthetic winner/loser, forged scope, and prelaunch refusal checks."""
import copy
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import queue_runner as Q
import verify_ready as R


def rows(rates=(25,25.125,25)):
    return [dict(view=view, miss_path='zero-copy', **{R.METRIC:dict(median=rate)},
                 requests=[dict(prompt_id=f'p{i}',prompt_token_sha256=f'h{i}',tokens=list(range(128)),
                                passed=True,exact_oracle=True) for i in range(12)])
            for view,rate in zip(('production','down-tile16','production'),rates)]


class ReadyTests(unittest.TestCase):
    def test_synthetic_exact_threshold_winner(self):
        self.assertTrue(R.evaluate(rows())['passed'])

    def test_synthetic_loser_each_control(self):
        for values in ((25,25.124,25),(25,25.2,25.1),(25.1,25.2,25),(25,24.9,25)):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError,'BOTH controls'):
                R.evaluate(rows(values))

    def test_missing_arm(self):
        with self.assertRaisesRegex(ValueError,'three screen'):
            R.evaluate(rows()[:2])

    def test_all_twelve_exact_and_same_tokens(self):
        for field,value in (('passed',False),('exact_oracle',False),('tokens',[1]*128),('prompt_id','p1')):
            data=rows();data[1]['requests'][0][field]=value
            with self.subTest(field=field), self.assertRaises(ValueError): R.evaluate(data)
        data=rows();data[1]['requests'].pop()
        with self.assertRaises(ValueError): R.evaluate(data)

    def test_view_miss_and_invalid_rates(self):
        for field,value in (('view','production'),('miss_path','streamed')):
            data=rows();data[1][field]=value
            with self.assertRaises(ValueError): R.evaluate(data)
        for value in (True,0,-1,float('inf'),float('nan')):
            with self.assertRaises(ValueError): R.evaluate(rows((25,value,25)))

    def test_existing_screen_drift_and_record_guard(self):
        for rates in ((24,26,25),(23,24,23)):
            with self.assertRaises(ValueError): R.evaluate(rows(rates))

    def test_no_launch_when_readiness_refuses_even_with_ready_json(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root=Path(tmp);(root/'evidence').mkdir();(root/'ready.json').write_text('{"ready":true}')
            stack.enter_context(patch.object(Q,'P',root))
            for obj,name,ret in ((Q.W,'build_gate',{}),(Q.W,'user_unit_gate',None),(Q.W,'closed_environment',{}),
                                 (Q.os,'getpriority',0),(Q.os,'sched_getaffinity',{0,1,2,3,16,17,18,19})):
                stack.enter_context(patch.object(obj,name,return_value=ret))
            stack.enter_context(patch.object(R,'verify',side_effect=ValueError('missing screen receipt')))
            spawn=stack.enter_context(patch.object(Q.subprocess,'Popen',side_effect=AssertionError('must not launch')))
            with self.assertRaisesRegex(ValueError,'missing screen'):
                Q.main(['--output-root',str(root/'evidence/card0-58p-a'),'--fault-review','/unused',
                        '--view','down-tile16','--authorized-device-window'])
            spawn.assert_not_called()
            self.assertFalse((root/'evidence/card0-58p-a').exists())

    def test_command_is_plain_systemd_handoff(self):
        command=R.chain_command()
        for text in ('systemd-run --user','--property=Restart=no','--property=SendSIGKILL=no',
                     '--property=Nice=0','--view down-tile16','--fault-review','card0-58p-a','< /dev/null'):
            self.assertIn(text,command)
        self.assertNotIn('--faults-reviewed-through',command)


if __name__=='__main__': unittest.main()
