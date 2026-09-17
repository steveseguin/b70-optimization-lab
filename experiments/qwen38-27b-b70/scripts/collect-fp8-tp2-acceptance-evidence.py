#!/usr/bin/env python3
"""Freeze or verify the two-card FP8 package acceptance session (R310, MTP depth 5); performs no GPU operations.

Successor of collect-fp8-flagship-evidence.py for the September 17 package (image R310, depth 5, draft shortlist).
The raw session comes from run-fp8-tp2-acceptance-session.py. The frozen packet carries every file the gates read,
the reference no-MTP strict run it is compared with, the qualified research container it must match, and the exact
bytes of every source file involved, so `verify` recomputes all gates from the archive alone.
"""
import argparse
import hashlib
import io
import importlib.util
import re
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[3]
DEFAULT = ROOT / 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-two-card-depth5'
EXPECTED_IMAGE = 'sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04'
# Same-image no-MTP strict run (two cards, R310) and the qualified depth-5 research container, both from the
# 2026-09-16 review campaign (experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md).
REFERENCE_STRICT = Path('/mnt/fast-ai/bench-results/fp8-review-20260916/tp2-mtp0-strict')
QUALIFIED_CONTAINER = Path('/mnt/fast-ai/bench-results/fp8-review-20260916/tp2-mtp5/container-final.json')
CONFIGURATION = {'image_id': EXPECTED_IMAGE, 'model': 'Qwen/Qwen3.8-27B-FP8', 'cards': 2, 'mtp_depth': 5,
                 'draft_shortlist': '/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt', 'max_model_len': 33024,
                 'max_num_batched_tokens': 4096, 'max_num_seqs': 1, 'prefix_caching': False}
SOURCE_PATHS = ['packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py',
                'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_fa_verify_rows.py',
                'experiments/qwen38-27b-b70/scripts/check-fp8-practical-session.py',
                'experiments/qwen38-27b-b70/scripts/collect-fp8-tp2-acceptance-evidence.py',
                'experiments/qwen38-27b-b70/scripts/run-fp8-tp2-acceptance-session.py',
                'experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-campaign-prereg.md',
                'repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json',
                'repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh',
                'scripts/bench-openai-realistic-suite.py', 'scripts/neural-download-canaries.py',
                'scripts/compare-strict-attempt-outputs.py']
DOWNLOADED_MUST_MATCH = ('packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py',
                         'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_fa_verify_rows.py',
                         'experiments/qwen38-27b-b70/scripts/check-fp8-practical-session.py')


def digest(data): return hashlib.sha256(data).hexdigest()
def dump(path, value): path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def derive(files):
    def get(name): return json.loads(files[name])
    practical = get('run/practical/summary.json')
    strict = get('run/strict/performance.json')
    state = get('run/session/state.json')
    health = get('run/health/result.json')
    runtime = get('run/runtime-comparison.json')
    source = get('run/public-source/source-receipt.json')
    canary = get('run/strict/canaries.json')
    spec = importlib.util.spec_from_file_location('practical_checks', ROOT / 'experiments/qwen38-27b-b70/scripts/check-fp8-practical-session.py')
    practical_checks = importlib.util.module_from_spec(spec); spec.loader.exec_module(practical_checks)
    checked_practical = True
    pairs = {}
    for row in practical['rows']:
        try: practical_checks.check_task(row['task'], row['text'])
        except (ValueError, KeyError, TypeError): checked_practical = False
        directory = row['directory']
        request = get('run/practical/' + directory + '/request.json')
        task = next(t for t in practical_checks.TASKS if t['id'] == row['task'])
        checked_practical &= request == practical_checks.payload_for(task, practical['model'])
        parsed = practical_checks.consume_stream(io.BytesIO(files['run/practical/' + directory + '/response.sse']), io.BytesIO(), 0, clock=lambda: 0)
        checked_practical &= all(parsed[k] == row[k] for k in ('text', 'token_ids', 'prompt_tokens', 'completion_tokens', 'cached_tokens', 'finish_reasons'))
        tokens = row.get('token_ids')
        checked_practical &= isinstance(tokens, list) and bool(tokens) and all(type(t) is int for t in tokens) and len(tokens) == row.get('completion_tokens')
        pairs[(row['task'], row['repeat'])] = row
    for task in ('conversation', 'code', 'document'):
        a = pairs.get((task, 1), {}); b = pairs.get((task, 2), {})
        checked_practical &= bool(a and b) and a.get('token_ids') == b.get('token_ids') and a.get('text') == b.get('text')
    actual = get('run/session/container-inspect.json')
    qualified = get('reference/qualified/container-inspect.json')
    if isinstance(qualified, list): qualified = qualified[0]

    def command(container):
        args = container['Config']['Cmd'].copy(); args[args.index('--served-model-name') + 1] = '<alias>'; return args
    stop = get('run/session/stop-request.json')
    owned_identity = (bool(re.fullmatch('[0-9a-f]{64}', state.get('container_id', ''))) and state['container_id'] == actual['Id'] == stop['container_id']
                      and state['container_name'] == actual['Name'].lstrip('/') and state['image_id'] == EXPECTED_IMAGE
                      and actual['Image'] == state.get('local_image_id', EXPECTED_IMAGE))
    source_checked = all(digest(files['downloaded-source/' + r['path']]) == r['sha256'] for r in source['files'])
    source_checked &= all(files['downloaded-source/' + p] == files['source/' + p] for p in DOWNLOADED_MUST_MATCH)
    reference = get('reference/strict/performance.json')
    left = {r['prompt_id']: r for r in reference['rows']}
    right = {r['prompt_id']: r for r in strict['rows']}

    def ids(row):
        for key in ('output_token_ids', 'completion_token_ids', 'token_ids'):
            if key in row:
                value = row[key]
                if not isinstance(value, list) or not value or any(type(t) is not int for t in value): raise ValueError('Invalid or empty strict output token IDs')
                return value
        raise ValueError('No complete output token IDs in strict row')
    exact = sum(ids(left[k]) == ids(right[k]) for k in left.keys() & right.keys())
    metric = 'class_balanced_tok_s_1_100_intervals_after_ttft'
    speed = strict['summary'][metric]['median']; reference_speed = reference['summary'][metric]['median']
    depth = json.loads(actual['Config']['Cmd'][actual['Config']['Cmd'].index('--speculative-config') + 1])['num_speculative_tokens']
    gates = {
        'strict_12_no_mtp_reference_outputs_exact': len(reference['rows']) == len(strict['rows']) == len(left) == len(right) == exact == 12,
        'strict_natural_quality_gate': strict['realistic_final_gate']['passed'],
        'strict_cache_zero': strict['fresh_response_validity']['cached_tokens_all_zero'],
        'strict_canaries': canary['pass_all'],
        'practical_six_pass': practical['passed'] and len(practical['rows']) == 6 and all(r['passed'] and r['objective_check']['passed'] for r in practical['rows']) and {(r['task'], r['repeat']) for r in practical['rows']} == {(t, n) for t in ('conversation', 'code', 'document') for n in (1, 2)},
        'practical_cache_zero': all(r.get('cached_tokens') == 0 for r in practical['rows']),
        'practical_token_repeat_exact': bool(checked_practical),
        'runtime_matches_qualified_depth5': runtime['matched_image'] and runtime['matched_vllm_arguments_except_model_alias'] and not runtime['environment_differences'] and actual['Image'] == qualified['Image'] == EXPECTED_IMAGE and command(actual) == command(qualified) and sorted(actual['Config']['Env']) == sorted(qualified['Config']['Env']) and depth == CONFIGURATION['mtp_depth'],
        'owned_clean_stop': owned_identity and state['status'] == 'stopped' and not state.get('error') and stop.get('requested') is True,
        'public_source_bytes': source_checked and source.get('anonymous_download') is True and source.get('git_worktree') is False,
        'post_stop_absent': not get('run/status-stopped.json')['container_present'] and not get('run/status-stopped.json')['api_healthy'],
        'pre_post_health': health['preflight_rc'] == health['postflight_rc'] == 0 and health['gpu_faults'] == [],
    }
    return {'schema': 'neural.download.fp8-tp2-acceptance-result.v1', 'passed': all(gates.values()), 'gates': gates,
            'public_source_commit': source['commit'], 'public_source_archive_sha256': source['archive_sha256'],
            'configuration': CONFIGURATION,
            'strict': {'no_mtp_reference_exact': exact, 'requests': len(right), 'decode_tokens_s': speed,
                       'no_mtp_reference_decode_tokens_s': reference_speed, 'speedup_vs_no_mtp': speed / reference_speed,
                       'interpretation': 'second fresh depth-5 server of the two-run pair (the first is the review campaign tp2-mtp5 stage); outputs identical to the same-image no-MTP reference'},
            'practical': {'requests': len(practical['rows']), 'tasks': 3, 'repeats': 2, 'rows': [{'task': r['task'], 'repeat': r['repeat'], 'passed': r['passed'], 'input_tokens': r.get('prompt_tokens'), 'output_tokens': r.get('completion_tokens'), 'http_ttft_ms': 1000 * r['http_ttft_s'] if 'http_ttft_s' in r else None, 'token_identity': r.get('repeat_identity')} for r in practical['rows']]},
            'timing_scope': 'Practical HTTP TTFT is a transport measurement; no server-prefill headline inferred. Strict decode uses the canonical first-100-token interval definition.',
            'limits': ['one configured lab host; existing hash-verified model files and Docker layers reused',
                       'clean source/state directories, not clean driver installation or independent-host replay',
                       'three supplied chat tasks, not long-context retrieval quality or a prolonged soak']}


def collect(raw, out):
    if out.exists(): raise ValueError('Refusing to overwrite frozen packet')
    files = {}
    for path in sorted(raw.rglob('*')):
        if not path.is_file(): continue
        rel = path.relative_to(raw)
        if rel.parts[0] == 'clean-source' or 'cache' in rel.parts or 'overlay' in rel.parts or rel.name == 'repository.tar.gz': continue
        if rel.suffix in ('.lock', '.tmp'): continue
        files['run/' + str(rel)] = path.read_bytes()
    for name in ('performance.json', 'canaries.json', 'campaign-identity.json'):
        files['reference/strict/' + name] = (REFERENCE_STRICT / name).read_bytes()
    files['reference/qualified/container-inspect.json'] = QUALIFIED_CONTAINER.read_bytes()
    sources = []
    for name in SOURCE_PATHS:
        body = (ROOT / name).read_bytes(); files['source/' + name] = body; sources.append({'path': name, 'sha256': digest(body)})
    source_receipt = json.loads(files['run/public-source/source-receipt.json'])
    for row in source_receipt['files']:
        files['downloaded-source/' + row['path']] = (Path(source_receipt['source_dir']) / row['path']).read_bytes()
    summary = derive(files)
    out.mkdir(parents=True)
    archive = out / 'evidence.tar.gz'
    with tarfile.open(archive, 'w:gz') as tf:
        for name, body in sorted(files.items()):
            item = tarfile.TarInfo(name); item.size = len(body); item.mode = 0o644; item.mtime = 0; tf.addfile(item, io.BytesIO(body))
    dump(out / 'summary.json', summary)
    dump(out / 'manifest.json', {'schema': 'neural.download.fp8-tp2-acceptance-evidence.v1', 'archive': {'path': archive.name, 'sha256': digest(archive.read_bytes()), 'bytes': archive.stat().st_size}, 'summary_sha256': digest((out / 'summary.json').read_bytes()), 'files': [{'path': n, 'sha256': digest(b), 'bytes': len(b)} for n, b in sorted(files.items())], 'sources': sources})
    verify(out)


def verify(out):
    manifest = json.loads((out / 'manifest.json').read_text()); archive = out / manifest['archive']['path']
    assert digest(archive.read_bytes()) == manifest['archive']['sha256']
    assert digest((out / 'summary.json').read_bytes()) == manifest['summary_sha256']
    files = {}
    with tarfile.open(archive) as tf:
        for member in tf:
            assert member.isfile() and member.name not in files
            files[member.name] = tf.extractfile(member).read()
    assert set(files) == {r['path'] for r in manifest['files']}
    for row in manifest['files']:
        assert digest(files[row['path']]) == row['sha256'] and len(files[row['path']]) == row['bytes']
    for row in manifest['sources']: assert digest((ROOT / row['path']).read_bytes()) == row['sha256'], row['path']
    summary = derive(files); assert summary == json.loads((out / 'summary.json').read_text())
    assert summary['passed'], summary['gates']
    print(f"FP8 two-card acceptance evidence verified: {len(files)} files, strict 12/12 vs no-MTP, practical 6/6, owned clean stop")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--raw', type=Path); parser.add_argument('--out', type=Path, default=DEFAULT); args = parser.parse_args()
    if args.raw: collect(args.raw, args.out)
    else: verify(args.out)
