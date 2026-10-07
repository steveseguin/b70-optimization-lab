"""CPU pilot controls: independent graph deltas, budgets and tamper refusal."""
import copy
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('duration109_plan', Path(__file__).with_name('plan_reference.py'))
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)


class PlanControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graphs, cls.fixtures = P.load_inputs()
        cls.plan = P.build_plan(cls.graphs, cls.fixtures)

    def reject(self, mutate):
        value = copy.deepcopy(self.plan); mutate(value)
        with self.assertRaisesRegex(ValueError, 'exact pinned construction'):
            P.validate_envelope(P.envelope(value), self.plan)

    def test_pinned_original_ledger_explicit_subset(self):
        original = P.strict_json(P.regular(P.FIXTURES))['fixtures']
        self.assertEqual(tuple(f['id'] for f in original), P.ORIGINAL_IDS)
        self.assertEqual(tuple(f['id'] for f in self.fixtures), ('boat','marble','bird'))
        self.assertEqual(self.fixtures, [{k:r[k] for k in ('id','prompt','seed','window')} for r in original[:3]])
        with self.assertRaisesRegex(ValueError, 'fixture order'):
            P.build_plan(self.graphs, self.fixtures[::-1])

    def test_native_graph_changes_only_duration_identity_and_existing640_geometry(self):
        prior=P.strict_json((P.HERE.parent/'20261007-sparse-transport107-plan/candidate-plan.json').read_bytes())['plan']
        for i in range(3):
            a=copy.deepcopy(self.plan['requests'][i]['graph']);b=copy.deepcopy(prior['requests'][i]['graph'])
            for g in (a,b):
                for n in g.values():
                    for key in ('run_name','clip_index','qualification_id'):
                        if not isinstance(n['inputs'].get(key),list):n['inputs'].pop(key,None)
            self.assertEqual(a['356']['inputs']['length'],49)
            self.assertEqual(a['366']['inputs']['frames_number'],49)
            a['356']['inputs']['length']=25;a['366']['inputs']['frames_number']=25
            self.assertEqual(a,b)
        self.assertTrue(set(('422','426','428','431')).isdisjoint(self.plan['requests'][0]['graph']))

    def test_all_graphs_duration_audio_rate_prompts_and_steps(self):
        fx={r['id']:r for r in self.fixtures}
        for row in self.plan['requests']:
            g=row['graph'];f=fx[row['fixture']]
            self.assertEqual(g['356']['inputs'],dict(width=320,height=192,length=49,batch_size=1))
            self.assertEqual(g['366']['inputs']['frames_number'],49)
            self.assertEqual(g['366']['inputs']['frame_rate'],24.0)
            self.assertEqual(g['365']['inputs']['frame_rate'],24.0)
            self.assertEqual(g['364']['inputs']['text'],f['prompt'])
            for n in ('338','339'):self.assertEqual(g[n]['inputs']['noise_seed'],f['seed'])
            base=self.graphs['native' if row['phase'] in ('native-reference','native-repeat') else 'optimized']
            for n in ('388','391','395','404'):
                if n in g:self.assertEqual(g[n],base[n])
            self.assertEqual(row['graph_sha256'],P.digest(P.canonical(g)))
        for n,k,v in [('356','length',25),('366','frames_number',25),('365','frame_rate',48),('395','sigmas','0.85,0.0')]:
            self.reject(lambda p:p['requests'][0]['graph'][n]['inputs'].__setitem__(k,v))

    def test_optimized_graph_delta_preserves_predecessor_operations(self):
        prior=P.strict_json((P.HERE.parent/'20261007-sparse-transport107-plan/candidate-plan.json').read_bytes())['plan']
        for row in self.plan['requests'][6:]:
            old=next(r for r in prior['requests'] if r['phase']==row['phase'] and r['fixture']==row['fixture'])
            a,b=copy.deepcopy(row['graph']),copy.deepcopy(old['graph'])
            for graph in (a,b):
                for node in graph.values():
                    for key in ('run_name','clip_index','qualification_id'):
                        if not isinstance(node['inputs'].get(key),list):node['inputs'].pop(key,None)
            a['356']['inputs']['length']=25;a['366']['inputs']['frames_number']=25
            self.assertEqual(a,b)

    def test_fresh_same_length_repeat_and_emitted_mapping(self):
        for a,b in zip(self.plan['requests'][:3],self.plan['requests'][3:6]):
            self.assertNotEqual(a['name'],b['name']);self.assertNotEqual(a['clip_index'],b['clip_index'])
            self.assertEqual(a['fixture'],b['fixture'])
        for phase in ('candidate-check','timed-fast'):
            rows=[r for r in self.plan['requests'] if r['phase']==phase]
            self.assertEqual(len(rows),7)
            self.assertEqual([r['expected_emitted_index'] for r in rows],[None]*4+[0,1,2])
            self.assertEqual([r['expected_emitted_fixture'] for r in rows[4:]],list(P.IDS))
            self.assertEqual(rows[4]['fixture'],'marble')
            self.assertEqual(rows[4]['reference'],P.PREFIX+'-native-p1-boat')
        self.assertEqual(len(self.plan['comparisons']),9)

    def test_no_trace_control_or_fullsuite_claim(self):
        self.assertEqual(self.plan['basis']['duration_pilot']['diagnostics'],'none')
        self.assertNotIn('sparse_transport',self.plan['basis'])
        self.assertFalse(any(r['phase']=='timed' or 'trace_enabled' in r for r in self.plan['requests']))
        self.assertEqual(self.plan['timing_scopes'][0]['completion_interval_count'],2)
        self.assertEqual(self.plan['timing_scopes'][0]['emitted_indices'],[0,1,2])
        self.assertIn('no adoption, full-suite',self.plan['claim_limit'])
        self.assertFalse(self.plan['runtime_qualified']);self.assertEqual(self.plan['model_requests'],0)

    def test_exact_shapes_and_payload_size(self):
        self.assertEqual(self.plan['expected_shapes'],{'images':[49,384,640,3],
            'video_latent':[1,128,7,12,20],'audio_latent':[1,8,51,16],'waveform':[1,2,96480]})
        self.assertEqual(sum(math.prod(v)*4 for v in self.plan['expected_shapes'].values()),146164992)
        self.reject(lambda p:p['expected_shapes']['audio_latent'].__setitem__(2,26))
        self.reject(lambda p:p['comparison_tensors'].remove('waveform'))

    def test_capture_categories_cover_every_graph_without_suppression(self):
        s=self.plan['proposed_storage_policy'];c=s['capture_classification']
        full=set(c['full_output_equivalent_request_names']);empty=set(c['placeholder_request_names'])
        self.assertEqual((len(full),len(empty)),(14,8));self.assertFalse(full & empty)
        self.assertEqual(full|empty,{r['name'] for r in self.plan['requests']}|{P.PREFIX+'-capture0',P.PREFIX+'-capture1'})
        for phase in ('candidate-check','timed-fast'):
            self.assertTrue({f'{P.PREFIX}-{phase}-{i:02}' for i in range(4)} <= empty)
        self.assertEqual(s['max_total_captures'],22)
        self.assertFalse(s['enforced']);self.assertFalse(s['extra_request_or_hidden_output_suppression'])
        for key,value in [('max_total_captures',16),('placeholder_max_bytes',2**30),('full_output_equivalent_cap',16)]:
            self.reject(lambda p:p['proposed_storage_policy'].__setitem__(key,value))

    def test_budget_arithmetic_and_actual_placeholder_bound(self):
        s=self.plan['proposed_storage_policy']
        total=14*(146164992+65544)+8*2**20+2**30+512*2**20+192*2**20
        self.assertEqual(total,3867555440);self.assertEqual(s['total_bound_bytes'],total)
        self.assertEqual(s['planned_write_bytes']-total,427411856)
        self.assertEqual(s['planned_write_bytes'],4*2**30);self.assertEqual(s['min_free_bytes'],50*2**30)
        # Largest fill retains stageB latents and existing 8x8/8-sample placeholders.
        placeholder=4*(128*7*12*20+8*51*16+1*8*8*3+1*2*8)+65544
        self.assertEqual(placeholder,952648);self.assertLess(placeholder,2**20)
        self.assertTrue(any('BEFORE opening' in x for x in s['required_prewrite_checks']))
        self.assertTrue(any('never truncate' in x for x in s['required_prewrite_checks']))

    def test_first_native_barrier_is_bound_and_pending(self):
        b=self.plan['first_native_barrier']
        self.assertEqual(b['after_request'],self.plan['requests'][0]['name'])
        self.assertEqual(b['before_request'],self.plan['requests'][1]['name'])
        self.assertFalse(b['implemented']);self.assertEqual(b['action'],'verify-first-native')
        self.assertTrue(any('2GiB' in r for r in b['requires']))
        self.reject(lambda p:p.pop('first_native_barrier'))

    def test_policy_durability_and_predecessor_refusal_history(self):
        self.assertEqual(P.digest(P.regular(P.PREDECESSOR_CLOSEOUT)),P.PREDECESSOR_CLOSEOUT_SHA)
        self.assertEqual(self.plan['basis']['duration_pilot']['predecessor_manifest_sha256'],P.PREDECESSOR_SHA)
        for r in self.plan['requests']:
            self.assertEqual(r['client_checkpoint_policy'],'storage-change-only' if r['phase']=='timed-fast' else 'always')
        self.assertIn('event log flush/fsync',self.plan['client_checkpoint_contract']['always_required'])
        self.reject(lambda p:p['client_checkpoint_contract']['always_required'].remove('fault/halt checks'))

    def test_layout_identity_binds_both_source_histories_without_quality_transfer(self):
        b = self.plan['basis']; d = b['duration_pilot']
        self.assertEqual((b['layout'],b['blocks']),('two-way20-28',[20,28]))
        self.assertEqual(d['predecessor_manifest_sha256'],P.PREDECESSOR_SHA)
        self.assertEqual(d['placement_basis']['manifest_sha256'],P.PLACEMENT_SHA)
        self.assertIn('no49-frame quality transfer',d['placement_basis']['scope'])
        self.assertEqual(d['memory_admission']['native_pre_gib'],[8,8,2,9])
        self.assertEqual(d['memory_admission']['capture_pre_gib'],[7,7,2,9])
        self.assertEqual(d['memory_admission']['decode_pre_gib'],[2,2,10,9])
        self.assertEqual(P.digest(P.canonical(b)),self.plan['qualification_id'])
        for key,value in [('layout','two-way'),('blocks',[23,25])]:
            changed=copy.deepcopy(b);changed[key]=value
            self.assertNotEqual(P.digest(P.canonical(changed)),self.plan['qualification_id'])
            self.reject(lambda p:p['basis'].__setitem__(key,value))
        self.reject(lambda p:p['basis']['duration_pilot']['memory_admission'].__setitem__('native_pre_gib',[6,6,2,7]))

    def test_all_request_math_identical_to108_after_namespace_normalization(self):
        old=P.strict_json(P.regular(P.HERE.parent/'20261007-duration108-plan/candidate-plan.json'))['plan']
        self.assertEqual(self.plan['expected_shapes'],old['expected_shapes'])
        for a,b in zip(self.plan['requests'],old['requests']):
            x,y=copy.deepcopy(a['graph']),copy.deepcopy(b['graph'])
            for graph in (x,y):
                for node in graph.values():
                    for key in ('run_name','clip_index','qualification_id'):
                        if not isinstance(node['inputs'].get(key),list):node['inputs'].pop(key,None)
            self.assertEqual(x,y)
        self.assertEqual(len(self.plan['requests']),len(old['requests']))
        self.assertEqual(self.plan['proposed_storage_policy']['total_bound_bytes'],old['proposed_storage_policy']['total_bound_bytes'])

    def test_unique_indices_ceiling_and_saved_reconstruction(self):
        indices=[r['clip_index'] for r in self.plan['requests']]
        self.assertEqual(indices,list(range(99909000,99909006))+list(range(99909100,99909107))+list(range(99909200,99909207)))
        self.assertEqual(len(set(indices)),20);self.assertLessEqual(max(indices),100000000)
        P.validate_envelope(P.strict_json(P.regular(P.HERE/'candidate-plan.json')),self.plan)
        self.assertNotIn('torch',sys.modules)
        self.reject(lambda p:p['requests'].append(copy.deepcopy(p['requests'][-1])))

    def test_invalid_sources_hashes_and_graph_edges_refused(self):
        value=P.envelope(self.plan);value['plan_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Plan hash'):P.validate_envelope(value,self.plan)
        with self.assertRaisesRegex(ValueError,'Duplicate'):P.strict_json('{"x":1,"x":2}')
        g=copy.deepcopy(self.plan['requests'][0]['graph']);g['344']['inputs']['latent_image']=['344',0]
        with self.assertRaisesRegex(ValueError,'cycle'):P.validate_graph_edges(g)
        g['344']['inputs']['latent_image']=['999',0]
        with self.assertRaisesRegex(ValueError,'edge'):P.validate_graph_edges(g)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'manifest.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'manifest differs'):P.load_inputs(root,P.FIXTURES)


if __name__ == '__main__':unittest.main(verbosity=2)
