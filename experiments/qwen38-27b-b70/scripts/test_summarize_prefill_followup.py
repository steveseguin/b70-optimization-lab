"""Portable raw-evidence replay and tamper gates, with no GPU requests."""
import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


m = module('collector', 'summarize-prefill-followup.py')
client_tests = module('client_tests', 'test_bench_prefill_followup.py')


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n' if not isinstance(data, str) else data)


def fixture(root):
    profile = root / '4b-tp2'
    profile.mkdir()
    for arm in m.ARMS:
        args = argparse.Namespace(base_url='http://fake', model='test', out=profile / arm,
            corpus=m.client.CORPUS_PATH, baseline=None, lengths='256,512',
            max_model_len=1024, max_tokens=128, repeats=3, timeout=1)
        with patch.object(m.client, 'fetch', client_tests.FakeEndpoint().fetch), contextlib.redirect_stdout(io.StringIO()):
            m.client.run(args)
    write(profile / 'identity.json', {'parent_image': m.R304})
    write(profile / 'image-inspect.json', [{'Id': m.R304}])
    env = {'VLLM_XPU_FP16_LINEAR_CLASSPAD': '0', 'VLLM_XPU_FP16_LINEAR_ROWCHUNK': '32',
        'VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST': m.SHORTLIST, 'VLLM_XPU_DRAFT_LM_HEAD_INT4': '1',
        'VLLM_XPU_GDN_SPEC_GROUP': '16', 'VLLM_XPU_GDN_PREFILL_GROUP': '1',
        'VLLM_XPU_GDN_SPLIT_MIXED': '1', 'VLLM_BATCH_INVARIANT': '0', 'VLLM_USE_V2_MODEL_RUNNER': '0',
        'VLLM_XPU_W4A16_DETERMINISM_PAD': '0', 'VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH': '0'}
    args = {'--model': '/model', '--tensor-parallel-size': '2', '--dtype': 'float16',
            '--quantization': 'compressed-tensors', '--kv-cache-dtype': 'auto',
            '--max-model-len': '1024', '--max-num-seqs': '1', '--max-num-batched-tokens': '1024',
            '--block-size': '64', '--gpu-memory-utilization': '0.95', '--served-model-name': 'test',
            '--speculative-config': json.dumps({'method': 'qwen3_5_mtp', 'num_speculative_tokens': 3}),
            '--compilation-config': json.dumps({'cudagraph_mode': 'FULL_DECODE_ONLY', 'splitting_ops': [],
                'cudagraph_capture_sizes': [1, 2, 3, 4, 5, 6, 8, 10, 15, 16, 20, 25, 30, 32, 40, 50, 60, 64],
                'max_cudagraph_capture_size': 64,
                'inductor_compile_config': {'deterministic': True, 'split_reductions': False}})}
    write(profile / 'container-inspect.json', [{'Image': m.R304, 'Config': {
        'Cmd': [x for pair in args.items() for x in pair] + ['--no-enable-prefix-caching'],
        'Env': [f'{k}={v}' for k, v in env.items()]},
        'Mounts': [{'Source': m.PROFILES['4b-tp2'][3], 'Destination': '/model', 'RW': False}]}])
    write(profile / 'runtime-sha256.txt', m.UTILS_HASH + '  ' + m.UTILS_PATH + '\n')
    shutil.copyfile(m.REPO / m.MODEL_MANIFESTS['4b-tp2'], profile / 'model-manifest.json')
    manifest = json.loads((profile / 'model-manifest.json').read_text())
    log = f'IMAGE CONTRACT PASS: profile=mtp1-serial-fa-split-gdn(v0290) image={m.R304} files=17\n'
    for entry in manifest['lfs_files'] + manifest['small_files']:
        digest = entry.get('sha256', entry.get('git_blob'))[:16]
        log += f'OK   {entry["path"]} direct={digest} ordinary={digest}\n'
    log += 'model revision and all recorded file identities verified (direct modes: odirect; ordinary cache path also matched)\n'
    write(profile / 'launcher.log', log)
    write(profile / 'postflight-discovery.txt', 'Device State: normal\n' * 2)
    write(profile / 'postflight-health.log', 'ok 2097152.0\n' * 2 + 'rank 0 allreduce ok 2.0\nrank 1 allreduce ok 2.0\n')
    write(profile / 'postflight-final-journal.txt', '')
    write(profile / 'stop.log', 'test\n')
    write(profile / 'DONE', 'done\n')
    suite_path = m.REPO / 'repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json'
    suite = json.loads(suite_path.read_text())
    rows = []
    for i, prompt in enumerate(suite['prompts']):
        offsets = [.1 + x * .01 for x in range(128)]
        rows.append({'prompt_id': prompt['id'], 'prompt_sha256': m.client.sha(prompt['prompt'].encode()),
            'prompt_tokens': 100, 'prompt_class': f'class{i // 2}', 'token_ids': list(range(128)),
            'token_id_offsets_s': offsets, 'completion_tokens': 128, 'cached_tokens': 0,
            'usage': {'completion_tokens': 128, 'prompt_tokens_details': {'cached_tokens': 0}},
            'tok_s_1_100_intervals_after_ttft': 99 / (offsets[99] - offsets[0])})
    for arm in ('original-reference', 'baseline-strict'):
        write(profile / arm / 'performance.json', {'rows': rows, 'realistic_final_gate': {'passed': True},
                                                   'fresh_response_validity': {'valid': True}})
        write(profile / arm / 'campaign-identity.json', {'performance_contract': {
            'max_tokens': 512, 'ignore_eos': False, 'complete_fixed_suite': True, 'metric_intervals': 99},
            'suite_sha256': m.client.sha(suite_path.read_bytes())})
        write(profile / arm / 'canaries.json', {'pass_all': True, 'repeat_8x': {'pass': True, 'unique_outputs': 1},
            'arithmetic': {'pass': True}, 'copy': {'pass': True}, 'json_schema': {'pass': True}})
    hashes = {p.name: m.client.sha(p.read_bytes()) for p in (profile / 'original-reference').iterdir()}
    write(profile / 'original-reference-hashes.json', hashes)
    write(profile / 'original-reference-comparison.json', {'comparison': {'exact_prompts': 12, 'total_prompts': 12},
                                                          'qualification': {'strict_pair_qualified': True}})
    return hashes


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.profile = self.root / '4b-tp2'
        hashes = fixture(self.root)
        self.pins = patch.dict(m.REFERENCE_HASHES, {'4b-tp2': hashes})
        self.pins.start()

    def tearDown(self):
        self.pins.stop()
        self.temp.cleanup()

    def collect(self):
        return m.profile_summary(m.Reader(self.root), '4b-tp2')

    def mutate_json(self, filename, change):
        path = self.profile / filename
        data = json.loads(path.read_text())
        change(data)
        write(path, data)

    def test_complete_raw_replay_and_control_aggregation(self):
        result = self.collect()
        self.assertTrue(result['complete'])
        self.assertFalse(result['promotion_qualified'])
        self.assertEqual(result['strict']['exact_prompts'], 12)
        self.assertEqual(result['points'][1]['mean_controls']['server_prefill_tokens_per_s'], 2048)
        self.assertEqual(result['points'][1]['samples'], 18)

    def test_raw_output_tamper_cannot_hide_behind_summary(self):
        path = self.profile / 'baseline/measure-code-512-0-sse.jsonl'
        events = [json.loads(x) for x in path.read_text().splitlines()]
        event = json.loads(events[0]['data'])
        event['choices'][0]['token_ids'][0] = 9999
        events[0]['data'] = json.dumps(event)
        write(path, ''.join(json.dumps(x) + '\n' for x in events))
        with self.assertRaisesRegex(ValueError, 'raw replay mismatch'):
            self.collect()

    def test_raw_histogram_tamper_rejected(self):
        path = self.profile / 'baseline/measure-code-512-0-metrics-after.txt'
        text = path.read_text()
        text = '\n'.join(line.split()[0] + ' 999' if 'time_seconds_sum' in line else line for line in text.splitlines())
        write(path, text)
        with self.assertRaisesRegex(ValueError, 'raw replay mismatch'):
            self.collect()

    def test_request_contract_tamper_rejected(self):
        self.mutate_json('baseline/measure-code-512-0-request.json', lambda d: d.update(ignore_eos=False))
        with self.assertRaisesRegex(ValueError, 'request contract mismatch'):
            self.collect()

    def test_reference_manifest_and_file_tamper_fails_qualified_pin(self):
        path = self.profile / 'original-reference/performance.json'
        write(path, path.read_text() + '\n')
        self.mutate_json('original-reference-hashes.json', lambda d: d.update({'performance.json': m.client.sha(path.read_bytes())}))
        with self.assertRaisesRegex(ValueError, 'qualified pin mismatch'):
            self.collect()

    def test_strict_output_tamper_fails_despite_comparison_boolean(self):
        self.mutate_json('baseline-strict/performance.json', lambda d: d['rows'][0]['token_ids'].__setitem__(-1, 9999))
        with self.assertRaisesRegex(ValueError, 'original reference output mismatch'):
            self.collect()

    def test_topology_tamper_rejected(self):
        def change(d):
            args = d[0]['Config']['Cmd']
            args[args.index('--tensor-parallel-size') + 1] = '1'
        self.mutate_json('container-inspect.json', change)
        with self.assertRaisesRegex(ValueError, 'container identity mismatch'):
            self.collect()

    def test_missing_stage_never_publishable(self):
        (self.profile / 'DONE').unlink()
        summary = m.summarize(self.root)
        self.assertFalse(summary['complete'])
        self.assertFalse(summary['profiles']['4b-tp2']['complete'])

    def test_summary_aggregate_tamper_rejected(self):
        self.mutate_json('baseline/summary.json', lambda d: d['by_length']['512'].update(server_prefill_tokens_per_s=99999))
        with self.assertRaisesRegex(ValueError, 'aggregate mismatch'):
            self.collect()

    def test_offline_replay_accepts_relocation_but_rejects_changed_results(self):
        saved = {'raw_root': '/original', 'profiles': {'4b': {'rate': 2000}}}
        replay = {'raw_root': '/extracted', 'profiles': {'4b': {'rate': 2000}}}
        m.check_saved(saved, replay)
        replay['profiles']['4b']['rate'] = 2001
        with self.assertRaisesRegex(ValueError, 'saved summary differs'):
            m.check_saved(saved, replay)


if __name__ == '__main__':
    unittest.main()
