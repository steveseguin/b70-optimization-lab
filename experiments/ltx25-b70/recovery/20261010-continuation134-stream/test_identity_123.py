"""120 parent graph and strict new qualification proof regressions, CPU only."""
import copy
import importlib.util
import unittest
from pathlib import Path
import stream_contract as c
import test_gate_receipts as fixtures

class ParentIdentity(unittest.TestCase):
    def test_all_geometry_matches_sealed133(self):
        path=Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-133b/resolution/components/stream_contract.py')
        spec=importlib.util.spec_from_file_location('contract127_geometry',path)
        parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
        for frames in c.FRAME_CHOICES:
            self.assertEqual(c.geometry(frames),parent.geometry(frames))

    def test_all_3960_qualification_graphs_equal_after_namespace_normalization(self):
        path=Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-133b/resolution/components/stream_contract.py')
        spec=importlib.util.spec_from_file_location('contract120_identity',path)
        parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
        def normalize(value):
            if isinstance(value,dict):return {k:normalize(v) for k,v in value.items()}
            if isinstance(value,list):return [normalize(v) for v in value]
            if isinstance(value,str):return value.replace('stream134-','stream133b-').replace('stream-candidate-134-v1','stream-candidate-133b-v1')
            if type(value) is int and 13400000 <= value < 13401000:return value-80000
            if type(value) is int and 13410000 <= value < 13411000:return value-89000
            return value
        count=0
        for key in parent.variant_keys():
            for reuse in (0,1):
                f,p,a,d,ad,bo,pa=key
                old=parent.qualification_params(f,reuse,p,a,d,ad,bo,pa)
                new=c.qualification_params(f,reuse,p,a,d,ad,bo,pa)
                for x,y in zip(old,new):
                    self.assertEqual(parent.build_chunk_graph(x),normalize(c.build_chunk_graph(y)))
                    count+=1
                self.assertEqual(c.numerical_contract(*key),parent.numerical_contract(*key))
                self.assertEqual(c.qualification_id(*key),parent.qualification_id(*key))
        self.assertEqual(count,3960)
        self.assertEqual([normalize(x) for x in c.setup_graphs()], parent.setup_graphs())

class ProofRejection(unittest.TestCase):
    def test_mismatched_options_fail(self):
        r,d,k=fixtures.passing();r[5]['server_options']['anchor_read_ahead']=1
        self.assertFalse(fixtures.decide(r,d,k)['passed'])

    def test_unknown_shared_options_fail(self):
        r,d,k=fixtures.passing()
        for row in r:row['server_options']['display_schedule']='invented'
        self.assertFalse(fixtures.decide(r,d,k)['passed'])

    def test_qualification_partial_barrier_fails(self):
        r,d,k=fixtures.passing();r[4]['snapshots'][0]['synchronized']=['xpu:3']
        self.assertFalse(fixtures.decide(r,d,k)['passed'])

    def test_qualification_missing_memory_card_fails(self):
        r,d,k=fixtures.passing();r[4]['snapshots'][0]['memory_cards']=['xpu:3']
        self.assertFalse(fixtures.decide(r,d,k)['passed'])

    def test_read_ahead_option_without_exercised_hit_fails(self):
        r,d,k=fixtures.passing(anchor='frame')
        for row in r:row['server_options']['anchor_read_ahead']=1
        self.assertFalse(fixtures.decide(r,d,k,anchor='frame')['passed'])
