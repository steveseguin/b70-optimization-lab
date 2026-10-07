"""CPU-only campaign identity/gate and extraction-calibration regressions."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import campaign
import extraction
from pilot import StubClient, ARMS, grade
from tasks import make_task, encoded


class FixtureClient(StubClient):
    kind = 'model'  # Test double only: no network/model invocation.
    model = 'fixture-model'
    endpoint = 'http://127.0.0.1:9999/v1'

    def __init__(self, task, mode='correct'):
        super().__init__(task); self.mode = mode

    def __call__(self, messages, phase, batch_id):
        events = copy.deepcopy(self.task['oracle']['events'][batch_id-1])
        if self.mode == 'reverse': events.reverse()
        if self.mode == 'float':
            for event in events: event['amount'] = float(event['amount'])
        if self.mode == 'malformed': events = [None]
        if self.mode == 'fail': raise RuntimeError('injected client failure')
        return json.dumps({'events': events}), {}


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='campaign-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.suite_path = self.root / 'suite.json'
        self.tasks = [make_task(seed=seed, batches=48, filler_words=320, style=style)
                      for seed in (17, 29) for style in ('report', 'dispatch')]
        rows = []
        for task in self.tasks:
            path = self.root / (task['style'] + '-seed' + str(task['seed']) + '.json')
            path.write_text(json.dumps(task))
            rows.append({'path': path.name, 'task_sha256': task['task_sha256'],
                         'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        self.suite_path.write_text(json.dumps({'cases': rows, 'arms': list(ARMS)}))
        self.frozen = campaign.plan(self.suite_path)
        lock = patch.object(campaign, 'endpoint_lock_path', return_value=self.root / 'endpoint.lock')
        lock.start(); self.addCleanup(lock.stop)

    def result(self, item, *, kind='model', identity=None):
        task=next(t for t in self.tasks if t['task_sha256']==item['task_sha256'])
        answers=copy.deepcopy(task['oracle']['answers'])
        return {'schema':'durable-pilot-run.v4','protocol':campaign.PROTOCOL,
                **campaign.generation_identity(),
                'max_retrieval':24,'max_answer_calls':32,'answer_protocol_completed':True,'processed_batches':48,
                'answer_protocol':{'calls':1,'retrievals':0},
                'calls':1,'cache_usage':{'complete':True,'cached_tokens':0,'calls':1},
                'status': 'completed', 'task_sha256': item['task_sha256'], 'arm': item['arm'],
                'answers':answers,'score': grade(task,answers), 'measurement_kind': kind,
                'timing_complete': True, 'resumed': False,
                'wall_seconds_this_session': 8 if item['arm'] == 'quoted' else 10,
                'source_sha256': self.frozen['source_sha256'], 'server_identity': identity,
                'context_limit_utf8_bytes': self.frozen['context_limit_utf8_bytes']}

    def fake_run(self, task, arm, out, client, limit, identity=None):
        return self.result({'task_sha256': task['task_sha256'], 'arm': arm},
                           kind=client.kind, identity=identity)

    def test_complete_matrix_qualifies_only_for_clean_model_timing(self):
        results = [self.result(item) for item in self.frozen['runs']]
        summary = campaign.summarize(results, self.frozen['runs'])
        self.assertTrue(summary['quality_gate_passed'])
        self.assertTrue(summary['single_server_speed_signal'])
        self.assertFalse(summary['speed_gate_passed'])
        self.assertEqual(summary['median_quoted_over_archive_elapsed_ratio'], .8)
        self.assertFalse(campaign.summarize(results, self.frozen['runs'], campaign_clean=False)['single_server_speed_signal'])
        results[1]['timing_complete'] = False
        self.assertFalse(campaign.summarize(results, self.frozen['runs'])['single_server_speed_signal'])

    def test_primary_pair_can_pass_with_inaccurate_summary_but_every_trial_is_required(self):
        results = [self.result(item) for item in self.frozen['runs']]
        for result in results:
            if result['arm'] == 'summary':
                result['score']['correct'] = 22
        summary = campaign.stage_summary(results, self.frozen, True, 'completed')
        self.assertTrue(summary['development_gate_passed'])
        self.assertTrue(summary['primary_quality_gate_passed'])
        self.assertFalse(summary['all_arms_quality_gate_passed'])
        self.assertTrue(summary['single_server_speed_signal'])
        self.assertFalse(summary['speed_gate_passed'])
        incomplete = [r for r in results if r['arm'] != 'summary']
        self.assertFalse(campaign.summarize(incomplete, self.frozen['runs'])['primary_quality_gate_passed'])
        self.assertFalse(campaign.summarize(incomplete)['primary_quality_gate_passed'])
        next(r for r in results if r['arm'] == 'quoted')['score']['correct'] = 23
        self.assertFalse(campaign.stage_summary(results, self.frozen, True, 'completed')['development_gate_passed'])

    def test_cache_evidence_is_recomputed_and_missing_or_invalid_counters_block_timing(self):
        results = [self.result(item) for item in self.frozen['runs']]
        result = next(r for r in results if r['arm'] == 'archive')
        path = self.root/'cache-calls.jsonl'
        for cached in (0, 4, None, True, -1, 101):
            details = {} if cached is None else {'cached_tokens': cached}
            row = {'usage': {'prompt_tokens': 100, 'prompt_tokens_details': details}}
            path.write_text(json.dumps(row)+'\n')
            complete = type(cached) is int and 0 <= cached <= 100
            result['cache_usage'] = {'complete': complete, 'cached_tokens': cached if complete else None, 'calls': 1}
            record = campaign.verify_cache_log(result, path)
            self.assertEqual(record['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            summary = campaign.summarize(results, self.frozen['runs'])
            self.assertEqual(summary['timing_eligible'], cached == 0 and type(cached) is int)
            self.assertTrue(summary['primary_quality_gate_passed'])
            if not summary['timing_eligible']:
                self.assertIsNone(summary['median_quoted_over_archive_elapsed_ratio'])
            result['cache_usage'] = {'complete': True, 'cached_tokens': 0, 'calls': 1}
            if cached != 0:
                with self.assertRaisesRegex(ValueError, 'aggregate'):
                    campaign.verify_cache_log(result, path)
        result['cache_usage'] = {'complete': 1, 'cached_tokens': 0, 'calls': 1}
        with self.assertRaisesRegex(ValueError, 'aggregate'):
            campaign.verify_cache_log(result, path)

    def test_native_development_keeps_summary_failures_and_binds_raw_cache_logs(self):
        directory, identity = self.development_fixture()
        results = []
        for path in directory.glob('*/result.json'):
            result = json.loads(path.read_text())
            if result['arm'] == 'summary':
                result['answers']['current-0'] += 1
                task = campaign.stage_tasks('development')[result['task_sha256']]
                result['score'] = grade(task, result['answers'])
                path.write_text(json.dumps(result))
            results.append(result)
        (directory/'summary.json').write_text(json.dumps(campaign.stage_summary(results, self.frozen, True, 'completed')))
        evidence = campaign.validate_development(directory, self.frozen, identity)
        self.assertEqual(sum(r['path'].endswith('calls.jsonl') for r in evidence), 12)
        raw = next(directory.glob('*-archive/calls.jsonl'))
        raw.write_text(json.dumps({'usage': {'prompt_tokens': 100, 'prompt_tokens_details': {'cached_tokens': 1}}})+'\n')
        with self.assertRaisesRegex(ValueError, 'aggregate'):
            campaign.validate_development(directory, self.frozen, identity)

    def test_summary_cache_hits_or_unknown_counts_block_development_and_timing(self):
        for cache in ({'complete': True, 'cached_tokens': 1, 'calls': 1},
                      {'complete': False, 'cached_tokens': None, 'calls': 1}):
            results = [self.result(item) for item in self.frozen['runs']]
            next(r for r in results if r['arm'] == 'summary')['cache_usage'] = cache
            summary = campaign.stage_summary(results, self.frozen, True, 'completed')
            self.assertTrue(summary['primary_quality_gate_passed'])
            self.assertFalse(summary['development_gate_passed'])
            self.assertFalse(summary['timing_eligible'])
            self.assertIsNone(summary['median_quoted_over_archive_elapsed_ratio'])

    def test_partial_unpaired_or_duplicate_matrix_cannot_qualify(self):
        results = [self.result(item) for item in self.frozen['runs']]
        for bad in (results[:-1], results + results[:1], copy.deepcopy(results)):
            if len(bad) == len(results): bad[-1]['task_sha256'] = 'different-task'
            summary = campaign.summarize(bad, self.frozen['runs'])
            self.assertFalse(summary['complete_planned_matrix'])
            self.assertFalse(summary['quality_gate_passed'])
            self.assertFalse(summary['speed_gate_passed'])
            self.assertIsNone(summary['median_quoted_over_archive_elapsed_ratio'])

    def test_stub_or_wrong_answer_or_nonfinite_time_cannot_pass(self):
        for mutate in (lambda r: r.update(measurement_kind='stub'),
                       lambda r: r['score'].update(correct=23),
                       lambda r: r.update(wall_seconds_this_session=float('nan'))):
            results = [self.result(item) for item in self.frozen['runs']]
            mutate(next(r for r in results if r['arm']=='archive'))
            self.assertFalse(campaign.summarize(results, self.frozen['runs'])['single_server_speed_signal'])

    def test_self_consistent_task_edit_is_not_a_frozen_task(self):
        path = self.root / self.frozen['runs'][0]['task']
        task = json.loads(path.read_text()); task['batches'][0]['text'] += ' Edited.'
        del task['task_sha256']; task['task_sha256'] = hashlib.sha256(encoded(task)).hexdigest()
        path.write_text(json.dumps(task))
        with self.assertRaisesRegex(ValueError, 'task bytes changed'):
            campaign.verify_frozen(self.frozen, self.suite_path, self.frozen['runs'][0])

    def test_source_drift_and_result_identity_drift_are_rejected(self):
        with patch.object(campaign, 'source_hashes', return_value={'changed.py': 'new'}):
            with self.assertRaisesRegex(ValueError, 'source files changed'):
                campaign.verify_frozen(self.frozen, self.suite_path, self.frozen['runs'][0])
        result = self.result(self.frozen['runs'][0]); result['source_sha256'] = {}
        with self.assertRaisesRegex(ValueError, 'source_sha256'):
            campaign.verify_result(result, self.frozen, self.frozen['runs'][0], 'model', None)

    def test_generation_policy_rejects_old_settings_missing_fields_and_wrong_types(self):
        expected = {'answer_generation': {'enable_thinking': True, 'reasoning_effort': 'medium', 'max_tokens': 8192},
                    'ingestion_generation': {'enable_thinking': False, 'max_tokens': 4096}}
        self.assertEqual(campaign.generation_identity(), expected)
        for key, value in expected.items():
            self.assertEqual(self.frozen[key], value)
        item = self.frozen['runs'][0]
        mutations = [lambda r: r.pop('answer_generation'),
            lambda r: r['answer_generation'].update(enable_thinking=False),
            lambda r: r['answer_generation'].update(enable_thinking=1),
            lambda r: r['answer_generation'].update(reasoning_effort='high'),
            lambda r: r['answer_generation'].update(max_tokens=4096),
            lambda r: r['answer_generation'].update(max_tokens=8192.0),
            lambda r: r['answer_generation'].update(unregistered=True),
            lambda r: r['ingestion_generation'].update(enable_thinking=True),
            lambda r: r['ingestion_generation'].update(enable_thinking=0),
            lambda r: r['ingestion_generation'].update(max_tokens=8192)]
        for mutate in mutations:
            result = self.result(item); mutate(result)
            with self.subTest(mutation=mutate):
                with self.assertRaisesRegex(ValueError, 'generation'):
                    campaign.verify_result(result, self.frozen, item, 'model', None)
        broken = copy.deepcopy(self.frozen); broken['answer_generation']['max_tokens'] = 4096
        with patch.object(campaign, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'generation'):
                campaign.execute(broken, self.suite_path, self.root/'bad-generation', stub=True)
            run.assert_not_called()

    def test_generation_policy_is_required_in_calibrations_and_native_development(self):
        paths, identity = self.calibration_files()
        saved = json.loads(paths[0].read_text())
        self.assertEqual(saved['ingestion_generation'], {'enable_thinking': False, 'max_tokens': 4096})
        for field in ('answer_generation', 'ingestion_generation'):
            broken = copy.deepcopy(saved); broken.pop(field); paths[0].write_text(json.dumps(broken))
            with self.assertRaisesRegex(ValueError, 'generation'):
                campaign.validate_calibration(paths, self.frozen, identity)
        paths[0].write_text(json.dumps(saved))
        directory, identity = self.development_fixture()
        sources = [directory/'plan.json', directory/'execution-identity.json',
                   next(directory.glob('*/result.json')), directory/'summary.json']
        for path in sources:
            original = json.loads(path.read_text())
            for field in ('answer_generation', 'ingestion_generation'):
                broken = copy.deepcopy(original); broken.pop(field); path.write_text(json.dumps(broken))
                with self.subTest(path=path, field=field):
                    with self.assertRaises(ValueError):
                        campaign.validate_development(directory, self.frozen, identity)
            path.write_text(json.dumps(original))

    def test_previous_revision_native_evidence_is_rejected(self):
        result = self.result(self.frozen['runs'][0]); result['schema'] = 'durable-pilot-run.v3'
        with self.assertRaisesRegex(ValueError, 'schema'):
            campaign.verify_result(result, self.frozen, self.frozen['runs'][0], 'model', None)
        result['schema'] = 'durable-pilot-run.v4'; result['protocol'] = 'durable-context-r3'
        with self.assertRaisesRegex(ValueError, 'protocol'):
            campaign.verify_result(result, self.frozen, self.frozen['runs'][0], 'model', None)

    def test_failed_attempt_is_retained_and_resume_cannot_qualify(self):
        out = self.root / 'campaign'
        with patch.object(campaign, 'run', side_effect=RuntimeError('injected failure')):
            with self.assertRaises(RuntimeError):
                campaign.execute(self.frozen, self.suite_path, out, stub=True)
        with patch.object(campaign, 'run', side_effect=self.fake_run):
            result = campaign.execute(self.frozen, self.suite_path, out, stub=True)
        history = [json.loads(line) for line in (out / 'campaign-attempts.jsonl').read_text().splitlines()]
        self.assertEqual([row['status'] for row in history], ['started', 'failed', 'started', 'completed'])
        self.assertFalse(result['campaign_clean'])
        self.assertFalse(result['speed_gate_passed'])

    def test_execution_identity_is_bound_before_resuming(self):
        out = self.root / 'identity-bound'
        with patch.object(campaign, 'run', side_effect=RuntimeError('stop')):
            with self.assertRaises(RuntimeError):
                campaign.execute(self.frozen, self.suite_path, out, stub=True)
        identity_path = out / 'execution-identity.json'
        saved = json.loads(identity_path.read_text()); saved['measurement_kind'] = 'model'
        identity_path.write_text(json.dumps(saved))
        with patch.object(campaign, 'run') as call:
            with self.assertRaisesRegex(ValueError, 'execution identity changed'):
                campaign.execute(self.frozen, self.suite_path, out, stub=True)
            call.assert_not_called()

    def calibration_files(self):
        identity = {'endpoint': FixtureClient.endpoint, 'model': FixtureClient.model, 'launch_sha256': 'fixture'}
        paths = []
        for style in ('report', 'dispatch'):
            task = make_task(seed=7, batches=48, filler_words=320, style=style)
            path = self.root / ('calibration-' + task['style'])
            extraction.diagnose(task, FixtureClient(task), path, extraction.DEVELOPMENT_INDICES, identity=identity)
            paths.append(path / 'result.json')
        return paths, identity

    def test_live_calibration_requires_both_styles_and_same_runtime(self):
        paths, identity = self.calibration_files()
        records = campaign.validate_calibration(paths, self.frozen, identity)
        self.assertEqual(len(records), 2)
        for bad_paths in (None, paths[:1], [paths[0], paths[0]]):
            with self.assertRaises(ValueError):
                campaign.validate_calibration(bad_paths, self.frozen, identity)
        changed = dict(identity, model='different')
        with self.assertRaises(ValueError):
            campaign.validate_calibration(paths, self.frozen, changed)
        data = json.loads(paths[1].read_text()); data['seed'] = 19; paths[1].write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            campaign.validate_calibration(paths, self.frozen, identity)

    def test_calibration_subset_wrong_task_budget_or_99_percent_is_rejected(self):
        paths, identity = self.calibration_files()
        original = json.loads(paths[0].read_text())
        alternatives = []
        subset = copy.deepcopy(original)
        subset['indices'] = [1, 2, 3, 4]; subset['rows'] = subset['rows'][:4]
        alternatives.append(subset)
        wrong_task = copy.deepcopy(original)
        wrong_task['task_sha256'] = make_task(seed=7, batches=48, filler_words=0)['task_sha256']
        alternatives.append(wrong_task)
        wrong_budget = copy.deepcopy(original); wrong_budget['context_limit_utf8_bytes'] = 12000
        alternatives.append(wrong_budget)
        near_exact = copy.deepcopy(original); near_exact['event_recall'] = .99
        alternatives.append(near_exact)
        for invalid in alternatives:
            with self.subTest(indices=invalid['indices'], recall=invalid['event_recall']):
                paths[0].write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):
                    campaign.validate_calibration(paths, self.frozen, identity)
        paths[0].write_text(json.dumps(original))
        self.assertEqual(len(campaign.validate_calibration(paths, self.frozen, identity)), 2)
        self.assertIn('100% exact', original['gate_policy'])

    def test_no_live_requests_before_calibration(self):
        launch = self.root / 'launch.json'; launch.write_text('{}')
        with patch.object(campaign, 'HTTPClient') as client:
            with self.assertRaisesRegex(ValueError, 'requires --calibration'):
                campaign.execute(self.frozen, self.suite_path, self.root / 'blocked',
                                 endpoint=FixtureClient.endpoint, server_identity=launch)
            client.assert_not_called()

    def test_extraction_rejects_reversed_float_and_malformed_events_without_crash(self):
        task = make_task(seed=7, batches=48, filler_words=320, style='report')
        for mode in ('reverse', 'float', 'malformed'):
            with self.subTest(mode=mode):
                result = extraction.diagnose(task, FixtureClient(task, mode), self.root / mode, [1])
                self.assertFalse(result['gate_passed'])
                self.assertEqual(result['status'], 'completed')
        self.assertFalse(json.loads((self.root / 'reverse' / 'result.json').read_text())['rows'][0]['exact_order'])

    def test_extraction_indices_budget_and_holdout_restrictions(self):
        for indices in ([], [1, 1], [0], [49], [True], ['1']):
            with self.assertRaises(ValueError):
                extraction.diagnose(self.tasks[0], FixtureClient(self.tasks[0]), self.root / 'invalid', indices)
        with self.assertRaises(ValueError):
            extraction.diagnose(self.tasks[0], FixtureClient(self.tasks[0]), self.root / 'oversize', [1], limit=99999)
        heldout = make_task(seed=19, batches=4, filler_words=0)
        with self.assertRaisesRegex(ValueError, 'development seed 7'):
            extraction.diagnose(heldout, FixtureClient(heldout), self.root / 'holdout', [1])

    def test_extraction_failure_keeps_failed_status_and_calls(self):
        out = self.root / 'failed-extraction'
        task = make_task(seed=7, batches=48, filler_words=320, style='report')
        with self.assertRaisesRegex(RuntimeError, 'injected client failure'):
            extraction.diagnose(task, FixtureClient(task, 'fail'), out, [1])
        self.assertEqual(json.loads((out / 'status.json').read_text())['status'], 'failed')
        self.assertTrue((out / 'calls.jsonl').exists())
        self.assertTrue((out / 'failures.jsonl').exists())
        self.assertFalse((out / 'result.json').exists())
        with self.assertRaises(FileExistsError):
            extraction.diagnose(task, FixtureClient(task), out, [1])

    def test_real_stub_campaign_completes_without_passing_model_gates(self):
        result = campaign.execute(self.frozen, self.suite_path, self.root / 'stub', stub=True)
        self.assertTrue(result['complete_planned_matrix'])
        self.assertFalse(result['quality_gate_passed'])
        self.assertFalse(result['speed_gate_passed'])

    def development_fixture(self):
        directory=self.root/'development-evidence';directory.mkdir()
        identity={'endpoint':FixtureClient.endpoint,'model':FixtureClient.model,'launch_sha256':'fixture'}
        def write(path,value):path.write_text(json.dumps(value))
        write(directory/'plan.json',self.frozen)
        write(directory/'execution-identity.json',{'schema':'durable-pilot-execution.v4',
            **campaign.generation_identity(),
            'protocol':campaign.PROTOCOL,'stage':'development','measurement_kind':'model',
            'server_identity':identity,
            'plan_sha256':hashlib.sha256(json.dumps(self.frozen,sort_keys=True).encode()).hexdigest()})
        (directory/'campaign-attempts.jsonl').write_text(json.dumps({'attempt':1,'status':'started'})+'\n'+
            json.dumps({'attempt':1,'status':'completed','completed':12})+'\n')
        results=[]
        for item in self.frozen['runs']:
            result=self.result(item,identity=identity);results.append(result)
            trial=directory/(Path(item['task']).stem+'-'+item['arm']);trial.mkdir()
            write(trial/'result.json',result)
            (trial/'calls.jsonl').write_text(json.dumps({'usage':{'prompt_tokens':100,'prompt_tokens_details':{'cached_tokens':0}}})+'\n')
        write(directory/'summary.json',campaign.stage_summary(results,self.frozen,True,'completed'))
        return directory,identity

    def test_full_development_verifies_twelve_native_trials_not_boolean(self):
        directory,identity=self.development_fixture()
        self.assertEqual(len(campaign.validate_development(directory,self.frozen,identity)),28)
        path=next(directory.glob('*-archive/result.json'));saved=json.loads(path.read_text())
        mutations=[lambda r:r.update(resumed=True),lambda r:r.update(answer_protocol_completed=False),
            lambda r:r.update(answer_protocol_completed=1),lambda r:r.update(processed_batches=48.0),
            lambda r:r.update(answer_protocol={'calls':33,'retrievals':0}),
            lambda r:r.update(answer_protocol={'calls':1,'retrievals':25}),
            lambda r:r.update(wall_seconds_this_session=float('nan')),
            lambda r:r.update(processed_batches=47),lambda r:r.update(protocol='durable-context-r1'),
            lambda r:r.update(source_sha256={}),lambda r:r.update(server_identity={}),
            lambda r:r['answers'].pop('current-0'),lambda r:r['answers'].update({'current-0':None}),
            lambda r:r['score'].update(correct=23)]
        for mutate in mutations:
            broken=copy.deepcopy(saved);mutate(broken);path.write_text(json.dumps(broken))
            with self.subTest(mutation=mutate):
                with self.assertRaises(ValueError):campaign.validate_development(directory,self.frozen,identity)
        path.write_text(json.dumps(saved));path.unlink()
        with self.assertRaises(FileNotFoundError):campaign.validate_development(directory,self.frozen,identity)

    def test_development_rejects_summary_tampering_failed_history_and_extra_attempts(self):
        directory,identity=self.development_fixture()
        summary=directory/'summary.json';saved=json.loads(summary.read_text())
        broken=copy.deepcopy(saved);broken['arms']['quoted']['correct']=47;summary.write_text(json.dumps(broken))
        with self.assertRaisesRegex(ValueError,'summary'):campaign.validate_development(directory,self.frozen,identity)
        summary.write_text(json.dumps(saved))
        history=directory/'campaign-attempts.jsonl';old=history.read_text()
        with history.open('a') as handle:handle.write(json.dumps({'attempt':2,'status':'started'})+'\n')
        with self.assertRaisesRegex(ValueError,'single completed'):campaign.validate_development(directory,self.frozen,identity)
        history.write_text(old)
        extra=directory/'extra-trial';extra.mkdir();(extra/'result.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'unexpected'):campaign.validate_development(directory,self.frozen,identity)

    def test_fixed_stages_refuse_old_holdout_or_reduced_development(self):
        def suite(seeds,batches=48,filler=320):
            rows=[]
            for seed in seeds:
                for style in ('report','dispatch'):
                    task=make_task(seed=seed,batches=batches,filler_words=filler,style=style)
                    path=self.root/f'{style}-{seed}.json';path.write_text(json.dumps(task))
                    rows.append({'path':path.name,'task_sha256':task['task_sha256'],
                        'file_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            path=self.root/'other-suite.json';path.write_text(json.dumps({'cases':rows,'arms':list(ARMS)}));return path
        valid=campaign.plan(suite([401,502,603]),'holdout')
        self.assertEqual(len(valid['runs']),18);self.assertEqual(valid['stage'],'holdout')
        development=campaign.plan(suite([17,29]),'development')
        self.assertEqual(len(development['runs']),12)
        self.assertEqual(development['primary_arms'],['archive','quoted'])
        self.assertEqual(development['secondary_arms'],['summary'])
        for seeds,batches,filler,stage in [([101,202,303],48,320,'holdout'),([7],4,0,'development'),
                                          ([7],48,0,'development'),([7],48,320,'development'),
                                          ([17],48,320,'development'),([401],48,320,'holdout')]:
            with self.assertRaises(ValueError):campaign.plan(suite(seeds,batches,filler),stage)

    def test_live_holdout_cannot_send_requests_without_full_development(self):
        paths,identity=self.calibration_files()
        launch=self.root/'launch.json';launch.write_text('{}')
        identity['launch_sha256']=hashlib.sha256(launch.read_bytes()).hexdigest()
        for path in paths:
            r=json.loads(path.read_text());r['server_identity']=identity;path.write_text(json.dumps(r))
        frozen=dict(self.frozen,stage='holdout')
        with patch.object(campaign,'HTTPClient') as client:
            with self.assertRaisesRegex(ValueError,'development-results'):
                campaign.execute(frozen,self.suite_path,self.root/'holdout-blocked',
                    endpoint=identity['endpoint'],model=identity['model'],server_identity=launch,calibration=paths)
            client.assert_not_called()
        partial=json.loads((self.root/'holdout-blocked/partial-summary.json').read_text())
        self.assertEqual(partial['status'],'failed');self.assertFalse(partial['quality_gate_passed'])

    def test_failure_writes_partial_summary_with_completed_trials(self):
        count=0
        def trial(*args,**kwargs):
            nonlocal count
            count+=1
            if count==2:raise RuntimeError('second trial failed')
            return self.fake_run(*args,**kwargs)
        out=self.root/'partial'
        with patch.object(campaign,'run',side_effect=trial):
            with self.assertRaises(RuntimeError):campaign.execute(self.frozen,self.suite_path,out,stub=True)
        partial=json.loads((out/'partial-summary.json').read_text())
        self.assertEqual(partial['observed_trials'],1);self.assertEqual(partial['status'],'failed')
        self.assertFalse(partial['development_gate_passed'])


if __name__ == '__main__':
    unittest.main()
