#!/usr/bin/env python3
"""Replay bounded baseline prefill evidence; never promote an optimization.

Reads raw payloads/SSE/histograms and rederives aggregates. Complete strict
token arrays are compared directly with pinned prior qualified outputs.
Missing, incomplete, or inconsistent evidence fails closed.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
spec = importlib.util.spec_from_file_location('followup_client', HERE / 'bench-prefill-followup.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)
R304 = 'sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2'
UTILS_HASH = '34ef265d5a05425bd217b718229428e7b124788fb4586d367bd8053d50a80168'
UTILS_PATH = '/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/utils.py'
SHORTLIST = '/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt'
PROFILES = {
    '4b-tp2': (2, 3, 'compressed-tensors', '/home/steve/llm-models/qwen35-4b-w4a16'),
    '9b-tp2': (2, 3, 'compressed-tensors', '/home/steve/llm-models/qwen35-9b-w4a16'),
    '27b-int4-tp1': (1, 4, 'gptq', '/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel'),
}
MODEL_MANIFESTS = {
    '4b-tp2': 'repro/qwen35-4b-w4a16-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json',
    '9b-tp2': 'repro/qwen35-9b-w4a16-b70/manifests/model-direct-redhatai-qwen35-9b-w4a16-a398088c.json',
    '27b-int4-tp1': 'repro/qwen38-27b-autoround-int4-b70/manifests/model-gptq-relabel-r212.json',
}
# These bind the copied references to the qualification receipts audited before
# this follow-up. Rewriting both a copied file and its local manifest cannot pass.
REFERENCE_HASHES = {
    '4b-tp2': {'performance.json': '57e9d5f422b0e4481954802a790aceab8e718b249145aa14a99c02b760c5963f', 'campaign-identity.json': '4dca6655e33c38a3f13086d6edc1b2373a9a1f5afcd9236c9d6dc1a7795e1d68', 'canaries.json': '04538cb7dd1fc134a76e772a6f6b74f23135d3c09808a1e496bc41f4d91b5461'},
    '9b-tp2': {'performance.json': '4902b180330411cfa5fd1783669eae532f47d1a09af5f6076bc61915de8f7497', 'campaign-identity.json': '9ab666c2506667b03af72af68c23501cb3c5fcf45a957e491019ac5a14fc5f8b', 'canaries.json': 'd8586131b2de303f9184f6eaa4fd1d75e00ab818fa15ec20b543931a74eb7cc5'},
    '27b-int4-tp1': {'performance.json': 'c6e9a852be8ce986f50592d643457b87d4e34cac912b9126721a25279a385d6d', 'campaign-identity.json': 'c45288d6daa7fffb5370d91b59fe591416f3a9a6d6ed75f7b7d027121311461c', 'canaries.json': '71e90facb64468b0f768c7adc767b9341ffe9eab0efb1f1c3f37d907ca7842c8'},
}
LENGTHS = (256, 512)
ARMS = ('baseline', 'final-control')
KEYS = {f'{name}-{length}' for name in client.CLASSES for length in LENGTHS}
FIELDS = client.FIELDS


def require(condition, message):
    if not condition:
        raise ValueError(message)


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def same(actual, expected, label):
    if type(expected) in (int, float):
        require(type(actual) in (int, float) and math.isfinite(actual)
                and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12), label)
    elif isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), label)
        for key in expected:
            same(actual[key], expected[key], f'{label}.{key}')
    elif isinstance(expected, bool):
        require(type(actual) is bool and actual == expected, label)
    else:
        require(actual == expected, label)


class Reader:
    def __init__(self, root):
        self.root = Path(root)
        self.sources = {}

    def read(self, relative, decode=True):
        path = Path(relative)
        require(not path.is_absolute() and '..' not in path.parts, 'unsafe evidence path')
        data = (self.root / path).read_bytes()
        self.sources[str(path)] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        return json.loads(data) if decode else data.decode()


def replay_arm(reader, profile, arm, served_model):
    prefix = Path(profile) / arm
    state = reader.read(prefix / 'summary.json')
    require(state.get('passed') is True, f'{arm}: unfinished client')
    args = state['args']
    require(args['lengths'] == '256,512' and args['repeats'] == 3 and args['max_tokens'] == 128
            and args['max_model_len'] == 1024 and args['model'] == served_model,
            f'{arm}: client contract mismatch')
    corpus_text = reader.read(prefix / 'corpus.json', False)
    require(hashlib.sha256(corpus_text.encode()).hexdigest() == state['corpus_sha256']
            == hashlib.sha256(client.CORPUS_PATH.read_bytes()).hexdigest(), f'{arm}: corpus hash mismatch')
    corpus = json.loads(corpus_text)
    for filename, field in (('bench-prefill-followup.py', 'client_sha256'),
                            ('bench-short-prefill.py', 'parser_sha256')):
        require(state[field] == hashlib.sha256((HERE / filename).read_bytes()).hexdigest(),
                f'{arm}: tool identity mismatch: {filename}')
    require(set(state['prompts']) == KEYS, f'{arm}: prompt coverage')
    for entry in corpus['sources']:
        name = entry['label']
        payload = reader.read(prefix / f'tokenize-{name}-request.json')
        same(payload, {'model': served_model, 'prompt': entry['text'], 'add_special_tokens': False},
             f'{arm}: tokenize source/policy mismatch')
        ids = reader.read(prefix / f'tokenize-{name}.json')['tokens']
        require(len(ids) >= 512 and all(type(x) is int and x >= 0 for x in ids), 'invalid tokenizer IDs')
        for length in LENGTHS:
            key = f'{name}-{length}'
            require(state['prompts'][key] == ids[:length], f'{arm}: prompt is not source prefix')
            require(state['prompt_sha256s'][key] == client.sha(json.dumps(ids[:length], separators=(',', ':')).encode()),
                    f'{arm}: prompt hash mismatch')
    require(len(state['rows']) == 18 and len(state['warmups']) == 2, f'{arm}: row/warmup count')
    expected_warmups = {('prose-256', 0), ('prose-512', 0)}
    outputs, seen = {}, set()
    for phase, rows in (('warmup', state['warmups']), ('measure', state['rows'])):
        for row in rows:
            key, repeat = row['key'], row['repeat']
            require(row['phase'] == phase and key in KEYS and type(repeat) is int,
                    f'{arm}: row identity mismatch')
            identity = (phase, key, repeat)
            require(identity not in seen, f'{arm}: duplicate row')
            seen.add(identity)
            require((key, repeat) in expected_warmups if phase == 'warmup' else repeat in (0, 1, 2),
                    f'{arm}: invalid repeat')
            stem = f'{phase}-{key}-{repeat}'
            prompt = state['prompts'][key]
            payload = reader.read(prefix / f'{stem}-request.json')
            same(payload, dict(model=served_model, prompt=prompt, max_tokens=128, temperature=0,
                               seed=42, ignore_eos=True, return_token_ids=True, stream=True,
                               stream_options={'include_usage': True}, n=1), f'{arm}: request contract mismatch')
            events = [json.loads(line) for line in reader.read(prefix / f'{stem}-sse.jsonl', False).splitlines()]
            offsets = [event['elapsed_s'] for event in events]
            require(offsets and all(positive(t) for t in offsets)
                    and offsets == sorted(offsets), f'{arm}: raw SSE timestamps invalid')
            replayed = client.parse_events(events, len(prompt), 128)
            replayed.update(client.required_metric_delta(
                reader.read(prefix / f'{stem}-metrics-before.txt', False),
                reader.read(prefix / f'{stem}-metrics-after.txt', False), len(prompt)))
            for field, value in replayed.items():
                same(row[field], value, f'{arm}: raw replay mismatch: {stem}/{field}')
            require(all(positive(row[field]) for field in FIELDS), f'{arm}: timing invalid')
            require(key not in outputs or outputs[key] == row['token_ids'], f'{arm}: repeat output mismatch')
            outputs[key] = row['token_ids']
    computed = client.aggregate(state['rows'], state['prompts'], LENGTHS, 3)
    same(state['by_length'], computed, f'{arm}: aggregate mismatch')
    return state, outputs, computed


def strict_attempt(reader, prefix):
    perf = reader.read(prefix / 'performance.json')
    identity = reader.read(prefix / 'campaign-identity.json')
    canaries = reader.read(prefix / 'canaries.json')
    contract = identity['performance_contract']
    require(contract['max_tokens'] == 512 and contract['ignore_eos'] is False
            and contract['complete_fixed_suite'] is True and contract['metric_intervals'] == 99,
            'strict natural-completion contract mismatch')
    require(perf['realistic_final_gate']['passed'] is True and perf['fresh_response_validity']['valid'] is True,
            'strict workload validity failed')
    require(canaries['pass_all'] is True and all(canaries[k]['pass'] is True
            for k in ('repeat_8x', 'arithmetic', 'copy', 'json_schema'))
            and canaries['repeat_8x']['unique_outputs'] == 1, 'strict canaries failed')
    suite_path = REPO / 'repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json'
    require(identity['suite_sha256'] == hashlib.sha256(suite_path.read_bytes()).hexdigest(), 'strict suite hash mismatch')
    prompts = {row['id']: row['prompt'] for row in json.loads(suite_path.read_text())['prompts']}
    rows = perf['rows']
    require(len(rows) == 12 and {row['prompt_id'] for row in rows} == set(prompts), 'strict prompt coverage')
    classes = {}
    for row in rows:
        require(row['prompt_sha256'] == client.sha(prompts[row['prompt_id']].encode()), 'strict prompt hash mismatch')
        ids, offsets = row['token_ids'], row['token_id_offsets_s']
        require(row['cached_tokens'] == 0 and row['usage']['prompt_tokens_details']['cached_tokens'] == 0
                and len(ids) == row['completion_tokens'] == row['usage']['completion_tokens']
                and 100 <= len(ids) <= 512 and all(type(x) is int and x >= 0 for x in ids), 'strict IDs/cache invalid')
        require(len(offsets) == len(ids) and all(positive(t) for t in offsets)
                and offsets == sorted(offsets) and offsets[99] > offsets[0], 'strict token timing invalid')
        rate = 99 / (offsets[99] - offsets[0])
        same(row['tok_s_1_100_intervals_after_ttft'], rate, 'strict decode replay mismatch')
        classes.setdefault(row['prompt_class'], []).append(rate)
    require(len(classes) == 6, 'strict classes incomplete')
    return {row['prompt_id']: row for row in rows}, statistics.median(statistics.median(v) for v in classes.values())


def check_reference(reader, profile):
    prefix = Path(profile)
    manifest = reader.read(prefix / 'original-reference-hashes.json')
    for name, digest in manifest.items():
        reader.read(prefix / 'original-reference' / name, False)
        require(reader.sources[str(prefix / 'original-reference' / name)]['sha256'] == digest,
                f'original reference hash mismatch: {name}')
    for name, digest in REFERENCE_HASHES[profile].items():
        require(manifest.get(name) == digest, f'original reference qualified pin mismatch: {name}')
    original, old_decode = strict_attempt(reader, prefix / 'original-reference')
    current, new_decode = strict_attempt(reader, prefix / 'baseline-strict')
    for key in original:
        require(original[key]['token_ids'] == current[key]['token_ids'], f'original reference output mismatch: {key}')
        require(original[key]['prompt_tokens'] == current[key]['prompt_tokens'], 'strict tokenizer identity differs')
        require(original[key]['prompt_class'] == current[key]['prompt_class'], 'strict prompt class differs')
    comparison = reader.read(prefix / 'original-reference-comparison.json')
    require(comparison['comparison']['exact_prompts'] == 12 and comparison['comparison']['total_prompts'] == 12
            and comparison['qualification']['strict_pair_qualified'] is True, 'stored strict comparison failed')
    return {'exact_prompts': 12, 'total_prompts': 12, 'baseline_decode_tps': new_decode,
            'original_reference_decode_tps': old_decode,
            'baseline_vs_original_reference_fractional_delta': new_decode / old_decode - 1,
            'independent_process_repeat': False,
            'scope': 'Complete output parity against pinned prior qualification; decode delta is historical support, not a matched optimization comparison.'}


def check_identity(reader, profile):
    prefix = Path(profile)
    tp, depth, quant, model = PROFILES[profile]
    identity = reader.read(prefix / 'identity.json')
    image = reader.read(prefix / 'image-inspect.json')[0]
    container = reader.read(prefix / 'container-inspect.json')[0]
    require(identity['parent_image'] == image['Id'] == container['Image'] == R304, 'runtime image identity mismatch')
    runtime = reader.read(prefix / 'runtime-sha256.txt', False).split()
    require(runtime == [UTILS_HASH, UTILS_PATH], 'runtime utils hash mismatch')
    argv = container['Config']['Cmd']
    def arg(name):
        require(argv.count(name) == 1, f'container argument missing/duplicated: {name}')
        return argv[argv.index(name) + 1]
    wanted = {'--model': '/model', '--tensor-parallel-size': str(tp), '--dtype': 'float16',
              '--quantization': quant, '--kv-cache-dtype': 'auto', '--max-model-len': '1024',
              '--max-num-seqs': '1', '--max-num-batched-tokens': '1024', '--block-size': '64',
              '--gpu-memory-utilization': '0.96' if tp == 1 else '0.95'}
    for name, value in wanted.items():
        require(arg(name) == value, f'container identity mismatch: {name}')
    require('--no-enable-prefix-caching' in argv and '--enable-prefix-caching' not in argv,
            'prefix cache policy mismatch')
    same(json.loads(arg('--speculative-config')), {'method': 'qwen3_next_mtp' if tp == 1 else 'qwen3_5_mtp',
         'num_speculative_tokens': depth}, 'draft identity mismatch')
    comp = json.loads(arg('--compilation-config'))
    capture_sizes = [1, 2, 3, 4, 5, 6, 8, 10, 15, 16, 20, 25, 30, 32, 40, 50, 60, 64]
    if tp == 1:
        capture_sizes += [80, 100, 120, 160, 200, 240, 320]
    require(comp['cudagraph_mode'] == 'FULL_DECODE_ONLY' and comp['splitting_ops'] == []
            and comp['max_cudagraph_capture_size'] == (320 if tp == 1 else 64)
            and comp['cudagraph_capture_sizes'] == capture_sizes, 'graph identity mismatch')
    require(comp['inductor_compile_config']['deterministic'] is True
            and comp['inductor_compile_config']['split_reductions'] is False, 'arithmetic contract mismatch')
    env = dict(entry.split('=', 1) for entry in container['Config']['Env'])
    for name, value in {'VLLM_XPU_FP16_LINEAR_CLASSPAD': '0', 'VLLM_XPU_FP16_LINEAR_ROWCHUNK': '32',
        'VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST': SHORTLIST, 'VLLM_XPU_DRAFT_LM_HEAD_INT4': '1',
        'VLLM_XPU_GDN_SPEC_GROUP': '16', 'VLLM_XPU_GDN_PREFILL_GROUP': '1',
        'VLLM_XPU_GDN_SPLIT_MIXED': '1', 'VLLM_BATCH_INVARIANT': '0', 'VLLM_USE_V2_MODEL_RUNNER': '0',
        'VLLM_XPU_W4A16_DETERMINISM_PAD': '0', 'VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH': '0'}.items():
        require(env.get(name) == value, f'runtime environment mismatch: {name}')
    mounts = [mount for mount in container['Mounts'] if mount['Destination'] == '/model']
    require(len(mounts) == 1 and mounts[0]['Source'] == model and mounts[0]['RW'] is False,
            'model identity/read-only mount mismatch')
    log = reader.read(prefix / 'launcher.log', False)
    require(f'IMAGE CONTRACT PASS: profile=mtp1-serial-fa-split-gdn(v0290) image={R304} files=17' in log,
            'missing complete image contract receipt')
    require('model revision and all recorded file identities verified' in log
            and 'ordinary cache path also matched' in log, 'missing model verification receipt')
    manifest = reader.read(prefix / 'model-manifest.json')
    require(reader.sources[str(prefix / 'model-manifest.json')]['sha256'] ==
            client.sha((REPO / MODEL_MANIFESTS[profile]).read_bytes()), 'model manifest identity mismatch')
    for entry in manifest['lfs_files'] + manifest['small_files']:
        digest = entry.get('sha256', entry.get('git_blob'))
        require(digest and re.search(r'^OK\s+' + re.escape(entry['path']) + r' direct=' +
                re.escape(digest[:16]) + r' ordinary=' + re.escape(digest[:16]) + r'$', log, re.M),
                f'model file verification missing: {entry["path"]}')
    return {**identity, 'tensor_parallel_size': tp, 'speculative_tokens': depth,
            'quantization': 'INT4' if tp == 1 else 'W4A16', 'served_model': arg('--served-model-name')}


def profile_summary(reader, profile):
    prefix = Path(profile)
    require(not (reader.root / prefix / 'ABORTED').exists(), 'stage ABORTED')
    require(reader.read(prefix / 'DONE', False).strip(), 'stage not DONE')
    identity = check_identity(reader, profile)
    discovery = reader.read(prefix / 'postflight-discovery.txt', False)
    require(discovery.count('Device State: normal') == 2, 'postflight device health failed')
    health = reader.read(prefix / 'postflight-health.log', False)
    require(health.count('ok 2097152.0') == 2 and 'rank 0 allreduce ok 2.0' in health
            and 'rank 1 allreduce ok 2.0' in health, 'postflight compute health failed')
    journal = reader.read(prefix / 'postflight-final-journal.txt', False)
    fault = re.compile(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup', re.I)
    require(not any(fault.search(line) for line in journal.splitlines()
                    if not line.endswith('Xe device coredump has been deleted.')), 'postflight GPU fault')
    reader.read(prefix / 'stop.log', False)
    arms = {arm: replay_arm(reader, profile, arm, identity['served_model']) for arm in ARMS}
    require(arms['baseline'][0]['prompts'] == arms['final-control'][0]['prompts'], 'control prompt identities differ')
    require(arms['baseline'][1] == arms['final-control'][1], 'control complete outputs differ')
    points = []
    for length in LENGTHS:
        metrics = {arm: {field: arms[arm][2][str(length)][field] for field in FIELDS} for arm in ARMS}
        points.append({'prompt_tokens': length, 'samples': 18, 'classes': 3, 'repeats_per_class_per_arm': 3,
                       'arms': metrics,
                       'mean_controls': {field: statistics.mean(metrics[arm][field] for arm in ARMS) for field in FIELDS},
                       'final_vs_initial_control_fractional_drift': {
                           field: metrics['final-control'][field] / metrics['baseline'][field] - 1 for field in FIELDS}})
    return {'complete': True, 'quality_exact': True, 'promotion_qualified': False,
            'identity': identity, 'points': points, 'strict': check_reference(reader, profile),
            'decision': 'publish measured baseline; retain existing runtime',
            'max_observed_control_fractional_drift': max(abs(p['final_vs_initial_control_fractional_drift']['server_prefill_tokens_per_s']) for p in points)}


def summarize(root):
    reader = Reader(root)
    result = {'schema': 'neural.download.prefill-followup-baselines.v1', 'raw_root': str(root),
              'complete': False, 'promotion_qualified': False,
              'metric_scope': 'Server histogram prefill; HTTP TTFT and tokens/TTFT proxy recorded separately.',
              'workload_scope': 'Unrepeated prose/code/documentation source excerpts, exact256/512 inputs, one user,128 output tokens; three repeats per class per control arm.',
              'aggregation': 'Median within each class, then across classes; arithmetic mean of two control-arm aggregates.',
              'profiles': {}}
    for profile in PROFILES:
        try:
            result['profiles'][profile] = profile_summary(reader, profile)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ZeroDivisionError) as exc:
            result['profiles'][profile] = {'complete': False, 'promotion_qualified': False,
                                           'error': f'{type(exc).__name__}: {exc}'}
    result['complete'] = all(row['complete'] for row in result['profiles'].values())
    result['sources'] = reader.sources
    return result


def check_saved(saved, recomputed):
    # Extraction directories may differ during offline replay. The origin path
    # is descriptive; every consumed evidence path/hash remains compared.
    same(saved, {**recomputed, 'raw_root': saved['raw_root']}, 'saved summary differs from replay')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--raw-root', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--check', action='store_true', help='verify the saved summary against raw evidence without writing')
    args = ap.parse_args()
    result = summarize(args.raw_root)
    if args.check:
        check_saved(json.loads(args.out.read_text()), result)
    else:
        with args.out.open('x') as out:
            json.dump(result, out, indent=2, ensure_ascii=False)
            out.write('\n')
    print(json.dumps({'complete': result['complete'], 'profiles': {
        key: value.get('error', value.get('decision')) for key, value in result['profiles'].items()}}))
    raise SystemExit(0 if result['complete'] else 3)
