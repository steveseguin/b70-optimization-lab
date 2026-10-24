"""Read only completed CPU fixture artifacts; no compiler, owner or device calls."""
import hashlib,json
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1];ROOT=P.parents[3]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
class Authority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build=read(P/'evidence/cpu-build.json');cls.schedule=read(P/'evidence/schedule-proof.json');cls.transition=read(P/'evidence/transition-proof.json')
    def test_compiled_source_and_reused_host_objects_exact(self):
        b=self.build;self.assertTrue(b['passed']);self.assertFalse(b['native_executed'] or b['device_executed'] or b['model_executed'])
        for group in ('source_sha256','parent_bindings'):
            for path,want in b[group].items():self.assertEqual(sha(ROOT/path),want,path)
        for plan in b['plans']:
            self.assertEqual(plan['compile_returncode'],0);self.assertEqual(plan['run_returncode'],0)
            self.assertEqual(sha(ROOT/plan['binary']),plan['binary_sha256'])
            for path,want in plan['repository_dependencies'].items():self.assertEqual(sha(ROOT/path),want,path)
            for path,want in plan['object_sha256'].items():self.assertEqual(sha(path),want,path)
            self.assertEqual(sha(P/'evidence'/f"{plan['name']}-proof.json"),plan['proof_sha256'])
        schedule,transition=b['plans'];self.assertEqual(schedule['object_sha256'],{})
        expected=read(P.parent/'packet210-host-cache-chunk/production-binding.json')['object_sha256'];self.assertEqual(transition['object_sha256'],expected)
        self.assertIn('-DOWN_RT_HOST_ONLY',transition['compile_command']);self.assertNotIn('-fsycl',transition['compile_command'])
    def test_actual_plan_chains_and_pair_substitution(self):
        inp=read(P.parent/'packet212-production-prefill-integration/schedule-inputs.json');old=read(P.parent/'packet212-production-prefill-integration/evidence/schedule-proof.json')
        self.assertEqual(len(inp['sites']),1486)
        expected=list(range(1479));a,b=self.schedule['modes'];self.assertEqual(a['steps'],[[i,r,0] for r in (0,1) for i in expected])
        self.assertEqual(len(b['steps']),2888);self.assertEqual(sum(s[2] for s in b['steps']),70)
        self.assertEqual(b['steps'],[[e['site'],2 if e['kind']=='pair' else e['row'],int(e['kind']=='pair')] for e in old['events']])
        for row in (0,1):self.assertEqual([i for i,r,pair in b['steps'] if pair or r==row],expected)
        self.assertTrue(all(self.schedule['checks'].values()));self.assertEqual(len(self.schedule['checks']),38)
    def test_chronology_same_and_complete(self):
        expected=[layer*512+(row*23+layer*31+slot*7)%512 for row in range(2) for layer in range(48) for slot in range(10)]
        self.assertEqual(self.schedule['chronological_routes'],expected)
        self.assertTrue(self.schedule['checks']['wrong_row_replay_discriminates'])
    def test_actual_cache_failures_preserve_first_error_and_poison(self):
        p=self.transition;self.assertEqual(p['first_errors'],{'before_prepare':'injected before prepare','prepare_refusal':'route outside expert table','prepared_copy_failure':'copy extent/lifetime','publication_commit_refusal':'new device table has not passed its publication fence','postcommit_stats_failure':'injected stats save failure'})
        for name in p['first_errors']:
            for suffix in ('phase_tracks_actual_cache','first_error_retained','secondary_does_not_replace','poison_intake_closed','incomplete_drain_no_transition','closed_without_success','closed_cache_refuses_access'):
                self.assertTrue(p['checks'][name+'_'+suffix])
        for name in ('prepare_refusal','publication_commit_refusal'):self.assertTrue(p['checks'][name+'_wrapper_autopoison_before_caller'])
        self.assertTrue(p['checks']['chunk_tail_next_chunk_epochs_advance'])
        self.assertEqual(len(p['checks']),50);self.assertTrue(all(p['checks'].values()))
    def test_actual_copies_pending_retention_and_safe_teardown(self):
        p=self.transition
        for name in ('actual_fill_bytes_exact','actual_table_publication_exact','pending_marker_actual_owner_inflight','pending_marker_close_retains_phase','pending_marker_payload_and_table_release_refused','pending_marker_both_allocations_live','pending_marker_completed_cleanup_preserves_failure'):self.assertTrue(p['checks'][name])
        self.assertEqual(len(p['owner_receipts']),7)
        for name,r in p['owner_receipts'].items():
            self.assertEqual(r['backend'],'MockDevice');self.assertTrue(r['safe_to_exit'] and r['idle_marker_complete']);self.assertEqual(r['live_bytes'],0);self.assertEqual(r['in_flight'],0)
            sequence=r['sequence'];self.assertLess(sequence.index('drain'),sequence.index('queue-released'));self.assertLess(sequence.index('queue-released'),sequence.index('context-released'))
        self.assertIn('simulated',p['completion_scope'])
    def test_actual_engine_hooks_and_shared_noexcept_controller(self):
        main=(P/'build/native/main.cpp').read_text();runtime=(P/'production_runtime.hpp').read_text();control=(P/'cache_transition.hpp').read_text();interval=(P/'cache_interval.hpp').read_text()
        for token in ('else cache_epoch=p213_cache_begin();','auto epoch=p213_cache_begin();p213_cache_finish(epoch,true);','else p213_cache_finish(cache_epoch,true);','auto plan=p213_cache_prepare(routes);','p213_cache_commit(plan.epoch,true,true);'):self.assertIn(token,main)
        for token in ('schedule=build_schedule(sites,tensors);','ordered_steps(schedule,mode)'):self.assertIn(token,runtime)
        for token in ('after_prepare()noexcept','after_commit()noexcept','std::is_nothrow_move_constructible_v<p58::Plan>','std::is_nothrow_move_assignable_v<p58::Plan>','if(!drained)return false;'):self.assertIn(token,control)
        self.assertIn('transitions.prepare(cache,routes)',interval);self.assertIn('transitions.commit(cache,value,copies_complete,publication_complete)',interval)
        self.assertNotIn('bool active=false,updating=',interval)
    def test_failed_attempts_keep_exact_sources_and_diagnosis(self):
        failed=[]
        for f in sorted((P/'evidence').glob('cpu-*/receipt.json')):
            r=read(f)
            if r['passed']:continue
            failed.append(r)
            for path,want in r['source_sha256'].items():self.assertEqual(sha(f.parent/Path(path).name),want)
            self.assertTrue((f.parent/'failure.log').is_file())
        self.assertEqual(len(failed),2)
        self.assertEqual(failed[0]['plans'][0]['compile_returncode'],1)
        self.assertEqual(failed[1]['plans'][0]['run_returncode'],0)
        self.assertEqual(failed[1]['plans'][1]['run_returncode'],-6)
if __name__=='__main__':unittest.main()
