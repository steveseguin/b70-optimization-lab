#!/usr/bin/env python3
"""Replay bounded baseline prefill evidence; never promote an optimization.

Adapted from the frozen summarize-prefill-followup.py; that source is unchanged.
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
CORPUS_PATH = HERE.parent / 'data/2026-09-14-fp8-prefill-corpus.json'
PROFILES = {
    '27b-fp8': (2, 1, 'fp8', '/mnt/fast-ai/llm-models/qwen3.8-27b-fp8'),
}
MODEL_MANIFESTS = {
    '27b-fp8': 'repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json',
}
# Bind the copied reference to previously qualified R304 FP8 outputs.
REFERENCE_HASHES = {
    '27b-fp8': {
        'performance.json': '64c40d19fab86bb23c97cb646162844285f331da2abada3e004cd73808e2d09a',
        'canaries.json': 'f234e605954b061e7f902eb92dd96739722df5437cadd9b2aceed79b976e45f8',
        'campaign-identity.json': '593f5da7c74fa6705afd7cd70ab8e621258a97994758629a72835181a27037e5',
    },
}
LENGTHS = (512, 2048)
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
    require(args['lengths'] == '512,2048' and args['repeats'] == 3 and args['max_tokens'] == 128
            and args['max_model_len'] == 4096 and args['model'] == served_model,
            f'{arm}: client contract mismatch')
    corpus_text = reader.read(prefix / 'corpus.json', False)
    require(hashlib.sha256(corpus_text.encode()).hexdigest() == state['corpus_sha256']
            == hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest(), f'{arm}: corpus hash mismatch')
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
        require(len(ids) >= max(LENGTHS) and all(type(x) is int and x >= 0 for x in ids), 'invalid tokenizer IDs')
        for length in LENGTHS:
            key = f'{name}-{length}'
            require(state['prompts'][key] == ids[:length], f'{arm}: prompt is not source prefix')
            require(state['prompt_sha256s'][key] == client.sha(json.dumps(ids[:length], separators=(',', ':')).encode()),
                    f'{arm}: prompt hash mismatch')
    require(len(state['rows']) == 18 and len(state['warmups']) == 2, f'{arm}: row/warmup count')
    expected_warmups = {(f'prose-{length}', 0) for length in LENGTHS}
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
              '--quantization': quant, '--kv-cache-dtype': 'auto', '--max-model-len': '4096',
              '--max-num-seqs': '1', '--max-num-batched-tokens': '4096', '--block-size': '64',
              '--gpu-memory-utilization': '0.95'}
    for name, value in wanted.items():
        require(arg(name) == value, f'container identity mismatch: {name}')
    require('--no-enable-prefix-caching' in argv and '--enable-prefix-caching' not in argv,
            'prefix cache policy mismatch')
    same(json.loads(arg('--speculative-config')), {'method': 'qwen3_next_mtp',
         'num_speculative_tokens': depth}, 'draft identity mismatch')
    comp = json.loads(arg('--compilation-config'))
    same(comp, {'cudagraph_mode': 'PIECEWISE', 'splitting_ops': [],
        'cudagraph_capture_sizes': [1], 'max_cudagraph_capture_size': 1,
        'inductor_compile_config': {'combo_kernels': False, 'benchmark_combo_kernel': False,
            'deterministic': True, 'triton.autotune_pointwise': False,
            'benchmark_epilogue_fusion': False}}, 'graph/arithmetic identity mismatch')
    env = dict(entry.split('=', 1) for entry in container['Config']['Env'])
    for name, value in {'VLLM_XPU_FP16_LINEAR_CLASSPAD': '0', 'VLLM_XPU_FP16_LINEAR_ROWCHUNK': '32',
        'VLLM_XPU_DRAFT_LM_HEAD_INT4': '1', 'VLLM_XPU_ENABLE_XPU_GRAPH': '0',
        'VLLM_XPU_FP8_BLOCK_W8A16': '1', 'VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE': '128',
        'VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE': 'bf16', 'VLLM_XPU_DRAFT_LM_HEAD_INT4_APPLY_ROWS': '0',
        'VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT': '1',
        'VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH': '1', 'VLLM_XPU_ALLREDUCE_HOST_WAIT': '1', 'VLLM_XPU_GDN_SPEC_GROUP': '16',
        'VLLM_XPU_GDN_PREFILL_GROUP': '1', 'VLLM_XPU_GDN_SPLIT_MIXED': '1',
        'VLLM_BATCH_INVARIANT': '0', 'VLLM_USE_V2_MODEL_RUNNER': '0',
        'VLLM_XPU_W8A16_DECODE_PAD_ROWS': '0', 'VLLM_XPU_W8A16_PAD_N_SET': '',
        'VLLM_XPU_W4A16_DETERMINISM_PAD': '0', 'VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH': '0'}.items():
        require(env.get(name) == value, f'runtime environment mismatch: {name}')
    require(not env.get('VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST'), 'unexpected draft shortlist')
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
            'quantization': 'FP8', 'activation_dtype': 'float16',
            'max_model_len': 4096, 'max_num_batched_tokens': 4096, 'served_model': arg('--served-model-name')}


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
    result = {'schema': 'neural.download.fp8-prefill-focus-baseline.v1', 'raw_root': str(root),
              'complete': False, 'promotion_qualified': False,
              'metric_scope': 'Server histogram prefill; HTTP TTFT and tokens/TTFT proxy recorded separately.',
              'workload_scope': 'Unrepeated prose/code/documentation source excerpts, exact512/2048 inputs, one user,128 output tokens; three repeats per class per control arm.',
              'arithmetic_scope': 'Pinned R304; W8A16 fixed-K hook covers scheduled rows1..512, larger calls use the natural catalog. No kernel or runtime changes.',
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
