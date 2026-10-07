#!/usr/bin/env python3
"""Offline controls using pinned real graphs, with independent semantic assertions."""
import ast
import copy
import time
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('resolution_plan', Path(__file__).with_name('plan_reference.py'))
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)


class PlanControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graphs, cls.fixtures = P.load_inputs()
        cls.plan = P.build_plan(cls.graphs, cls.fixtures)

    def reject_changed_plan(self, mutate):
        changed = copy.deepcopy(self.plan); mutate(changed)
        # Even a coherently rehashed modification must fail independent reconstruction.
        with self.assertRaisesRegex(ValueError, 'exact pinned construction'):
            P.validate_envelope(P.envelope(changed), self.plan)

    def test_full_suite_preserves_102_numerics_and_complete_original_order(self):
        olddir=P.HERE.parent/'20261007-resolution-w2-102'
        original=P.strict_json((olddir/'candidate-plan.json').read_bytes())['plan']
        self.assertNotEqual(self.plan['qualification_id'],original['qualification_id'])
        for field in ('expected_shapes','native_encoder_contract','comparison_tensors','pipeline_depths'):
            self.assertEqual(self.plan[field],original[field])
        self.assertEqual(self.plan['fixtures'][:3],original['fixtures'])
        basis=dict(self.plan['basis']);basis['fixture_ids']=original['basis']['fixture_ids']
        self.assertEqual(basis,original['basis'])
        for newrow,oldrow in zip(self.plan['requests'][:3],original['requests'][:3]):
            actual=copy.deepcopy(newrow['graph']);expected=copy.deepcopy(oldrow['graph'])
            for graph in (actual,expected):
                for node in graph.values():
                    for key in ('run_name','clip_index','qualification_id'):
                        node['inputs'].pop(key,None)
            self.assertEqual(actual,expected)
        self.assertEqual(tuple(f['id'] for f in self.fixtures),
            ('boat','marble','bird','pendulum','rain','paper','candle','pour','fabric','wheel'))
        source=P.strict_json(P.regular(P.FIXTURES))['fixtures']
        self.assertEqual(self.fixtures,[{k:r[k] for k in ('id','prompt','seed','window')} for r in source])

    def test_explicit_timing_scopes_exclude_boundary_and_no_headline(self):
        timed=[r for r in self.plan['requests'] if r['phase']=='timed']
        self.assertEqual([r['timing_scope'] for r in timed[:4]],['unscored-fill']*4)
        self.assertEqual([r['timing_scope'] for r in timed[4:14]],['full-suite-pass']*10)
        self.assertEqual([r['timing_scope'] for r in timed[14:]],['bounded-continuity']*30)
        self.assertEqual([r['emitted_suite_pass'] for r in timed[4:]],sum(([i]*10 for i in range(1,5)),[]))
        self.assertEqual([r['expected_emitted_fixture'] for r in timed[4:]],list(P.IDS)*4)
        scopes=self.plan['timing_scopes']
        self.assertEqual(scopes[0]['request_names'],[r['name'] for r in timed[4:14]])
        self.assertEqual(scopes[1]['request_names'],[r['name'] for r in timed[14:]])
        self.assertEqual(scopes[0]['emitted_indices'],list(range(10)))
        self.assertEqual(scopes[1]['emitted_indices'],list(range(10,40)))
        self.assertIn('no cold-request or record headline',scopes[0]['claim'])
        self.assertIn('not endurance or a performance headline',scopes[1]['claim'])
        self.reject_changed_plan(lambda p:p['timing_scopes'][0].__setitem__('emitted_indices',list(range(40))))

    def test_exact_budget_and_namespace(self):
        budget=self.plan['proposed_storage_policy']
        self.assertEqual((budget['max_total_captures'],budget['planned_write_bytes'],budget['min_free_bytes']),
                         (80,7*2**30,50*2**30))
        self.assertEqual([(p['submitted'],p['emitted'],p['pipeline_fills']) for p in self.plan['optimized_phases']],
                         [(14,10,4),(44,40,4)])
        indices=[r['clip_index'] for r in self.plan['requests']]
        self.assertEqual(indices,list(range(99903000,99903020))+list(range(99903100,99903114))+list(range(99903200,99903244)))
        self.assertTrue(all(r['name'].startswith('resolution-full-20261007-') for r in self.plan['requests']))

    def test_actual_pins_and_reproducible_plan(self):
        P.validate_envelope(P.envelope(self.plan), P.build_plan(self.graphs, self.fixtures))
        self.assertEqual(len(self.plan['requests']), 78)
        self.assertFalse(self.plan['runtime_qualified'])
        self.assertNotIn('torch', sys.modules)

    def test_native_sampler_decode_is_independent_of_optimized_path(self):
        base = self.graphs['native']
        for request in self.plan['requests'][:20]:
            graph = request['graph']
            for node in ('344', '348', '358', '368', '374', '388', '391', '395', '404', '414'):
                actual, expected = copy.deepcopy(graph[node]), copy.deepcopy(base[node])
                actual['inputs'].pop('run_name', None); expected['inputs'].pop('run_name', None)
                self.assertEqual(actual, expected, node)
            self.assertTrue(set(('422','426','428','431')).isdisjoint(graph))
            self.assertEqual(graph['356']['inputs'], {'width':320,'height':192,'length':25,'batch_size':1})

    def test_accepted_window_preserved_but_not_claimed_all_eager(self):
        for row in self.plan['requests']:
            g = row['graph']; self.assertEqual(g['364']['inputs']['mode'], 'pipeline-window')
            self.assertEqual(g['425']['inputs']['mode'], 'graph-shard')
            self.assertEqual(g['365']['inputs']['positive'], ['364',0])
            self.assertEqual(g['365']['inputs']['negative'], ['364',0])
            self.assertNotIn('421',g)
            self.assertEqual(g['364']['inputs']['comparison_mode'], P.COMPARISON_MODE)
            self.assertFalse(g['364']['inputs']['speed_only'])
        self.assertTrue(all(f['window']==64 for f in self.plan['fixtures']))

    def test_each_repeat_new_execution_same_fixture_inputs(self):
        a,b = self.plan['requests'][:10],self.plan['requests'][10:20]
        for first,second in zip(a,b):
            self.assertNotEqual(first['name'],second['name']);self.assertNotEqual(first['clip_index'],second['clip_index'])
            self.assertEqual(first['fixture'],second['fixture'])
            self.assertEqual(first['graph']['364']['inputs']['text'],second['graph']['364']['inputs']['text'])
            for n in ('338','339'):self.assertEqual(first['graph'][n],second['graph'][n])

    def test_mapping_accounts_for_fill_and_emitted_fixture_not_current_prompt(self):
        timed=[r for r in self.plan['requests'] if r['phase']=='timed']
        self.assertEqual(len(timed),44)
        self.assertTrue(all(r['reference'] is None for r in timed[:4]))
        self.assertEqual([r['expected_emitted_index'] for r in timed[4:]],list(range(40)))
        self.assertEqual(timed[4]['fixture'],'rain')
        self.assertEqual(timed[4]['expected_emitted_fixture'],'boat')
        self.assertEqual(timed[4]['reference'],P.PREFIX+'-native-p1-boat')
        self.assertEqual(set(r['expected_emitted_fixture'] for r in timed[4:]),set(P.IDS))
        self.assertEqual(len(self.plan['comparisons']),60)

    def test_changed_geometry_or_steps_or_encoder_rejected_even_rehashed(self):
        for node,key,value in [('356','width',128),('395','sigmas','0.85,0.0'),('364','mode','original')]:
            with self.subTest(node=node):
                self.reject_changed_plan(lambda p: p['requests'][0]['graph'][node]['inputs'].__setitem__(key,value))

    def test_candidate_cannot_become_reference(self):
        self.reject_changed_plan(lambda p:p['reference_names'].__setitem__('boat',P.PREFIX+'-candidate-check-04'))
        self.reject_changed_plan(lambda p:p['comparisons'][-1].__setitem__('reference',p['comparisons'][-1]['candidate']))

    def test_missing_tensor_or_speed_only_claim_or_qualification_refused(self):
        self.reject_changed_plan(lambda p:p['comparison_tensors'].remove('waveform'))
        self.reject_changed_plan(lambda p:p.__setitem__('runtime_qualified',True))
        self.reject_changed_plan(lambda p:p['requests'][-1]['graph']['428']['inputs'].__setitem__('speed_only',True))

    def test_hash_duplicate_keys_and_bad_source_fail_closed(self):
        e=P.envelope(self.plan);e['plan_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Plan hash'):P.validate_envelope(e,self.plan)
        with self.assertRaisesRegex(ValueError,'Duplicate'):P.strict_json('{"x":1,"x":2}')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'manifest.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'manifest differs'):P.load_inputs(root,P.FIXTURES)
            source=root/'data.json';source.write_text('{}');link=root/'link.json';link.symlink_to(source)
            with self.assertRaisesRegex(ValueError,'Unsafe'):P.regular(link)

    def test_actual_run_ahead_returns_current_conditioning_not_previous(self):
        # Execute the real pinned function body, without importing Torch or spawning workers.
        raw=P.regular(P.PACKET/'source/scripts/ltx_pipeline.py')
        manifest=P.strict_json(P.regular(P.PACKET/'manifest.json'))
        self.assertEqual(P.digest(raw),manifest['files']['source/scripts/ltx_pipeline.py'])
        node=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name=='run_ahead')
        jobs={}; calls=[]; own=object(); previous=object()
        def submit(stage,index,fn,tag):
            calls.append(('submit',index,tag))
            if index in jobs:return False
            jobs[index]=(fn(),tag);return True
        def collect(stage,index,tag):
            value,actual=jobs.pop(index);calls.append(('collect',index,tag))
            return (value if actual==tag else None),{'speculation_miss':actual!=tag}
        env={'require':P.require,'MAX_PENDING':4,'submit':submit,'collect':collect,
             'pending':lambda stage:sorted(jobs),'time':time}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<pinned run_ahead>','exec'),env)
        for index in (99900000,99900001):
            value,detail=env['run_ahead']('encode',index,2,lambda:own,tag='own-text',lookahead=lambda i:None)
            self.assertIs(value,own);self.assertEqual(detail['started_ahead'],[])
            self.assertFalse(detail['speculation_miss']);self.assertEqual(detail['pending_after'],[])
            self.assertEqual(calls[-2:],[('submit',index,'own-text'),('collect',index,'own-text')])
        jobs[99900002]=(previous,'other-text')
        value,detail=env['run_ahead']('encode',99900002,2,lambda:own,tag='own-text',lookahead=lambda i:None)
        self.assertIs(value,own);self.assertTrue(detail['speculation_miss'])
        # Native reference contract refuses speculation_miss, even though helper recomputes correctly.
        with self.assertRaisesRegex(ValueError,'depth'):
            env['run_ahead']('encode',99900003,0,lambda:own,tag='own-text',lookahead=lambda i:None)

    def test_graph_cycle_and_missing_edge_refused(self):
        graph=copy.deepcopy(self.plan['requests'][0]['graph'])
        graph['344']['inputs']['latent_image']=['344',0]
        with self.assertRaisesRegex(ValueError,'cycle'):P.validate_graph_edges(graph)
        graph['344']['inputs']['latent_image']=['999',0]
        with self.assertRaisesRegex(ValueError,'edge'):P.validate_graph_edges(graph)

    def test_all_seeds_prompts_shapes_and_unique_names(self):
        fixtures={f['id']:f for f in self.fixtures}
        self.assertEqual([fixtures[f]['seed'] for f in P.IDS],[42,17,123,271,314,519,808,1201,2026,4096])
        for row in self.plan['requests']:
            f=fixtures[row['fixture']];g=row['graph']
            self.assertEqual(g['364']['inputs']['text'],f['prompt'])
            for n in ('338','339'):self.assertEqual(g[n]['inputs']['noise_seed'],f['seed'])
            self.assertEqual(P.digest(P.canonical(g)),row['graph_sha256'])
        self.assertEqual(len({r['name'] for r in self.plan['requests']}),78)
        self.assertEqual(len({r['clip_index'] for r in self.plan['requests']}),78)
        self.assertEqual(self.plan['expected_shapes']['images'],[25,384,640,3])


if __name__ == '__main__':
    unittest.main(verbosity=2)
