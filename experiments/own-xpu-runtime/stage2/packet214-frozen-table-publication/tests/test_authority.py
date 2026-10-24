"""Read-only retained publication fixture/source checks; never launches an owner."""
import hashlib,json
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1];ROOT=P.parents[3]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
class Authority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.build=read(P/'evidence/cpu-build.json');cls.proof=read(P/'evidence/publication-proof.json')
    def test_actual_cpu_source_objects_and_output_pins(self):
        b=self.build;self.assertTrue(b['passed']);self.assertFalse(b['native_executed'] or b['device_executed'] or b['model_executed']);self.assertEqual(b['compile_returncode'],0);self.assertEqual(b['run_returncode'],0)
        for group in ('source_sha256','repository_dependencies','parent_bindings'):
            for path,want in b[group].items():self.assertEqual(sha(ROOT/path),want,path)
        for path,want in b['object_sha256'].items():self.assertEqual(sha(path),want,path)
        self.assertEqual(b['object_sha256'],read(P.parent/'packet210-host-cache-chunk/production-binding.json')['object_sha256'])
        self.assertEqual(sha(ROOT/b['binary']),b['binary_sha256']);self.assertEqual(sha(P/'evidence/publication-proof.json'),b['proof_sha256'])
        self.assertIn('-DOWN_RT_HOST_ONLY',b['compile_command']);self.assertNotIn('-fsycl',b['compile_command'])
    def test_full_table_geometry_generations_and_actual_consumers(self):
        p=self.proof;self.assertEqual(p['geometry'],{'tables':144,'entries_per_table':512,'entry_bytes':16,'publication_bytes':1179648})
        for generation in (1,2):
            for stem in ('full_table_exact_generation','transfer_shape_generation','actual_prepared_pointer_consumers_generation'):self.assertTrue(p['checks'][stem+str(generation)])
        self.assertNotEqual(p['byte_sha256']['generation1'],p['byte_sha256']['generation2']);self.assertTrue(p['checks']['fixed_destinations_ignore_caller_array_decoys'])
    def test_refusals_and_immediate_operation_identity(self):
        checks=self.proof['checks']
        for name in ('duplicate_destination_refused','wrong_logical_destination_refused','staging_publication_alias_refused','publication_destination_alias_refused','short_actual_staging_extent_refused','short_actual_destination_extent_refused','short_input_table_refused','zero_generation_refused','zero_pointer_refused','readers_active_publication_refused','released_storage_refuses_publication','capture_refused_before_publish_operation'):self.assertTrue(checks[name],name)
        source=(P/'publication.hpp').read_text();self.assertIn('require(!d.capturing()',source);self.assertIn('d.compute(static_cast<const ownrt::Operation&>(op),kernel_ids,{})',source);self.assertNotIn('begin_capture(',source)
    def test_known_pending_event_and_hidden_preledger_work_distinct(self):
        checks=self.proof['checks']
        for name in ('tracked_pending_owner_event','pending_refuses_restage','tracked_event_raw_allocator_release_guard','pending_close_retains_storage','tracked_completion_allows_safe_cleanup','hidden_marker_not_device_ledger','hidden_work_sync_failure_retains','hidden_work_all_storage_live','hidden_work_restage_refused','hidden_work_blocks_cache_release','actual_backend_sync_then_release','hidden_error_preserved_after_cleanup'):self.assertTrue(checks[name],name)
        self.assertEqual(self.proof['first_errors']['hidden_backend_submission'],'injected hidden backend submission failure')
        self.assertIn('simulated',self.proof['scope']);self.assertIn('not native DMA proof',self.proof['scope'])
    def test_real_partial_publication_poison_and_original_error(self):
        p=self.proof;self.assertEqual(p['first_errors']['partial_publication'],'copy extent/lifetime')
        self.assertNotEqual(p['byte_sha256']['partial_before'],p['byte_sha256']['partial_after'])
        for name in ('partial_publication_first_table_changed','partial_publication_remaining_tables_unchanged','partial_publication_poison_no_commit','partial_publication_sync_cleanup_safe','partial_publication_failed_cache_close_not_success'):self.assertTrue(p['checks'][name])
    def test_safe_closed_cpu_owners_no_native_claim(self):
        p=self.proof;self.assertTrue(p['passed'] and all(p['checks'].values()));self.assertFalse(p['device_executed'] or p['native_executed'] or p['model_executed']);self.assertEqual(len(p['owner_receipts']),7)
        for r in p['owner_receipts'].values():
            self.assertEqual(r['backend'],'MockDevice');self.assertTrue(r['safe_to_exit'] and r['idle_marker_complete']);self.assertEqual(r['live_bytes'],0);self.assertEqual(r['in_flight'],0)
            order=r['sequence'];self.assertLess(order.index('drain'),order.index('queue-released'));self.assertLess(order.index('queue-released'),order.index('context-released'))
    def test_generated_engine_guards_and_borrowed_backend_cleanup(self):
        main=(P/'build/native/main.cpp').read_text();helper=(P/'publication.hpp').read_text()
        for token in ('publication_backend=owned_publication_backend.get();','std::move(owned_publication_backend)','table_publisher->ready()','table_publisher->close(std::chrono::seconds(a.wait_seconds))&&table_publisher->release_allowed()','ownrt::hold_for_supervisor();','table_publisher.reset();publication_backend=nullptr;'):self.assertIn(token,main)
        for signature in ('void release(int c,Allocation id)','void upload(int c, Allocation dst','void prepare_commands()','void guard()','static void p58_reset_request('):
            begin=main.index(signature);self.assertIn('table_publisher->ready()',main[begin:begin+420])
        self.assertIn('backend.synchronize();',helper);self.assertIn('closed_&&!uncertain_&&!pending()',helper)
        self.assertLess(helper.index('uncertain_=true;\n#ifdef OWN_RT_HOST_ONLY'),helper.index('auto event=d.compute('))
        # Source drift guards only; native shutdown was not executed.
if __name__=='__main__':unittest.main()
