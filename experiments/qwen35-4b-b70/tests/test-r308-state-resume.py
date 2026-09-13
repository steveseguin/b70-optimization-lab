#!/usr/bin/env python3
"""CPU-only lifecycle tests executing the exact R308 inserted helper methods."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

PATCH=Path(__file__).resolve().parents[3]/'experiments/qwen38-27b-b70/docker/rebase-v0290/r308-gdn-state-resume.py'
spec=importlib.util.spec_from_file_location('r308_patch',PATCH)
patch=importlib.util.module_from_spec(spec);spec.loader.exec_module(patch)
namespace={};exec('class Runner:\n'+patch.METHODS,namespace);Runner=namespace['Runner']

def make(ids=('a',),counts=(2,),async_scheduling=True,mode='none'):
    r=Runner();r._gdn_state_handoff_enabled=lambda:True
    r.cache_config=NS(mamba_cache_mode=mode);r.use_async_scheduling=async_scheduling
    r.input_batch=NS(req_ids=list(ids),req_id_to_index={x:i for i,x in enumerate(ids)},num_accepted_tokens_cpu=list(counts))
    r.num_accepted_tokens=NS(np=[1]*len(ids),gpu=[1]*len(ids))
    r.syncs=0
    def sync():r.syncs+=1
    r.num_accepted_tokens_event=NS(synchronize=sync)
    return r

def output(finished=(),resumed=()):
    return NS(finished_req_ids=set(finished),scheduled_cached_reqs=NS(resumed_req_ids=set(resumed)))

class Tests(unittest.TestCase):
    def test_sync_and_async_pause(self):
        for asynchronous in (False,True):
            r=make(async_scheduling=asynchronous)
            r._r308_preserve_gdn_acceptance({'a'},output())
            r.input_batch.num_accepted_tokens_cpu[0]=1 # add_request reset
            r._r308_restore_gdn_acceptance(1)
            self.assertEqual(r.num_accepted_tokens.np,[2]);self.assertEqual(r.num_accepted_tokens.gpu,[2])
            self.assertEqual(r.syncs,1);self.assertFalse(r._r308_paused_gdn_acceptance)
    def test_d2h_sync_precedes_snapshot(self):
        r=make(counts=(1,))
        r.num_accepted_tokens_event=NS(synchronize=lambda:r.input_batch.num_accepted_tokens_cpu.__setitem__(0,3))
        r._r308_preserve_gdn_acceptance({'a'},output());r._r308_restore_gdn_acceptance(1)
        self.assertEqual(r.num_accepted_tokens.gpu,[3])
    def test_mixed_rows_reordered_without_overwriting_gpu_correction(self):
        r=make(('a','b','c'),(2,3,4))
        r._r308_preserve_gdn_acceptance({'a','c'},output())
        r.input_batch.req_ids=['c','b','a'];r.num_accepted_tokens.np=[1,1,1];r.num_accepted_tokens.gpu=[1,3,1]
        r._r308_restore_gdn_acceptance(3)
        self.assertEqual(r.num_accepted_tokens.gpu,[4,3,2]);self.assertEqual(r.num_accepted_tokens.np,[4,1,2])
    def test_multiple_empty_steps_and_other_batches(self):
        r=make();r._r308_preserve_gdn_acceptance({'a'},output())
        r.input_batch.req_ids=[];r.input_batch.req_id_to_index={}
        for _ in range(3):r._r308_preserve_gdn_acceptance(set(),output());r._r308_restore_gdn_acceptance(0)
        r.input_batch.req_ids=['b'];r._r308_restore_gdn_acceptance(1)
        self.assertEqual(r.num_accepted_tokens.gpu,[1]);self.assertEqual(r._r308_paused_gdn_acceptance,{'a':2})
        r.input_batch.req_ids=['a'];r._r308_restore_gdn_acceptance(1);self.assertEqual(r.num_accepted_tokens.gpu,[2])
    def test_preemption_and_finished_identity_reuse(self):
        for invalidator in ('resumed','finished'):
            r=make();r._r308_preserve_gdn_acceptance({'a'},output())
            r._r308_preserve_gdn_acceptance(set(),output(**{invalidator:('a',)}))
            r._r308_restore_gdn_acceptance(1);self.assertEqual(r.num_accepted_tokens.gpu,[1])
        r=make();r._r308_preserve_gdn_acceptance({'a'},output(resumed=('a',)))
        self.assertFalse(r._r308_paused_gdn_acceptance);self.assertEqual(r.syncs,0)
    def test_single_accept_noop_and_align_excluded(self):
        for counts,mode in (((1,),'none'),((3,),'align')):
            r=make(counts=counts,mode=mode);r._r308_preserve_gdn_acceptance({'a'},output());r._r308_restore_gdn_acceptance(1)
            self.assertEqual(r.num_accepted_tokens.gpu,[1]);self.assertFalse(r._r308_paused_gdn_acceptance)
    def test_consumed_once(self):
        r=make();r._r308_preserve_gdn_acceptance({'a'},output());r._r308_restore_gdn_acceptance(1)
        r.num_accepted_tokens.gpu[0]=1;r._r308_restore_gdn_acceptance(1);self.assertEqual(r.num_accepted_tokens.gpu,[1])

if __name__=='__main__':unittest.main()
