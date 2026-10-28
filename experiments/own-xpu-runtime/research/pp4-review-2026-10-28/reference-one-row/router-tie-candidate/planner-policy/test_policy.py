"""CPU planner regression; existing fake receipts/owners, no native launch."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'AGENT_HANDOFF.md').is_file())
sys.path.insert(0, str(ROOT/'experiments/own-xpu-runtime/engine/tools'))
import pipeline_driver as base
import dedicated_provider_driver as dedicated
import persistent_rolling_driver as persistent
from test_pipeline_driver import PlanningTests
from test_dedicated_bulk_plan import BulkPlanTests
from test_persistent_rolling import PersistentPlanTests
FLAG = 'OWNRT_REFERENCE_ROUTE_TIE_SORT'

class PolicyTests(PlanningTests):
    def capability(self):
        path=Path(self.config['build_receipt']); r=json.loads(path.read_text())
        for name in ('adapter.cpp','reference_sort_addressed.hpp'):
            relative='stage2/packet194-expert-diet-engine/'+name
            r['sources'][relative]=base.digest(base.HERE.parent/'src'/relative)
        path.write_text(json.dumps(r))

    def test_default_false_and_parent_flag_cannot_enable_owners(self):
        for value in ('absent',False):
            if value is False:self.config['reference_route_tie_sort']=False
            with patch.dict(os.environ,{FLAG:'1'}):p=self.plan()
            self.assertFalse(p['reference_route_tie_sort'])
            self.assertEqual({s['environment'][FLAG] for s in p['stages']},{'0'})
            self.assertEqual(p['reference_route_scope'],'f32-target-only')
            self.assertEqual(p['draft_route_policy'],'unchanged-bf16')

    def test_true_reaches_every_stage_without_changing_lookup(self):
        self.capability();self.config['reference_route_tie_sort']=True
        a=Path(self.config['adapter_plan']);v=json.loads(a.read_text())
        for env in v['environment']:env.update(OWNRT_LOOKUP_COPY='1',OWNRT_DRAFT_KERNELS='router')
        a.write_text(json.dumps(v));p=self.plan()
        for s in p['stages']:
            self.assertEqual(s['environment'][FLAG],'1')
            self.assertEqual(s['environment']['OWNRT_LOOKUP_COPY'],'1')
            self.assertEqual(s['environment']['OWNRT_DRAFT_KERNELS'],'router')

    def test_non_boolean_values_refused(self):
        for value in (0,1,None,'1',[],{}):
            with self.subTest(value=value):
                self.config['reference_route_tie_sort']=value
                with self.assertRaisesRegex(ValueError,'must be Boolean'):self.plan()

    def test_compiled_capability_required_only_when_on(self):
        self.plan();self.config['reference_route_tie_sort']=True
        with self.assertRaisesRegex(ValueError,'compiled reference route policy'):self.plan()
        self.capability();self.plan()

    def test_adapter_contradictions_refused_for_both_rank_templates(self):
        self.capability();a=Path(self.config['adapter_plan']);original=json.loads(a.read_text())
        for enabled in (False,True):
            self.config['reference_route_tie_sort']=enabled
            for rank in (0,1):
                v=deepcopy(original);v['environment'][rank][FLAG]='0' if enabled else '1';a.write_text(json.dumps(v))
                with self.assertRaisesRegex(ValueError,'contradicts explicit config'):self.plan()
                v['environment'][rank][FLAG]='1' if enabled else '0';a.write_text(json.dumps(v));self.plan()

class DerivedPolicyTests(unittest.TestCase):
    def set_policy(self,p,enabled):
        p.update(reference_route_tie_sort=enabled,reference_route_scope='f32-target-only',draft_route_policy='unchanged-bf16')
        for s in p['stages']:s['environment'].update({FLAG:str(int(enabled)),'OWNRT_LOOKUP_COPY':'1'})
        return p

    def test_dedicated_two_and_three_targets_and_provider_scope(self):
        for count in (2,3):
            with tempfile.TemporaryDirectory() as td:
                path,c,p,_=BulkPlanTests().fixture(Path(td));cuts=[0,25,48] if count==2 else [0,17,33,48]
                if count==3:
                    p['stages'].insert(1,deepcopy(p['stages'][0]));c['boundaries']=cuts
                    for i,(s,bdf) in enumerate(zip(p['stages'],('0000:23:00.0','0000:27:00.0','0000:47:00.0'))):
                        s.update(id=i,bdf=bdf,first=i==0,final=i==2,begin=cuts[i],end=cuts[i+1])
                path.write_text(json.dumps(c));hashes=[]
                for enabled in (False,True):
                    policy=self.set_policy(deepcopy(p),enabled)
                    with patch.object(base,'make_plan',return_value=policy):out=dedicated.make_plan(path)
                    for owner in out['stages']+[out['provider']]:
                        self.assertEqual(owner['environment'][FLAG],str(int(enabled)))
                        self.assertEqual(owner['environment']['OWNRT_LOOKUP_COPY'],'1')
                    hashes.append(out['request_sha256'])
                self.assertNotEqual(*hashes) # Config identical: effective policy itself binds identity.

    def test_colocated_provider_and_all_targets_share_policy_identity(self):
        with tempfile.TemporaryDirectory() as td:
            path,_,_,underlying=PersistentPlanTests().fixture(Path(td));hashes=[]
            for enabled in (False,True):
                with patch.object(base,'make_plan',side_effect=lambda p:self.set_policy(underlying(p),enabled)):
                    out=persistent.make_plan(path)
                for owner in out['stages']:
                    self.assertEqual(owner['environment'][FLAG],str(int(enabled)))
                    self.assertEqual(owner['environment']['OWNRT_LOOKUP_COPY'],'1')
                hashes.append(out['request_sha256'])
            self.assertNotEqual(*hashes)

if __name__=='__main__':unittest.main()
