"""CPU-only startup placement, parent identity and admission contracts."""
import ast
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import text_residency133 as text
import cone_memory131 as cone
import stream_contract as contract

HERE = Path(__file__).resolve().parent

def environment():
    return dict(text.SCOPE, LTX_TEXT_RESIDENCY='split36')

def opts():
    return dict(text_residency='split36', text_oracle_sha256=text.ORACLE_SHA256,
        cone_graph_memory='text-shift', display_device='xpu:3', display_schedule='eager-display',
        display_worker='serial', anchor_read_ahead=0, snapshot_schedule='full',
        snapshot_mode='fingerprint', aux_residency='legacy', audio_residency='legacy',
        cone_capture_reserve='parent', display_allocator_release='off', decoder_graph_pool_cap_bytes=None)

class Text133(unittest.TestCase):
    def test_off_is_parent(self):
        self.assertEqual(text.launch({}), 'legacy')
        self.assertEqual(text.split_index({}), 24)
        self.assertEqual(text.options({}), {'text_residency': 'legacy', 'text_oracle_sha256': None})
    def test_on_is_startup36(self):
        self.assertEqual(text.split_index(environment()), 36)
        self.assertEqual(text.validate_scope(environment()), 'split36')
        self.assertEqual(cone.validate_scope(environment()), 'text-shift')
        contract.check_text_residency_scope(145, 'two-way20-28', 'frame', 1, ('cone',1,1), opts())
    def test_unknown_mode_refuses(self):
        for value in ('', 'cpu', 'split32', 'split48', None, 36):
            with self.assertRaises(ValueError): text.launch({text.ENV:value})
    def test_oracle_is_hash_bound(self):
        value = text.load_oracle(HERE/'text-oracle133.json')
        self.assertEqual(len(value['prompts']), 12)
        self.assertEqual(len(value['window_probe']['rows']), 40)
        with patch.object(Path, 'read_bytes', return_value=b'{}'):
            with self.assertRaisesRegex(ValueError, 'hash'): text.load_oracle(HERE/'text-oracle133.json')
    def test_all_parent_conditioning_passes(self):
        oracle = text.load_oracle()
        for sha, row in oracle['prompts'].items():
            self.assertTrue(text.check_conditioning(oracle,sha,row['tensors'])['passed'])
    def test_unknown_prompt_refuses(self):
        with self.assertRaisesRegex(ValueError,'no parent'): text.check_conditioning(text.load_oracle(),'0'*64,[])
    def test_complete_window_passes(self):
        oracle=text.load_oracle()
        self.assertTrue(text.check_window(oracle,dict(oracle['window_probe'],passed=True))['passed'])
    def test_window_missing_duplicate_reordered_refuse(self):
        oracle=text.load_oracle()
        for rows in (oracle['window_probe']['rows'][:-1],oracle['window_probe']['rows']*2,list(reversed(oracle['window_probe']['rows']))):
            with self.assertRaises(ValueError): text.check_window(oracle,dict(oracle['window_probe'],passed=True,rows=rows))
    def test_node_transform_changes_only_startup_boundary(self):
        parent=Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-132/source/scripts/graph_text_encoder_node.py').read_bytes()
        result=text.transform_node(parent);ast.parse(result)
        self.assertEqual(result.replace(b"import text_residency133\nSHARD = ('xpu:2', 'xpu:3', text_residency133.split_index())",b"SHARD = ('xpu:2', 'xpu:3', 24)"),parent)
        with self.assertRaises(ValueError): text.transform_node(result)
    def test_cone_first_capture_preserves_floor_and_reserve(self):
        floor=(5+9)*2**30+3*2**30//4
        row=cone.admit(object(),lambda:floor,mode='text-shift',first_capture=True)
        self.assertEqual(row['required_bytes'],floor)
        self.assertIsNone(row['allocator_release'])
        self.assertTrue(cone.validate_record(row))
        with self.assertRaises(RuntimeError): cone.admit(object(),lambda:floor-1,mode='text-shift',first_capture=True)
    def test_cone_replay_preserves_floor_and_screen(self):
        floor=9*2**30+3*2**30//4
        row=cone.admit(object(),lambda:floor,mode='text-shift',first_capture=False)
        self.assertTrue(cone.validate_record(row))
        with self.assertRaises(RuntimeError): cone.admit(object(),lambda:floor-1,mode='text-shift',first_capture=False)
    def test_text_shift_never_empties_allocator(self):
        with patch('allocator_release130.snapshot',side_effect=AssertionError('no allocator operation')):
            cone.admit(object(),lambda:20*2**30,mode='text-shift',first_capture=True)
    def test_missing_oracle_metadata_refuses(self):
        options=opts();options.pop('text_oracle_sha256')
        with self.assertRaises(ValueError): contract.check_text_residency_scope(145,'two-way20-28','frame',1,('cone',1,1),options)
    def test_no_live_move_or_numerical_kernel_source(self):
        src=(HERE/'text_residency133.py').read_text()
        self.assertNotIn('import torch',src)
        self.assertNotIn('.to(',src)
        self.assertNotIn('.replay(',src)

for index,key in enumerate(text.SCOPE):
    def check(self,key=key):
        env=environment();env[key]='changed'
        with self.assertRaises(ValueError):text.validate_scope(env)
    setattr(Text133,'test_scope_%02d_%s'%(index,key.lower()),check)
for index in range(40):
    def check(self,index=index):
        oracle=text.load_oracle();report=copy.deepcopy(dict(oracle['window_probe'],passed=True))
        report['rows'][index]['window_sha256'][0]='0'*64
        with self.assertRaises(ValueError):text.check_window(oracle,report)
    setattr(Text133,'test_window_hash_%02d'%index,check)
for index in range(12):
    def check(self,index=index):
        oracle=text.load_oracle();sha=list(oracle['prompts'])[index];rows=copy.deepcopy(oracle['prompts'][sha]['tensors'])
        rows[0]['sha256']='0'*64
        with self.assertRaises(ValueError):text.check_conditioning(oracle,sha,rows)
    setattr(Text133,'test_conditioning_hash_%02d'%index,check)
