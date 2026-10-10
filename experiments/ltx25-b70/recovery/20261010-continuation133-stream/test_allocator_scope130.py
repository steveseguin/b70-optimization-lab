"""Packet132 launch, receipt, qualification and namespace boundaries; no devices."""
import ast
import copy
import os
from pathlib import Path
import unittest

import stream_contract as contract
import stream_receipts
import test_gate_receipts as fixtures

HERE = Path(__file__).resolve().parent

class AllocatorScope130(unittest.TestCase):
    def options(self):
        return dict(aux_residency='legacy', display_device='xpu:2', display_schedule='eager-display',
                    display_worker='parallel', snapshot_schedule='full', snapshot_mode='fingerprint',
                    anchor_read_ahead=0)

    def check(self, mode='before-admission', frames=169, placement='two-way20-28', anchor='frame',
              decoder_graph=0, levers=('cone', 1, 1), options=None):
        return contract.check_display_allocator_release_scope(mode, frames, placement, anchor,
                         decoder_graph, levers, self.options() if options is None else options)

    def test_scope_accepts_only_explicit169_and_off_retains_parent(self):
        self.check()
        self.check('off', frames=49, placement='two-way', anchor='guide', decoder_graph=1,
                   levers=('full', 0, 0), options={})
        for field, value in [('frames',145), ('placement','two-way'), ('anchor','latent'),
                             ('decoder_graph',1), ('levers',('full',1,1)),
                             ('levers',('cone',0,1)), ('levers',('cone',1,0))]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.check(**{field:value})
        for field, value in [('aux_residency','xpu2'), ('display_device','xpu:3'),
                             ('display_schedule','sampler-a'), ('display_worker','serial'),
                             ('snapshot_schedule','a-xpu3-sync'), ('snapshot_mode','walk'),
                             ('anchor_read_ahead',1)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(options=dict(self.options(), **{field:value}))

    def test_invalid_mode_refused(self):
        for mode in ('on', '', 1, None):
            with self.subTest(mode=mode), self.assertRaises(ValueError): self.check(mode)

    def test_receipts_reject_wrong_scope_and_unknown_value(self):
        rows, _, _ = fixtures.passing()
        for mode in ('before-admission','invalid'):
            row=copy.deepcopy(rows[0]); row['server_options']['display_allocator_release']=mode
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                stream_receipts.validate_measurements(row)

    def test_qualification_rejects_release_identity_mismatch(self):
        rows, decodes, captures = fixtures.passing()
        rows[4]['server_options']['display_allocator_release']='off'
        self.assertFalse(fixtures.decide(rows,decodes,captures)['passed'])

    def test_namespace_and_launcher_bind_the_option(self):
        tree=ast.parse((HERE/'runtime_packet.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='expected_run_name')
        key='169/two-way20-28/frame/dg0/ad-cone/bo1/pa1/sm-fingerprint'
        ns=dict(os=os,RUN_NAMES={key:'stream133-base'})
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<run-name>','exec'),ns)
        env=dict(zip(('LTX_STREAM_FRAMES','LTX_SAMPLER_PLACEMENT','LTX_ANCHOR','LTX_DECODER_GRAPH',
                      'LTX_ANCHOR_DECODE','LTX_BENCODE_OVERLAP','LTX_PREP_AHEAD','LTX_SNAPSHOT_MODE'),
                     ('169','two-way20-28','frame','0','cone','1','1','fingerprint')))
        parent=ns['expected_run_name'](env)
        self.assertEqual(ns['expected_run_name'](dict(env,LTX_DISPLAY_ALLOCATOR_RELEASE='off')),parent)
        self.assertEqual(ns['expected_run_name'](dict(env,LTX_DISPLAY_ALLOCATOR_RELEASE='before-admission')),
                         parent+'-arbefore-admission')
        launcher=(HERE/'launch-133.sh').read_text()
        self.assertIn('AR=${LTX_DISPLAY_ALLOCATOR_RELEASE:-off}',launcher)
        self.assertIn('LTX_DISPLAY_ALLOCATOR_RELEASE=$AR',launcher)
        self.assertIn('NAME=${NAME}-arbefore-admission',launcher)
        self.assertIn('PY=/home/steve/.venvs/ltx25-baseline/bin/python\n',launcher)

if __name__=='__main__': unittest.main()
