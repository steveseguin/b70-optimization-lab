"""Synthetic CPU receipts emitted by the real trace state machine; no devices/actions."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

G = load('transport_gate_tested', HERE / 'transport_gate.py')
# Reuse only the existing fake event/stream driver, never model/runtime code.
F = load('transport_fake_event_driver', HERE.parent / '20261007-sparse-transport107-runtime/test_trace.py')
PLAN = HERE.parent / '20261007-sparse-transport107-plan/candidate-plan.json'


class TransportGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads(PLAN.read_bytes())['plan']['requests']
        fixture = F.Tests(); fixture.setUp()
        fixture.identity['plan_sha256'] = json.loads(PLAN.read_bytes())['plan_sha256']
        fixture.manager.identity = copy.deepcopy(fixture.identity)
        observations = {}
        snapshots = {}
        for phase in ('candidate-check', 'timed-fast'):
            observations[phase] = []
            for ordinal, row in enumerate(r for r in cls.rows if r['phase'] == phase):
                worker = ordinal % 2
                binding = fixture.workers[worker]
                fixture.thread[:] = [binding['ident'], binding['name']]
                job = fixture.manager.begin_job(row['clip_index'], worker, phase)
                if job.selected:
                    fixture.full_job(job)
                fixture.backend.drained = True
                receipt = job.finish_after_existing_drains(True)
                fixture.manager.clear()
                observations[phase].append({'clip_index': row['clip_index'],
                    'sample_inputs': {'guider_a_conds': {'sha256': 'a'*64},
                        'guider_b_conds': {'sha256': 'b'*64}, 'noise_seeds': [42, 42],
                        'video_latent': {'sha256': 'c'*64}, 'audio_latent': {'sha256': 'd'*64}},
                    'sample_output': {'video_finite': True, 'audio_finite': True,
                        'video_sha256': 'e'*64, 'audio_sha256': 'f'*64,
                        'video_ptr': 1000+ordinal, 'audio_ptr': 2000+ordinal},
                    'trace_receipt': receipt})
            snapshots[phase] = fixture.manager.close_candidate() if phase == 'candidate-check' else fixture.manager.snapshot()
        cls.fixtures = (snapshots, observations, fixture.identity)

    def fixture(self, phase='candidate-check'):
        snapshots, observations, identity = copy.deepcopy(self.fixtures)
        return snapshots[phase], observations[phase], copy.deepcopy(self.rows), identity, phase

    def valid(self, values):
        before = copy.deepcopy(values)
        result = G.check(*values)
        self.assertEqual(values, before, 'Gate mutated caller evidence')
        self.assertTrue(result['valid'], result['errors'])
        self.assertNotIn('model_quality_passed', result)
        self.assertLess(len(G.canonical(result)), G.MAX_RECEIPT_BYTES)
        return result

    def invalid(self, values):
        result = G.check(*values)
        self.assertFalse(result['valid'], 'Malformed diagnostic was accepted')
        self.assertTrue(result['errors'])
        self.assertNotIn('model_quality_passed', result)
        return result

    def test_real_trace_schema_two_workers_complete_and_timed_no_events(self):
        for phase in ('candidate-check', 'timed-fast'):
            values = self.fixture(phase); result = self.valid(values)
            self.assertEqual(len(result['sampler_observations']), 14)
            self.assertEqual(set(values[0]['claims']), {0, 1})
            self.assertEqual([r['events_recorded'] for r in values[0]['receipts'].values()], [232, 232])
            # JSON serialization changes worker map keys to strings.
            values = json.loads(json.dumps(values)); self.valid(values)

    def test_thirteen_actual_jobs_tail12_without_unexecuted_submission13(self):
        for phase in ('candidate-check', 'timed-fast'):
            with self.subTest(phase=phase):
                args = self.fixture(phase)
                omitted = args[1].pop()
                self.assertFalse(omitted['trace_receipt']['selected'])
                index = omitted['clip_index']
                args[0]['jobs'] = [j for j in args[0]['jobs']
                    if (j['phase'], j['clip_index']) != (phase, index)]
                key = phase + ':' + omitted['trace_receipt']['disabled_reason']
                args[0]['disabled_counts'][key] -= 1
                result = self.valid(args)
                self.assertEqual(len(result['sampler_observations']), 13)
                self.assertEqual(result['sampler_observations'][-1]['clip_index'], index-1)
                self.assertEqual(len([r for r in args[2] if r['phase']==phase]), 14)

    def test_identity_phase_closed_and_active_refusal(self):
        for key, value in [('schema', 'wrong'), ('identity', {}), ('candidate_closed', False),
                           ('active_jobs', 1), ('binding_failures', 1), ('audit_error', 'fault')]:
            with self.subTest(key=key):
                args = self.fixture(); args[0][key] = value; self.invalid(args)
        args = list(self.fixture()); args[-1] = 'timed-control'; self.invalid(args)

    def test_both_workers_and_complete_stages_required(self):
        for mutate in (lambda s: s['receipts'].pop(1), lambda s: s['claims'].pop(1),
                       lambda s: s.update(complete=False),
                       lambda s: s['receipts'][0]['coverage']['b'].update(blocks=47),
                       lambda s: s['receipts'][0].update(valid=False, error='incomplete')):
            args = self.fixture(); mutate(args[0]); self.invalid(args)

    def test_duplicate_jobs_observations_and_missing_scored_producer(self):
        args = self.fixture(); args[0]['jobs'].append(copy.deepcopy(args[0]['jobs'][0])); self.invalid(args)
        args = self.fixture(); args[1].append(copy.deepcopy(args[1][0])); self.invalid(args)
        args = self.fixture(); index = args[1][0]['clip_index']
        args[0]['jobs'] = [r for r in args[0]['jobs'] if r['clip_index'] != index]
        args[1].pop(0); self.invalid(args)

    def test_async_tail_missing_on_either_side_is_not_hidden_by_ten_scored_clips(self):
        for phase in ('candidate-check', 'timed-fast'):
            args = self.fixture(phase); last = args[1][-1]['clip_index']
            self.assertGreater(last, min(r['clip_index'] for r in args[1])+9)
            args[0]['jobs'] = [r for r in args[0]['jobs'] if r['clip_index'] != last]
            self.invalid(args)
            args = self.fixture(phase); args[1].pop(); self.invalid(args)
            for key in ('sample_inputs', 'sample_output', 'trace_receipt'):
                args = self.fixture(phase); args[1][-1][key] = None; self.invalid(args)

    def test_physical_worker_and_thread_binding(self):
        for key, value in [('clip_index', 123), ('worker_index', 7), ('thread_ident', 333),
                           ('thread_name', 'other'), ('finished', False), ('existing_drains_succeeded', False)]:
            args = self.fixture(); args[0]['jobs'][0][key] = value; self.invalid(args)
        args = self.fixture(); args[0]['workers'][1]['ident'] = args[0]['workers'][0]['ident']; self.invalid(args)
        args = self.fixture(); args[0]['claims'][0] = 99907109; self.invalid(args)

    def test_timed_events_even_in_uncollected_tail_refused(self):
        args = self.fixture('timed-fast'); args[0]['phase_events']['timed-fast'] = 2; self.invalid(args)
        args = self.fixture('timed-fast'); args[0]['jobs'][-1]['events_recorded'] = 2; self.invalid(args)
        args = self.fixture('timed-fast'); args[1][-1]['trace_receipt']['operation_count'] = 1; self.invalid(args)
        args = self.fixture('timed-fast'); args[0]['jobs'][-1]['selected'] = True; self.invalid(args)
        args = self.fixture('timed-fast'); args[2][-1]['trace_enabled'] = True; self.invalid(args)

    def test_original_sentry_entries_not_just_empty_dict_required(self):
        for key in ('guider_a_conds','guider_b_conds','noise_seeds','video_latent','audio_latent'):
            args = self.fixture(); args[1][0]['sample_inputs'].pop(key); self.invalid(args)
        for key in ('video_finite','audio_finite','video_sha256','audio_sha256'):
            args = self.fixture(); args[1][0]['sample_output'].pop(key); self.invalid(args)

    def test_malformed_counter_types_refused(self):
        for key in ('active_jobs', 'binding_failures'):
            for value in (False, 0.0, '0'):
                args = self.fixture(); args[0][key] = value; self.invalid(args)
        args = self.fixture('timed-fast'); args[0]['phase_events']['timed-fast'] = False; self.invalid(args)
        args = self.fixture(); args[0]['workers']['00'] = args[0]['workers'].pop(0); self.invalid(args)

    def test_operation_event_routes_and_selected_thread_identity(self):
        for mutate in (lambda r: r.update(thread_ident=999),
                       lambda r: r['operations'][0].update(event_devices=['unknown']*2),
                       lambda r: r['operations'][0].update(forward_ordinal=1),
                       lambda r: r['operations'][0].update(elapsed_ms=[-1]),
                       lambda r: r['operations'][0].update(recorded_indices=[])):
            args = self.fixture(); receipt = args[0]['receipts'][0]; mutate(receipt)
            index = receipt['clip_index']
            next(o for o in args[1] if o['clip_index']==index)['trace_receipt'] = copy.deepcopy(receipt)
            self.invalid(args)

    def test_malformed_top_level_is_invalid_without_action_or_exception(self):
        for value in (None, [], {}, 'bad'):
            args = list(self.fixture()); args[0] = value; self.invalid(args)
        for value in (None, {}, 'bad'):
            args = list(self.fixture()); args[1] = value; self.invalid(args)


if __name__ == '__main__':
    unittest.main()
