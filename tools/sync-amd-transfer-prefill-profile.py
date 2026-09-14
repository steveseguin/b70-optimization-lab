#!/usr/bin/env python3
"""Publish the original recommended FP8 prefill baseline with recovery support.

The failed candidate contributes no performance values. Previous capacity
profiles remain intact. Restoration must pass before this profile is written.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[1]
DATA = 'experiments/qwen38-27b-b70/data/2026-09-14-amd-transfer'
SOURCE = DATA + '/summary.json'
REPORT = 'experiments/qwen38-27b-b70/notes/2026-09-14-amd-transfer-results.md'
PACKAGE = 'packages/qwen38-27b-fp8-tp2-b70/package.json'
PROFILE_ID = 'server-prefill-recommended-fp8-33024-control'
IMAGE = 'sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verified_summary():
    raw = (ROOT / SOURCE).read_bytes()
    manifest = json.loads((ROOT / DATA / 'manifest.json').read_text())
    require(sha(raw) == manifest['summary_sha256'], 'Summary hash differs from manifest')
    archive_path = ROOT / DATA / 'evidence.tar.gz'
    require(manifest['archive'] == archive_path.name, 'Unexpected evidence archive')
    archive = archive_path.read_bytes()
    require(len(archive) == manifest['archive_bytes'] and sha(archive) == manifest['archive_sha256'],
            'Evidence archive identity differs')
    with tarfile.open(archive_path, 'r:gz') as tf:
        members = tf.getmembers()
        expected = manifest['members']
        require(len(members) == manifest['member_count'] == len(expected), 'Archive coverage differs')
        require([m.name for m in members] == sorted(expected), 'Archive names/order differ')
        for member in members:
            path = PurePosixPath(member.name)
            require(member.isfile() and not path.is_absolute() and '..' not in path.parts,
                    'Unsafe archive member')
            body = tf.extractfile(member).read()
            require(len(body) == expected[member.name]['bytes'] and
                    sha(body) == expected[member.name]['sha256'], 'Archive member identity differs')
    require(manifest['verification']['context_sse_metrics_and_strict_intervals_replayed'] is True,
            'Timing/output replay verification is missing')
    return json.loads(raw)


def profile(package):
    data = verified_summary()
    require(data['new_optimization_promoted'] is False, 'Unexpected optimization promotion')
    control = data['control']
    identity = control['identity']
    require(identity['image'] == IMAGE, 'Control runtime differs')
    command = identity['command']
    env = dict(item.split('=', 1) for item in identity['env'])

    def argument(name):
        require(command.count(name) == 1, 'Missing or duplicate argument: ' + name)
        return command[command.index(name) + 1]

    for key, value in {'--tensor-parallel-size': '2', '--dtype': 'float16',
                       '--quantization': 'fp8', '--kv-cache-dtype': 'auto',
                       '--max-model-len': '33024', '--max-num-batched-tokens': '4096',
                       '--max-num-seqs': '1', '--block-size': '64',
                       '--gpu-memory-utilization': '0.95'}.items():
        require(argument(key) == value, 'Control setup differs: ' + key)
    require('--no-enable-prefix-caching' in command and '--enable-prefix-caching' not in command,
            'Control must disable prefix caching')
    require(json.loads(argument('--speculative-config')) ==
            {'method': 'qwen3_next_mtp', 'num_speculative_tokens': 1}, 'Control draft differs')
    for key, value in {'VLLM_USE_V2_MODEL_RUNNER': '0', 'VLLM_XPU_FP8_BLOCK_W8A16': '1',
                       'VLLM_XPU_FP16_LINEAR_CLASSPAD': '0', 'VLLM_XPU_FP16_LINEAR_ROWCHUNK': '32',
                       'VLLM_XPU_ENABLE_XPU_GRAPH': '0'}.items():
        require(env.get(key) == value, 'Control environment differs: ' + key)
    compilation = json.loads(argument('--compilation-config'))
    require(compilation['splitting_ops'] == [] and
            compilation['inductor_compile_config']['deterministic'] is True,
            'Control compilation contract differs')
    recommended = package['recommended_setup']
    for key, expected in [('cards', 2), ('mtp_depth', 1), ('max_model_len', 33024),
                          ('max_num_batched_tokens', 4096), ('max_num_seqs', 1),
                          ('prefix_caching', False)]:
        require(recommended[key] == expected, 'Recommended setup differs: ' + key)
    require(recommended['image'].endswith('@' + IMAGE), 'Recommended runtime differs')
    require(control['strict_prompt_count'] == 12 and control['canaries_passed'] is True and
            control['realistic_workload_gate_passed'] is True, 'Control strict gates failed')
    parity = control['complete_token_reference_parity']
    require(parity['exact_prompts'] == parity['total_prompts'] == 12 and
            parity['complete_token_arrays_exact'] is True, 'Control reference outputs differ')
    context = control['context']
    require(context['measured_requests'] == 18 and context['warmups'] == 3 and
            context['all_cached_tokens_zero'] is True and
            context['all_complete_repeat_outputs_exact'] is True, 'Control context gates failed')
    restoration = data['restoration']
    require(restoration['status'] == 'completion-receipt-present' and
            restoration['completion_receipt'] is not None, 'Restoration final receipt is pending')
    state = restoration['state_snapshot']
    require(state['status'] == 'ready' and state['image_id'] == IMAGE,
            'Restored serving identity differs')
    restored_strict = restoration['strict_replayed']
    require(restored_strict['prompt_count'] == 12 and
            restored_strict['all_complete_outputs_equal_pre_reboot'] is True and
            restored_strict['all_cached_tokens_zero'] is True and
            restored_strict['canaries_passed'] is True and
            restored_strict['realistic_final_gate']['passed'] is True,
            'Restored strict output gates failed')
    restored_context = restoration['context_replayed']
    require(restored_context['measured_requests'] == 18 and
            restored_context['all_complete_outputs_equal_pre_reboot'] is True and
            restored_context['all_cached_tokens_zero'] is True, 'Restored context gates failed')
    require(set(context['by_length']) == set(restored_context['by_length']) == {'512', '2048', '16384'},
            'Measured context lengths differ')
    points = []
    for length in (512, 2048, 16384):
        measured = context['by_length'][str(length)]
        value = measured['server_prefill_tokens_per_s']
        require(measured['samples'] == restored_context['by_length'][str(length)]['samples'] == 6,
                'Unexpected samples per input length')
        require(type(value) in (int, float) and math.isfinite(value) and value > 0,
                'Invalid measured rate')
        points.append({'context_tokens': length, 'value': value, 'samples': 6})
    return {
        'id': PROFILE_ID,
        'label': 'Reading speed at 512–16,384 input tokens · recommended FP8 setup',
        'public_label': 'Reading speed · recommended setup · 2 GPUs · 1-token draft · 33,024-token capacity',
        'metric': 'prefill', 'unit': 'tok/s', 'x_metric': 'context_tokens',
        'x_label': 'Input length (tokens)', 'measurement_kind': 'server_prefill',
        'scope': 'Original control on the recommended official FP8 setup: one user, two GPUs, MTP1, '
                 '33,024 total-token capacity, 4,096 scheduling budget and no saved prompt cache.',
        'public_scope': 'How fast the recommended setup reads your prompt before writing an answer. '
                        'One user; 512, 2,048 and 16,384 input tokens; no saved prompt cache. '
                        'Unrepeated prose, code and documents. These are baseline measurements.',
        'evidence': REPORT, 'source_data': SOURCE, 'evidence_manifest': DATA + '/manifest.json',
        'operating_profile': {
            'tensor_parallel_size': 2, 'speculative_tokens': 1, 'quantization': 'FP8',
            'parent_runtime': 'R304', 'image_id': IMAGE, 'activations': 'FP16', 'kv_cache': 'FP16',
            'concurrency': 1, 'max_model_len': 33024, 'max_num_batched_tokens': 4096,
            'max_num_seqs': 1, 'prefix_caching': False, 'classpad': 0, 'rowchunk': 32,
            'block_size': 64, 'gpu_memory_utilization': 0.95, 'model_runner': 'V1',
        },
        'technical_method': 'September 14 original-control measurements on two ASRock B70s. '
            'Input tokens divided by server prefill duration, from first scheduled execution to first token, '
            'replayed from one-request histogram deltas. At each exact input length, two repeats per '
            'prose/code/documentation class: median within each class, then median across classes '
            '(six measured requests per point). Three separate warmups are excluded. Numeric input IDs; '
            '128 forced output tokens; zero cached tokens and complete output repeat equality. '
            'The full natural-completion suite also passes 12/12 reference comparisons and canaries. '
            'After the failed combined newer-runtime/V2/DFlash startup and user reboot, the original '
            'qualified service was restored; its strict suite and all measured context outputs match '
            'the pre-reboot control. Restored-process timings are separate supporting evidence and '
            'are not pooled into these values. No candidate inference result, optimization speedup, '
            'new decode record or unmeasured-context performance is claimed. Historical 1K- and '
            '4K-capacity prefill profiles remain separate.',
        'promotion_qualified': False, 'points': points,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    path = ROOT / PACKAGE
    package = json.loads(path.read_text())
    measured = profile(package)
    dependencies = [REPORT, SOURCE, DATA + '/manifest.json', DATA + '/evidence.tar.gz',
                    DATA + '/freeze-incident.json', DATA + '/incident-loader-source-review.json',
                    'experiments/qwen38-27b-b70/scripts/collect-amd-transfer-evidence.py',
                    'experiments/qwen38-27b-b70/scripts/bench-prefill-followup.py',
                    'experiments/qwen38-27b-b70/scripts/bench-short-prefill.py',
                    'tools/sync-amd-transfer-prefill-profile.py']
    for dependency in dependencies:
        require((ROOT / dependency).is_file(), 'Missing package dependency: ' + dependency)
    rows = package.setdefault('performance_profiles', [])
    existing = [p for p in rows if p.get('id') == PROFILE_ID]
    require(len(existing) <= 1, 'Duplicate recommended prefill profile')
    missing = [p for p in dependencies if p not in package['dependencies']]
    if existing != [measured] or missing:
        if args.check:
            raise SystemExit('Recommended FP8 prefill profile/dependencies need synchronization: ' + PACKAGE)
        rows[:] = [p for p in rows if p.get('id') != PROFILE_ID]
        rows.append(measured)
        package['dependencies'].extend(missing)
        path.write_text(json.dumps(package, indent=2, ensure_ascii=False) + '\n')
    print('Verified recommended FP8 prefill baseline.' if args.check else 'Updated recommended FP8 prefill baseline.')


if __name__ == '__main__':
    main()
