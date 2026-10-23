"""CPU-only synthetic chain tests; no runtime, model, key or network access.

The synthetic seal is admitted only by unittest.mock.patch in this process.
It cannot pass the unmodified production CLI or become a real submission.
"""
import base64
import contextlib
import copy
import io
import json
from pathlib import Path
import statistics
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import packet58_submission as S
import submission_cli


def put(e, key, value):
    raw = value if isinstance(value, bytes) else S.encoded(value)
    e.members[key] = dict(sha256=S.sha(raw), raw_base64=base64.b64encode(raw).decode(),
                          source_path=str(S.ROOT / S.CHAIN / key))
    return S.sha(raw)


def changed(e, key, change):
    value = e.read(key)
    change(value)
    return put(e, key, value)


def synthetic():
    e = S.Evidence()
    policy=json.loads((S.HERE/'record-threshold.snapshot').read_text())
    put(e,'record-threshold.json',policy)
    policy_hash=put(e,'submission-policy.json',S.POLICY)
    put(e,'sources/'+str(S.PACKET/'submission-policy.json'),S.encoded(S.POLICY))
    fixture_sha = S.sha(b'\0' * 20480)
    fixtures = {f'step{step}/layer-{layer:02}.bf16': fixture_sha for step in range(1, 9) for layer in range(48)}
    entries, tokens_by_id, inputs = [], {}, {}
    for index, pid in enumerate(S.M.PROMPT_CLASSES):
        tokens = list(range(500 + index * 128, 628 + index * 128))
        tokens_by_id[pid] = tokens
        inp = dict(tokens=[index + 1] * (87 + index))
        inputs[pid] = inp['tokens']
        prefix = 'oracle/' + pid + '/'
        inp_hash = put(e, prefix + 'input.json', inp)
        result_hash = put(e, prefix + 'result.json', dict(tokens=tokens, arithmetic=S.ARITHMETIC,
                            device_executed=False, status='token-cap'))
        val_hash = put(e, prefix + 'validation.json', dict(passed=True, fixture_hashes=fixtures))
        rec_hash = put(e, prefix + 'receipt.json', dict(verified=True, device_executed=False,
                       arithmetic=S.ARITHMETIC, binary_sha256='b' * 64, result_sha256=result_hash,
                       validation_sha256=val_hash, input_sha256=inp_hash))
        entries.append(dict(prompt_id=pid, input_bundle='fixture/' + pid,
                            input_bundle_hashes={'input.json': inp_hash}, prompt_tokens=len(inp['tokens']),
                            generated_tokens=128, oracle_receipt_sha256=rec_hash))
    for leaf in ('receipt.json', 'result.json', 'validation.json', 'input.json'):
        put(e, 'oracle/incident-retrospective-repeat/' + leaf, e.raw('oracle/incident-retrospective/' + leaf))
    manifest = dict(complete=True, arithmetic=S.ARITHMETIC, context=4096, token_cap=128,
                    suite_sha256=S.SUITE_SHA, prompts=entries)
    frozen_hash = put(e, 'frozen-manifest.json', dict(prompts=entries))
    build_hash = put(e, 'oracle-source/build-receipt.json', dict(passed=True, binary_sha256='b' * 64,
                     frozen_sources={str(S.FROZEN): frozen_hash}))
    arith_hash = put(e, 'oracle-source/arithmetic.json', dict(arithmetic=S.ARITHMETIC))
    put(e, 'oracle-source/suite_check.py', b'# Synthetic checker, no execution\n')
    binding_files = {}
    for leaf in ('build-receipt.json', 'arithmetic.json', 'suite_check.py'):
        path = str(S.AUTHORITY / leaf)
        binding_files[path] = put(e, 'binding/' + path, e.raw('oracle-source/' + leaf))
    binding_hash = put(e, 'oracle-binding.json', dict(arithmetic=S.ARITHMETIC, binary_sha256='b' * 64,
                                                    files_sha256=binding_files))
    completion = dict(passed=True, device_executed=False, arithmetic=S.ARITHMETIC, prompts=12,
                      token_cap=128, build_receipt_sha256=build_hash, arithmetic_sha256=arith_hash,
                      old_manifest_sha256=frozen_hash)
    completion['manifest_sha256'] = put(e, 'oracle/suite-manifest.json', manifest)
    completion['determinism_sha256'] = put(e, 'oracle/determinism.json', dict(passed=True,
                  first_receipt_sha256=entries[0]['oracle_receipt_sha256'],
                  repeat_receipt_sha256=entries[0]['oracle_receipt_sha256']))
    completion['kd_capture_sha256'] = put(e, 'oracle/kd-capture.json', dict(passed=True))
    completion['old_v_new_sha256'] = put(e, 'oracle/old-v-new.json', dict(passed=True))
    completion_hash = put(e, 'oracle/completion.json', completion)
    put(e, 'sources/' + str(S.PACKET / 'oracle-binding.json'), e.raw('oracle-binding.json'))
    selection_hash = put(e, 'sources/' + str(S.PACKET / 'selection.json'), dict(kernel='synthetic'))
    cpu_hash = put(e, 'gates/k1-cpu.json', dict(passed=True, device_executed=False, exact_output_sha256='c' * 64))
    e.members['artifacts/build/device/own-rt-iq3'] = dict(sha256='d' * 64, bytes=100, retention='sha256-only')
    seal = dict(passed=True, device_executed=False, arithmetic=S.ARITHMETIC, gpu_count=1, decode_mode='plain',
                runtime_revision='a' * 40, gates={'k1-cpu.json': cpu_hash},
                sources={str(S.PACKET / 'oracle-binding.json'): binding_hash,
                         str(S.PACKET / 'selection.json'): selection_hash, str(S.PACKET/'submission-policy.json'):policy_hash},
                artifacts={'build/device/own-rt-iq3': 'd' * 64})
    seal_hash = put(e, 'seal.json', seal)
    for wi, name in enumerate(S.ORDER):
        k1 = name.startswith('K1')
        mode = 'K1' if k1 else name
        scope = 'whole-host'
        for leaf in ('kernel-before.jsonl', 'kernel-window.jsonl'):
            put(e, name + '/' + leaf, b'')
        if k1:
            native = dict(passed=True, safe_to_exit=True, device_executed=True, zero_copy_supported=True,
                          zero_copy_bytes_equal=True, mixed_bytes_equal=True, streamed_bytes_equal=True,
                          cold_rotation=True, exact_output_sha256='c' * 64, working_set_bytes=256 * 1024**2,
                          bytes_per_iteration=32_000_000, host_ms=1, vram_ms=1, streamed_ms=2)
            put(e, name + '/run/k1.json', native)
            put(e, name + '/summary.json', native)
        else:
            cap = 8 if name in ('KD', 'W2m') else 128
            retain = '1-8' if name in ('KD', 'W2m', 'WS') else 'none'
            native = dict(passed=True, safe_to_exit=True, device_executed=True, owner_cards=1,
                          arithmetic=S.ARITHMETIC, profiling=False, selection_sha256=selection_hash,
                          cpu_affinity=[0, 1, 2, 3, 16, 17, 18, 19], observed_nice=0, native_nice=0,
                          teardown=[dict(safe_to_exit=True, idle_marker_complete=True, exit_code=0, live_bytes=0, in_flight=0)])
            native['lookup_residency']=json.loads((S.HERE/'lineage/synthetic-lookup-receipt.json').read_text())
            native_hash = put(e, name + '/run/run/receipt.json', native)
            put(e, name + '/run/suite-manifest.snapshot.json', manifest)
            rows = []
            for pi, entry in enumerate(entries[:1] if cap == 8 else entries):
                pid = entry['prompt_id']
                prefix = name + '/run/run/' + pid + '/'
                # WS128x deliberately faster; a wrong timing-window choice is visible.
                rate = 10 + pi * pi if name == 'WS128' else 1000 + pi
                start = 1000 + pi * 100
                stamps = [start + 2 + i / rate for i in range(cap)]
                r = dict(passed=True, arithmetic=S.ARITHMETIC, tokens=tokens_by_id[pid][:cap],
                         cached_tokens=0, gpu_count=1, decode_mode='plain', context=4096,
                         requested_max_new=cap, prompt_tokens=entry['prompt_tokens'],
                         request_start_monotonic=start, request_end_monotonic=stamps[-1] + .5,
                         timing_rows=[dict(completed_monotonic=t) for t in stamps])
                put(e,prefix+'timings.jsonl',b''.join(json.dumps(dict(process_major_faults=0,process_minor_faults=1)).encode()+b'\n' for _ in range(cap)))
                native_result_hash = put(e, prefix + 'result.json', r)
                put(e, prefix + 'reset.json', dict(passed=True, cached_tokens=0, allocation_ids_preserved=True))
                count = 0
                if retain != 'none':
                    for step in range(1, 9):
                        layers = []
                        for layer in range(48):
                            leaf = f'step{step}/layer-{layer:02}.bf16'
                            e.members[prefix + leaf] = dict(sha256=fixture_sha, bytes=20480, retention='sha256-only')
                            layers.append(dict(layer=layer, sha256=fixture_sha))
                            count += 1
                        put(e, prefix + f'step{step}/layers.jsonl', b''.join(S.encoded(x) .replace(b'\n', b'') + b'\n' for x in layers))
                metrics = S.M.request_metrics(r, entry['prompt_tokens'], cap, retain, start=start, end=stamps[-1] + .5, device=True)
                rows.append(dict(metrics, passed=True, prompt_id=pid, prompt_class=S.M.PROMPT_CLASSES[pid],
                                 prompt_token_sha256=S.token_hash(inputs[pid]), tokens=r['tokens'], repeat=1,
                                 exact_oracle=True, compared_layer_fixtures=count, native_result_sha256=native_result_hash))
            summary = dict(S.M.aggregate(rows), requests=rows, passed=True, prompt_kv_response_reuse=False,
                           kv_dtype='BF16', gpu_count=1, decode_mode='plain', context=4096,
                           oracle_completion_sha256=completion_hash, timing_claim_eligible=name == 'WS128',
                           lane_scope=scope, native_receipt_sha256=native_hash,cache_maintenance='overlap',view='down-tile16',selection_sha256=selection_hash)
            summary_hash = put(e, name + '/run/summary.json', summary)
            put(e, name + '/summary.json', summary)
            put(e, name + '/run/receipt.json', dict(passed=True, safe_to_exit=True, window=name, summary_sha256=summary_hash,command=['--lookups','resident','--hc-geometry','hc-wide','--experts','wide64+halfcache','--other-fusion','fused','--retirement','ordered-foreground','--hc','p60fusion','--cache-maintenance','overlap','--miss-path','zero-copy','--cache-cap','max23','--cache-bytes','23049601024','--wait-policy','spin','--foreground-io','kernel','--expert-gateup','diet']))  # chain flags: composition.FLAGS carries the generated chain flags
            put(e, name + '/host-memory.jsonl', b'{}\n')
        files = {key[len(name) + 1:]: member['sha256'] for key, member in e.members.items()
                 if key.startswith(name + '/') and key != name + '/host-memory.jsonl'}
        clients = dict(blocked=[], other=[])
        w = dict(schema='own-runtime.packet58.window.v1', window=mode, passed=True, qualifying=not k1,
                 device_executed=True, child_still_running=False, stop_reasons=[], returncode=0,
                 gpu_count=1, card=0, context=4096, decode_mode='plain', build_receipt_sha256=seal_hash,
                 artifacts_sha256=seal['artifacts'], boot_id='synthetic-boot', pid=100 + wi,
                 process_start_ticks=100 + wi, started_utc_ns=1 + wi * 100, finished_utc_ns=50 + wi * 100,
                 environment={'PATH': '/usr/bin:/bin'}, native_files=files,cache_maintenance='overlap',view='down-tile16',
                 lane_admission=dict(passed=True, devices_drained=True, card=0, scope=scope,
                                     timing_claim_eligible=name == 'WS128',
                                     reservation=dict(scope=scope, boot_id='synthetic-boot'),
                                     owners={str(200 + wi): dict(seen=True, start_ticks=200 + wi,
                                         fds=[dict(driver='xe', pci='0000:23:00.0')])},
                                     clients=clients, clients_latest=clients, clients_after_drain=clients))
        if not k1:
            prev = S.ORDER[wi - 1] + '/window.json'
            w['previous'] = dict(path=str(S.ROOT / S.CHAIN / prev), sha256=S.sha(e.raw(prev)))
            w['k1_refs'] = [dict(path=str(S.ROOT / S.CHAIN / k / 'window.json'),
                                sha256=S.sha(e.raw(k + '/window.json')),
                                native_k1_sha256=S.sha(e.raw(k + '/run/k1.json'))) for k in S.ORDER[:2]]
            w['miss_path'] = 'zero-copy'
            digest = S.sha(e.raw(name + '/host-memory.jsonl'))
            census_hash=put(e,name+'/run/run/census.json',[dict(allocations=[dict(label='card0:exact-half-decode-table',category='weights',memory='device',bytes=262144,live=True)])])
            w['native_files']['run/run/census.json']=census_hash
            w['postload_memory'] = dict(exact_half_decode_table_bytes=262144,complete_postload=True, full_cache_bytes=23_049_601_024,
                                       pinned_expert_bytes=48_627_712_000, sources={'host-memory.jsonl': digest})
            w['memory_samples_sha256'] = digest
        put(e, name + '/window.json', w)
    put(e, 'queue.json', dict(schema='own-runtime.packet58.queue.v1', passed=True, card=0,
                              completed=list(S.ORDER), running=None))
    return e, seal_hash


class SubmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture, cls.seal = synthetic()

    def setUp(self):
        self.e = S.Evidence(copy.deepcopy(self.fixture.members))
        self.pin = patch.object(S, 'SEAL_SHA', self.seal)
        self.pin.start()
        self.addCleanup(self.pin.stop)

    def test_passing_chain_uses_ws128_only_and_balances_six_classes(self):
        r = S.derive(self.e)
        classes = {kind: statistics.median(10 + i * i for i, pid in enumerate(S.M.PROMPT_CLASSES)
                                          if S.M.PROMPT_CLASSES[pid] == kind) for kind in set(S.M.PROMPT_CLASSES.values())}
        self.assertAlmostEqual(r['primary_metric']['value_tok_s'], statistics.median(classes.values()))
        self.assertNotAlmostEqual(r['primary_metric']['value_tok_s'], r['secondary']['submission100_statistics']['median'])
        self.assertEqual(r['exactness']['prompts'], 12)
        self.assertFalse(r['fresh_timing_repeat_passed'])
        self.assertFalse(r['realistic_final_gate']['passed'])
        self.assertTrue(all(x['submission100']['numerator'] == 99 for x in r['rows']))

    def test_overlap_argv_required(self):
        key='WS128/run/receipt.json'
        digest=changed(self.e,key,lambda r:r.update(command=['--lookups','resident','--hc-geometry','hc-wide','--experts','wide64+halfcache','--other-fusion','fused','--retirement','ordered-foreground','--hc','p60fusion','--cache-maintenance','serial','--miss-path','zero-copy','--wait-policy','spin','--foreground-io','kernel','--expert-gateup','diet']))
        changed(self.e,'WS128/window.json',lambda r:r['native_files'].__setitem__('run/receipt.json',digest))
        with self.assertRaisesRegex(ValueError,'overlapped cache argv'):S.derive(self.e)

    def test_hc_argv_required(self):
        for value in ('production','bogus'):
            e=S.Evidence(copy.deepcopy(self.fixture.members))
            key='WS128/run/receipt.json'
            def alter(row):row['command'][row['command'].index('--hc')+1]=value
            digest=changed(e,key,alter)
            changed(e,'WS128/window.json',lambda row:row['native_files'].__setitem__('run/receipt.json',digest))
            with self.assertRaisesRegex(ValueError,'overlapped cache argv|full composition'):S.derive(e)

    def test_equal_or_lower_than_threshold_refused(self):
        speed=S.derive(self.e)['primary_metric']['value_tok_s']
        for threshold in (speed, speed+1):
            evidence=S.Evidence(copy.deepcopy(self.fixture.members))
            changed(evidence,'record-threshold.json',
                    lambda row:row['records'][-1].update(threshold_tok_s=threshold))
            with self.subTest(threshold=threshold),self.assertRaisesRegex(ValueError,'not above matching one-card threshold'):
                S.derive(evidence)

    def test_final_location_cli_root(self):
        self.assertEqual(submission_cli.load_submitter().REPO_ROOT,S.ROOT)

    def test_capacity_argv_required(self):
        for flag,value in [('--cache-cap','18GB'),('--cache-bytes','18000000000'),('--cache-cap','max'),('--cache-bytes','21552729600')]:  # the 35.927 record line is refused as this candidate
            with self.subTest(flag=flag):
                e=S.Evidence(copy.deepcopy(self.fixture.members))
                key='WS128/run/receipt.json'
                def alter(row):
                    row['command'][row['command'].index(flag)+1]=value
                digest=changed(e,key,alter)
                changed(e,'WS128/window.json',lambda row:row['native_files'].__setitem__('run/receipt.json',digest))
                with self.assertRaisesRegex(ValueError,'overlapped cache argv|full composition'):S.derive(e)

    def test_fault_counters_and_pinned_predecessor(self):
        r=S.derive(self.e)
        self.assertEqual(r['fault_counters'],dict(major=0,minor=1536,tokens=1536,new_gpu_fault_lines=0))
        self.assertTrue(all(r['comparison'][k]==v for k,v in S.POLICY['supersedes'].items()))
        notes=S.submission_notes(r)
        self.assertIn(S.POLICY['supersedes']['reference_submission'],notes)
        self.assertIn(S.POLICY['public_record_check']['disclosure'],notes)
        self.assertIn('overlapped cache maintenance',notes)
        self.assertIn('realistic_final_gate.passed=false',notes)
        for text in ('23.05 GB expert cache', 'cache_cap max23', '23,049,601,024', 'exact expert gate/up diet', '128-token owner scope', 'unchanged capacity and 30.5 GB DRM guard'):
            self.assertIn(text, notes)
        self.assertEqual(r['label'], 'qwen38-flash-next-unsloth-iq3xxs-ownrt-tp1-packet196-onecard-diet-chain-a-realistic-20261023')
        self.assertIn('lru23.05gb-max23', r['promotionIdentity']['optimization_identity'])
        self.assertIn(S.POLICY['readiness_amendment'],notes)
        self.assertIn(S.RERUN_DISCLOSURE,notes)
        self.assertEqual(r['rerun_disclosure'], S.RERUN_DISCLOSURE)
        for text in ('30.050', 'not submitted', '3,736', '124', 'quiet-host', 'unproven', 'no third run'):
            self.assertIn(text, notes)
        self.assertEqual(r['chain_attempt'],'a')

    def test_chain_a_refused_before_reading_evidence(self):
        with patch.object(S.Evidence, 'add', side_effect=AssertionError('must refuse before read')):
            with self.assertRaisesRegex(ValueError, 'only the registered card0-diet-a'):
                S.collect(S.ROOT / S.PACKET / 'evidence/card0-58ah-a')

    def test_missing_fault_counter_refuses(self):
        key='WS128/run/run/code-review/timings.jsonl'
        raw=self.e.raw(key).decode().replace('"process_major_faults": 0','"omitted": 0')
        digest=put(self.e,key,raw.encode())
        changed(self.e,'WS128/window.json',lambda r:r['native_files'].__setitem__('run/run/code-review/timings.jsonl',digest))
        with self.assertRaises(KeyError):S.derive(self.e)

    def test_failed_window(self):
        changed(self.e, 'WS/window.json', lambda w: w.update(passed=False))
        with self.assertRaisesRegex(ValueError, 'failed window'):
            S.derive(self.e)

    def test_inexact_prompt_with_rehashed_receipt(self):
        key = 'WS128/run/run/code-review/result.json'
        digest = changed(self.e, key, lambda r: r['tokens'].__setitem__(0, 999999))
        changed(self.e, 'WS128/window.json', lambda w: w['native_files'].__setitem__('run/run/code-review/result.json', digest))
        with self.assertRaisesRegex(ValueError, 'inexact prompt'):
            S.derive(self.e)

    def test_missing_ws128(self):
        self.e.members.pop('WS128/window.json')
        with self.assertRaises(KeyError):
            S.derive(self.e)

    def test_incomplete_queue(self):
        changed(self.e, 'queue.json', lambda q: q.update(completed=list(S.ORDER[:-1]), passed=False))
        with self.assertRaisesRegex(ValueError, 'queue incomplete'):
            S.derive(self.e)

    def test_notes_too_long(self):
        result = S.derive(self.e)
        result['public_record_check']['disclosure'] = 'x' * 2001
        with self.assertRaisesRegex(ValueError, 'notes exceed 2000'):
            S.submission_notes(result)

    def test_changed_hash(self):
        changed(self.e, 'WS128/run/run/code-review/reset.json', lambda r: r.update(cached_tokens=1))
        with self.assertRaisesRegex(ValueError, 'bound hash mismatch'):
            S.derive(self.e)

    def test_unbound_native_receipt(self):
        changed(self.e, 'WS128/window.json', lambda w: w['native_files'].pop('run/run/code-review/result.json'))
        with self.assertRaisesRegex(ValueError, 'unbound window evidence'):
            S.derive(self.e)

    def test_shared_host_timing_refused(self):
        changed(self.e, 'WS128/window.json', lambda w: w['lane_admission'].update(scope='lane-A'))
        with self.assertRaisesRegex(ValueError, 'whole-host'):
            S.derive(self.e)

    def test_oracle_not_interchangeable(self):
        changed(self.e, 'oracle/completion.json', lambda r: r.update(arithmetic='different'))
        with self.assertRaisesRegex(ValueError, 'CPU oracle'):
            S.derive(self.e)

    def test_fixture_byte_mismatch(self):
        key = 'WS/run/run/code-review/step1/layer-00.bf16'
        self.e.members[key]['sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            S.derive(self.e)

    def test_nonmonotonic_timestamps(self):
        key = 'WS128/run/run/code-review/result.json'
        digest = changed(self.e, key, lambda r: r['timing_rows'][1].update(r['timing_rows'][0]))
        changed(self.e, 'WS128/window.json', lambda w: w['native_files'].__setitem__('run/run/code-review/result.json', digest))
        with self.assertRaisesRegex(ValueError, 'non-increasing'):
            S.derive(self.e)

    def test_empty_timestamps_clean_refusal(self):
        key = 'WS128/run/run/code-review/result.json'
        digest = changed(self.e, key, lambda r: r.update(timing_rows=[]))
        changed(self.e, 'WS128/window.json', lambda w: w['native_files'].__setitem__('run/run/code-review/result.json', digest))
        with self.assertRaisesRegex(ValueError, 'request endpoints'):
            S.derive(self.e)

    def test_native_owner_reuse(self):
        owner = self.e.read('WS128x/window.json')['lane_admission']['owners']
        changed(self.e, 'WS128/window.json', lambda w: w['lane_admission'].update(owners=owner))
        with self.assertRaisesRegex(ValueError, 'device process reused'):
            S.derive(self.e)

    def test_production_pin_rejects_fixture(self):
        self.pin.stop()
        with patch.object(S,'SEAL_SHA','f'*64), self.assertRaisesRegex(ValueError, 'bound hash mismatch: seal.json'):
            S.derive(self.e)

    def test_offline_cli_schema_and_record_update(self):
        # A temporary repository holds generated test outputs. The shared CLI is
        # invoked exactly with --dry-run; urlopen is patched to forbid any network.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / S.THRESHOLD).parent.mkdir(parents=True)
            (repo / S.LIVE_THRESHOLD).parent.mkdir(parents=True)
            (repo / S.LIVE_THRESHOLD).write_bytes(self.e.raw('record-threshold.json'))
            (repo / S.THRESHOLD).write_bytes(self.e.raw('record-threshold.json'))
            out = repo / S.OUTPUT / 'fixture'
            S.write_prepared(self.e, out, repo)
            cli = submission_cli.load_submitter()
            cli.REPO_ROOT = repo
            item = json.loads((out / 'payload-queue.json').read_bytes())[0]
            self.assertEqual(cli.preflight_payload(item), [])
            argv = ['submission_cli.py', '--payloads', str(out / 'payload-queue.json'), '--dry-run']
            output = io.StringIO()
            with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(output), \
                    patch.object(cli.urllib.request, 'urlopen', side_effect=AssertionError('network forbidden')):
                self.assertEqual(cli.main(), 0)
            projected = json.loads(output.getvalue())
            self.assertEqual(projected, [item])
            api_flags = cli.api_engine_flags(item['payload']['engineFlags'])
            self.assertEqual(api_flags['tensorParallel'], 1)
            self.assertEqual(api_flags['kvCacheDtype'], 'auto')
            self.assertEqual(api_flags['gpuLayers'], 48)
            self.assertFalse(api_flags['specDecoding'])
            self.assertIn('gpuCount', output.getvalue())
            self.assertEqual(item['payload']['hardware']['gpuCount'], 1)
            self.assertEqual(item['payload']['engineFlags']['tensorParallel'], 1)
            self.assertFalse(item['payload']['engineFlags']['mtpEnabled'])
            self.assertLessEqual(len(item['payload']['notes']), 2000)
            bad = copy.deepcopy(item)
            bad['payload']['notes'] = 'x' * 2001
            self.assertTrue(any('2000' in p for p in cli.preflight_payload(bad)))
            bad = copy.deepcopy(item)
            bad['payload']['tokSOut'] += 1
            self.assertTrue(S.scope_problems(bad, repo))
            result_path = out / 'result.json'
            row = S.update_record(result_path, 'synthetic-coordinator-id', repo)
            self.assertEqual(row['threshold_tok_s'], item['payload']['tokSOut'])
            self.assertEqual(row['readiness_amendment'],S.POLICY['readiness_amendment'])
            self.assertEqual(row['rerun_disclosure'],S.RERUN_DISCLOSURE)
            self.assertEqual(row['chain_attempt'],'a')
            with self.assertRaisesRegex(ValueError, 'improve threshold'):
                S.update_record(result_path, 'another-id', repo)
            self.assertTrue(S.scope_problems(item, repo))


if __name__ == '__main__':
    unittest.main()
