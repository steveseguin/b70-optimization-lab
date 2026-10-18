"""CPU mocks only; no subprocess, systemd, device, or CPU model runs."""
from pathlib import Path
import copy
import json
import unittest
from unittest.mock import patch
import orchestrate as o

def mock():
    rows={lane:[dict(choice=c,rate=(50 if c=='production' else 51 if c=='wide64' else 49),exact=True,exact_count=13)
                for c in o.ORDERS[lane]] for lane in 'AB'}
    return dict(boot_id='mock-boot',fault_counts=[2],lane_states=['inactive'],screens=dict(lanes=rows,errors={}))

class Tests(unittest.TestCase):
    def test_both_lane_winner(self):self.assertEqual(o.select(mock()['screens'])['experts'],'wide64')
    def test_one_lane_regression_keeps_production(self):
        data=mock()['screens'];next(r for r in data['lanes']['B'] if r['choice']=='wide64')['rate']=49
        self.assertEqual(o.select(data)['experts'],'production')
    def test_equality_is_not_faster(self):
        data=mock()['screens'];next(r for r in data['lanes']['B'] if r['choice']=='wide64')['rate']=50
        self.assertEqual(o.select(data)['experts'],'production')
    def test_any_inexact_screen_blocks_candidate(self):
        data=mock()['screens'];data['lanes']['A'][2]['exact']=False
        self.assertEqual(o.select(data)['experts'],'production')
    def test_missing_control_blocks_candidate(self):
        data=mock()['screens'];data['lanes']['B'].pop()
        self.assertEqual(o.select(data)['experts'],'production')
    def test_uses_both_controls(self):
        data=mock()['screens'];data['lanes']['B'][-1]['rate']=54
        self.assertEqual(o.select(data)['experts'],'production')
    def test_nan_rejected(self):
        data=mock()['screens'];data['lanes']['A'][1]['rate']=float('nan')
        self.assertEqual(o.select(data)['experts'],'production')
    def test_dry_orchestration_only_prepares_and_prints(self):
        lines=[]
        with patch.object(o.subprocess,'run',side_effect=AssertionError('external call')):
            b=o.Backend(o.ROOT,lines.append,mock());ready=o.orchestrate(b,lines.append)
        self.assertTrue(ready['ready']);self.assertFalse(ready['chain_launched'])
        self.assertEqual(b.launched,{})
        runs=[line for line in lines if 'RUN ' in line]
        self.assertEqual(len(runs),6)
        self.assertTrue(all('python3 -B' in line for line in runs))
        self.assertFalse(any('systemd-run' in line for line in runs))
        self.assertIn('--experts wide64',runs[0]);self.assertIn('--plan',runs[-1])
    def test_precheck_failure_stops_readiness(self):
        data=mock();data['fail_command']='storage_precheck.py'
        b=o.Backend(o.ROOT,lambda _:None,data)
        with self.assertRaises(ValueError):o.orchestrate(b,lambda _:None)
        self.assertEqual(b.launched,{})
    def test_fresh_fault_stops_before_reseal(self):
        data=mock();data['fault_counts']=[3]
        b=o.Backend(o.ROOT,lambda _:None,data)
        with self.assertRaisesRegex(ValueError,'fault count changed'):o.orchestrate(b,lambda _:None)
        self.assertEqual(b.launched,{})

if __name__=='__main__':unittest.main()

class ReadyTests(unittest.TestCase):
    def test_mock_and_pending_never_authorize_launch(self):
        from verify_ready import verify
        for row in (dict(ready=False),dict(ready=True,dry_run=True,chain_launched=False)):
            with self.assertRaisesRegex(ValueError,'real completed'):verify(row)
    def test_ready_binds_boot_selection_and_build(self):
        import tempfile
        from verify_ready import verify
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);packet=root/o.PACKET;packet.mkdir(parents=True)
            for name in ('build-receipt.json','selection.json'):(packet/name).write_text('{}')
            row=dict(ready=True,dry_run=False,chain_launched=False,boot_id='test',command=o.chain_command(),
                     build_receipt_sha256=o.digest(packet/'build-receipt.json'),
                     selection_sha256=o.digest(packet/'selection.json'),
                     orchestration_sources={'orchestrate.py':o.digest(o.HERE/'orchestrate.py')})
            verify(row,root,'test')
            with self.assertRaisesRegex(ValueError,'boot changed'):verify(row,root,'different')
            (packet/'selection.json').write_text('changed')
            with self.assertRaisesRegex(ValueError,'packet bytes changed'):verify(row,root,'test')
