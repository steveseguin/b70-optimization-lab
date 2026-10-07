"""Small CPU-only source/topology/accounting tests; no model or capture payloads."""
import ast
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import plan as P


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.envelope=P.build_plan();cls.plan=cls.envelope['plan']

    def test_exact_eight_request_order_and_six_full_captures(self):
        rows=self.plan['requests']
        expected=['continuation111-window-probe','continuation111-prepare-native']
        expected+=['continuation111-pass%d-chunk%d'%(p,c) for p in range(2) for c in range(3)]
        self.assertEqual(self.plan['execution_order'],expected)
        self.assertEqual([r['name'] for r in rows],expected)
        self.assertEqual([r['phase'] for r in rows],['native-setup']*2+['native-reference']*3+['native-repeat']*3)
        self.assertEqual([r['capture_role'] for r in rows],[None,None]+['full']*6)
        self.assertEqual([r['clip_index'] for r in rows[2:]],[99911000,99911001,99911002,99911010,99911011,99911012])
        self.assertTrue(all(r['authority_phase']=='native_reference' for r in rows))
        self.assertEqual(self.plan['budget']['max_attempts'],8)
        self.assertEqual(self.plan['budget']['max_captures'],6)
        self.assertEqual(self.plan['budget']['retries'],0)

    def test_setup_preserves_exact110_topology_only_names_rebound(self):
        p=P.prototype()
        old=p.anchor.strict_json(P.read(p.PACKET/'resolution/setup-schedule.json',P.SETUP_FILE_SHA))['schedule']['rows'][:2]
        for before,after in zip(old,self.plan['requests'][:2]):
            graph=copy.deepcopy(before['graph'])
            for node in graph.values():
                if 'run_name' in node['inputs']:node['inputs']['run_name']=after['name']
            self.assertEqual(after['graph'],graph)
        self.assertEqual(self.plan['requests'][1]['requires_proofs'],['proof:continuation111-window-probe'])

    def test_all_graphs_are_static_and_provider_has_run_name_only(self):
        for row in self.plan['requests']:
            graph=row['graph'];P.validate_edges(graph)
            self.assertEqual(P.sha(P.canonical(graph)),row['graph_sha256'])
            providers=[n for n in graph.values() if n['class_type']==P.PROVIDER]
            self.assertEqual(len(providers),int(bool(row.get('chunk_index',0))))
            for node in providers:self.assertEqual(node['inputs'],{'run_name':row['name']})
            for node in graph.values():
                self.assertFalse({'anchor_sha256','capture_path','predecessor_run','expected_sha256'}&set(node['inputs']))
        self.assertIn('actual outer plan_sha256',self.plan['provider_binding']['context_plan_sha256'])

    def test_qid_precedes_graph_identity_and_is_distinct_from_actual_plan(self):
        self.assertEqual(self.plan['qualification_id'],P.sha(P.canonical(self.plan['numerical_contract'])))
        self.assertEqual(self.envelope['plan_sha256'],P.sha(P.canonical(self.plan)))
        self.assertNotEqual(self.envelope['plan_sha256'],self.plan['qualification_id'])
        self.assertNotEqual(self.envelope['plan_sha256'],self.plan['basis']['prototype_numerical_design_sha256'])
        for row in self.plan['requests'][2:]:
            self.assertEqual(row['graph']['364']['inputs']['qualification_id'],self.plan['qualification_id'])
        policy=self.plan['numerical_contract']['mandatory_runtime_policy']
        self.assertEqual((policy['torch_default_dtype'],policy['intermediate_device']),('torch.float32','cpu'))
        self.assertEqual((policy['vae_model_dtype'],policy['vae_output_dtype']),('torch.bfloat16','torch.float32'))
        self.assertEqual(policy['before_each_conditioning_stage_floor_gib'],[8,8,2,9])
        self.assertEqual(policy['after_each_conditioning_stage_floor_gib'],2)
        self.assertEqual(policy['sampler_capture_routes'],0);self.assertEqual(policy['decoder_replicas'],0)

    def test_constructor_does_not_fabricate_or_validate_future_capture_bindings(self):
        p=P.prototype()
        with patch.object(P,'prototype',return_value=p), \
             patch.object(p,'build_chunk',side_effect=AssertionError('No future predecessor module')), \
             patch.object(p.anchor,'validate_binding',side_effect=AssertionError('No fabricated capture proof')), \
             patch.object(p.anchor,'extract_anchor',side_effect=AssertionError('No capture reads')):
            self.assertEqual(P.build_plan(),self.envelope)

    def test_numerical_edges_match_source_pinned_prototype_without_fake_predecessor(self):
        p=P.prototype();base,_=p.basis()
        tree=ast.parse(P.read(P.PROTOTYPE/'graph.py',P.PROTOTYPE_PINS['graph.py']))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build_chunk')
        # Execute only the reviewed pure graph-insertion branch. No fake anchor
        # metadata or weakened predecessor validation is passed to the prototype.
        branch=next(n for n in fn.body if isinstance(n,ast.If) and
                    "graph['377']" in ast.unparse(n) and "graph['340']" in ast.unparse(n))
        ns={'graph':copy.deepcopy(base),'chunk_index':1,'ANCHOR_EDGE':p.ANCHOR_EDGE}
        exec(compile(ast.Module(body=[branch],type_ignores=[]),'<pinned-prototype-topology>','exec'),ns)
        expected=ns['graph']
        for row in self.plan['requests'][2:]:
            normalized=copy.deepcopy(row['graph'])
            if row['chunk_index']:
                del normalized['continuation111_anchor']
                for key in ('anchor_stage_a','anchor_stage_b'):
                    normalized[key]['class_type']='LTXVImgToVideoInplace'
                    del normalized[key]['inputs']['run_name'];del normalized[key]['inputs']['stage']
                comparison=expected
            else:comparison=base
            for key in base:
                if 'run_name' in base[key]['inputs']:normalized[key]['inputs']['run_name']=base[key]['inputs']['run_name']
            for key in ('338','339'):normalized[key]['inputs']['noise_seed']=42
            for key in ('clip_index','qualification_id'):normalized['364']['inputs'][key]=base['364']['inputs'][key]
            self.assertEqual(normalized,comparison)

    def test_exact_guarded_call_contract_both_stages_and_native_audio_unchanged(self):
        p=P.prototype();base,_=p.basis()
        for row in self.plan['requests'][2:]:
            graph=row['graph']
            for key in ('344','368','348','366','358','365','388','391','395','404'):
                self.assertEqual(graph[key],base[key])
            if row['chunk_index']:
                for key,stage,edge in [('anchor_stage_a','A',['356',0]),('anchor_stage_b','B',['348',0])]:
                    self.assertEqual(graph[key],{'class_type':P.CONDITIONER,'inputs':{
                        'vae':['420',2],'image':['continuation111_anchor',0],'latent':edge,
                        'strength':1.0,'bypass':False,'run_name':row['name'],'stage':stage}})
        spec=self.plan['node_contracts'][P.CONDITIONER]
        self.assertEqual(spec['native_source_sha256'],self.plan['basis']['source_files']['source/comfy_extras/nodes_lt.py'])
        self.assertFalse(spec['registered'])

    def test_per_chunk_proofs_first_conditioned_and_replay_linkage(self):
        rows=self.plan['requests']
        self.assertEqual(rows[2]['establishes'],['first-native-verified'])
        self.assertEqual(rows[3]['establishes'],['first-conditioned-verified'])
        for i,row in enumerate(rows[1:],1):self.assertIn('proof:'+rows[i-1]['name'],row['requires_proofs'])
        for row in rows[2:]:
            p,c=row['pass_index'],row['chunk_index']
            self.assertEqual(row['predecessor_capture'],None if c==0 else 'continuation111-pass%d-chunk%d'%(p,c-1))
            self.assertEqual(row['reference_capture'],None if p==0 else 'continuation111-pass0-chunk%d'%c)
            if c and (p or c==2):self.assertIn('first-conditioned-verified',row['requires_proofs'])

    def test_capture_and_provisional_disk_bounds_not_admission(self):
        c=self.plan['capture_contract'];b=self.plan['budget'];claims=self.plan['claims']
        self.assertEqual(c['raw_capture_bound_bytes'],877383216)
        self.assertEqual(len(c['roles']),6);self.assertEqual(set(c['roles'].values()),{'full'})
        self.assertEqual(b['minimum_free_before_build_bytes'],54*P.GIB+384*P.MIB)
        self.assertEqual(b['runtime_write_allowance_bytes'],4*P.GIB)
        self.assertEqual(b['min_free_bytes'],50*P.GIB)
        self.assertEqual(b['raw_capture_bound_bytes']+b['all_other_outputs_must_fit_remaining_bytes'],4*P.GIB)
        self.assertFalse(b['admitted']);self.assertFalse(self.plan['proof_contract']['encode_workspace_admitted'])
        self.assertEqual(claims['unique_video_frames_per_chain'],145)
        self.assertEqual(sum(r['new_video_frames'] for r in self.plan['requests'][2:5]),145)
        self.assertFalse(claims['replay_is_additional_unique_content']);self.assertFalse(claims['continuous_av'])
        self.assertEqual(self.plan['proof_contract']['native_pre_floor_gib'],[8,8,2,9])

    def test_rehashed_order_guard_arithmetic_count_budget_or_identity_drift_rejected(self):
        for mode in ('order','last-seed','single-stage','stage-alias','provider-path','raw-cap','reserve','barrier','context','shape'):
            value=copy.deepcopy(self.envelope);p=value['plan'];rows=p['requests']
            if mode=='order':rows[-1],rows[-2]=rows[-2],rows[-1]
            if mode=='last-seed':rows[-1]['graph']['338']['inputs']['noise_seed']=45
            if mode=='single-stage':rows[3]['graph']['340']['inputs']['video_latent']=['348',0]
            if mode=='stage-alias':rows[3]['graph']['anchor_stage_a']['inputs']['stage']='a'
            if mode=='provider-path':rows[3]['graph']['continuation111_anchor']['inputs']['capture_path']='/tmp/arbitrary'
            if mode=='raw-cap':p['budget']['max_captures']=7
            if mode=='reserve':p['budget']['min_free_bytes']-=1
            if mode=='barrier':rows[4]['requires_proofs']=[]
            if mode=='context':p['provider_binding']['context_plan_sha256']='prototype hash'
            if mode=='shape':p['capture_contract']['shapes']['images'][0]=25
            for row in rows:row['graph_sha256']=P.sha(P.canonical(row['graph']))
            value['plan_sha256']=P.sha(P.canonical(p))
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'exact reviewed'):P.validate(value)

    def test_source_drift_and_special_file_rejected(self):
        pins=dict(P.PROTOTYPE_PINS);pins['graph.py']='f'*64
        with patch.object(P,'PROTOTYPE_PINS',pins),self.assertRaisesRegex(ValueError,'Pinned source'):P.build_plan()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fifo';os.mkfifo(path)
            with self.assertRaisesRegex(ValueError,'Nonregular'):P.read(path,'a'*64)

    def test_exact_reconstruction_and_no_model_import(self):
        self.assertEqual(P.validate(self.envelope),self.envelope)
        self.assertNotIn('torch',__import__('sys').modules)
        with self.assertRaises(ValueError):P.native_graph({},False,0,'a'*64)


if __name__=='__main__':unittest.main()
