#!/usr/bin/env python3
"""Recompute historical R307 comparisons and capture compact immutable receipts."""
import hashlib
import json
from pathlib import Path
import re
import shutil

OUT = Path(__file__).resolve().parent
ROOT = Path('/mnt/fast-ai/bench-results')
STRICT = ROOT / 'qwen35-4b-w4a16-20260912-r307'
DEPTH = ROOT / 'qwen35-4b-w4a16-20260913-r307-32k'
REBASE = ROOT / 'rebase-v0290-20260912'
OLD9 = ROOT / 'qwen35-9b-w4a16-20260912-r307'
manifest = []


def copy(path):
    rel = path.relative_to(ROOT)
    dest = OUT / 'evidence' / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, dest)
    manifest.append({'source': str(path), 'copy': str(dest.relative_to(OUT)), 'bytes': path.stat().st_size,
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})


def load(path):
    return json.loads(path.read_text())


def numeric(values):
    return bool(values) and all(type(x) is int and x >= 0 for x in values)


summary = {'schema': 'r307-historical-regression-audit-v1', 'strict': {}, 'depth': {}, 'health': {},
           'limitations': ['Historical diagnostic qualification only; no automatic image-contract or public promotion.',
                          'Strict profile labels say 9b and depth arm labels say mtp1; actual container image/config must take precedence.',
                          'Alias harness retained only degeneracy counts, not complete output token IDs; no exact-identity claim from that screen.',
                          'Depth has one server per arm, not two fresh speculative servers.']}
for root in (STRICT, DEPTH):
    for pattern in ('config.txt', 'repo-head.txt', 'boot-id.txt', 'campaign*.txt', 'campaign.log', '*post*.txt', 'preflight-*.txt', 'compare-*.json'):
        for p in root.glob(pattern):
            copy(p)
    for server in [p for p in root.iterdir() if p.is_dir() and not p.name.endswith('cache')]:
        text = (server / 'server.log').read_text(errors='replace')
        inspect = load(server / 'container-inspect.json')
        if isinstance(inspect, list):
            inspect = inspect[0]
        identity = {'image_id': inspect.get('Image'), 'image_name': inspect.get('Config', {}).get('Image'),
                    'args': inspect.get('Args'), 'started_at': inspect.get('State', {}).get('StartedAt'),
                    'image_contract_bypassed': 'IMAGE CONTRACT SKIPPED' in text,
                    'contract_evidence': [line for line in text.splitlines() if 'IMAGE CONTRACT SKIPPED' in line]}
        target = OUT / 'evidence' / server.relative_to(ROOT) / 'runtime-identity-extract.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(identity, indent=2) + '\n')
        journal = root / (server.name + '-post-kernel-journal.txt')
        compute = root / (server.name + '-post-compute-xccl.txt')
        faults = [line for line in journal.read_text().splitlines() if re.search(r'Fault response|CAT error|engine.*reset|coredump', line, re.I)]
        smoke = compute.read_text() if compute.exists() else ''
        summary['health'][f'{root.name}/{server.name}'] = {'kernel_fault_matches': faults,
            'compute_smoke_present': compute.exists(), 'single_device_smokes': smoke.count('ok 2097152.0'),
            'rank0_allreduce_ok': 'rank 0 allreduce ok 2.0' in smoke,
            'rank1_allreduce_ok': 'rank 1 allreduce ok 2.0' in smoke,
            'contract_bypassed': identity['image_contract_bypassed']}
        for sub in ('strict', 'depth'):
            folder = server / sub
            if folder.exists():
                for p in folder.iterdir():
                    if p.suffix == '.json' and '.stdout.' not in p.name or p.name == 'input-sha256sums.txt':
                        copy(p)

summary['comparison_artifact_hashes'] = {}
for comparison in STRICT.glob('compare-*.json'):
    data = load(comparison)
    checks = {}
    for side in ('left', 'right'):
        for name, artifact in data[side]['artifacts'].items():
            checks[f'{side}/{name}'] = hashlib.sha256((ROOT / artifact['path']).read_bytes()).hexdigest() == artifact['sha256']
    summary['comparison_artifact_hashes'][comparison.name] = checks

arms = {arm: load(STRICT / arm / 'strict/performance.json') for arm in ('mtp0-a', 'mtp0-b', 'mtp3-a', 'mtp3-b')}
for left, right in [('mtp0-a', 'mtp0-b'), ('mtp3-a', 'mtp3-b'), ('mtp3-a', 'mtp0-a'), ('mtp3-b', 'mtp0-a')]:
    a = {r['prompt_id']: r for r in arms[left]['rows']}
    b = {r['prompt_id']: r for r in arms[right]['rows']}
    checks = []
    for key in a:
        x, y = a[key], b[key]
        checks.append({'prompt_id': key, 'tokens': len(x['token_ids']),
            'numeric_complete': all(numeric(r['token_ids']) and len(r['token_ids']) == r['completion_tokens'] == r['stream_token_id_count'] for r in (x, y)),
            'prompt_hash_equal': x['prompt_sha256'] == y['prompt_sha256'],
            'ids_exact': x['token_ids'] == y['token_ids'], 'cache_zero': x['cached_tokens'] == y['cached_tokens'] == 0})
    summary['strict'][f'{left}-vs-{right}'] = {'same_prompt_set': set(a) == set(b), 'prompts': len(checks),
        'total_tokens_per_arm': sum(r['tokens'] for r in checks), 'recomputed_pass': all(all(v for k,v in r.items() if k not in ('prompt_id','tokens')) for r in checks), 'checks': checks}

baseline = load(DEPTH / 'depth-mtp0/depth/summary.json')
spec = load(DEPTH / 'depth-mtp3/depth/summary.json')
by_id = {c['case_id']: c for c in baseline['cases']}
checks = []
for case in spec['cases']:
    key = case['case_id']
    a = load(DEPTH / 'depth-mtp0/depth' / by_id[key]['receipt'])
    b = load(DEPTH / 'depth-mtp3/depth' / case['receipt'])
    x, y = a['response'], b['response']
    checks.append({'case': key, 'depth': case['active_context_tokens'],
        'numeric_complete_128': all(numeric(r['token_ids']) and len(r['token_ids']) == r['usage']['completion_tokens'] == 128 for r in (x,y)),
        'ids_exact': x['token_ids'] == y['token_ids'],
        'summary_ids_match_receipts': case['output_token_ids'] == y['token_ids'] and by_id[key]['output_token_ids'] == x['token_ids'],
        'prompt_hash_equal': a['fixture']['prompt_token_ids_sha256'] == b['fixture']['prompt_token_ids_sha256'],
        'usage_prompt_depth_exact': x['usage']['prompt_tokens'] == y['usage']['prompt_tokens'] == case['active_context_tokens'],
        'cache_zero': all(r['usage']['prompt_tokens_details']['cached_tokens'] == 0 for r in (x,y))})
summary['depth'] = {'cases': len(checks), 'depths': sorted({r['depth'] for r in checks}),
    'recomputed_pass': all(all(v for k,v in r.items() if k not in ('case','depth')) for r in checks), 'checks': checks}
for p in [REBASE/'alias-r307/harness.stdout', OLD9/'ABORTED', OLD9/'campaign.log', OLD9/'mtp0-a-post-kernel-journal.txt',
          REBASE/'stock-boundary/campaign.log', REBASE/'stock-boundary/image.txt', REBASE/'stock-boundary/run.sh', REBASE/'stock-boundary/mtp3.stdout']:
    copy(p)
alias = json.loads((REBASE/'alias-r307/harness.stdout').read_text().split('=== JSON ===')[1])
summary['alias'] = {'requests': sum(x['iters'] for x in alias['results']), 'degenerate': sum(x['degenerate'] for x in alias['results']), 'exact_token_identity_verified': False}
stock = (REBASE/'stock-boundary/mtp3.server.log').read_text(errors='replace').splitlines()
excerpt = [f'{i+1}: {line}' for i,line in enumerate(stock) if 'RuntimeError:' in line or 'EngineDeadError:' in line or '500 Internal Server Error' in line]
(OUT/'stock-crash-excerpt.txt').write_text('\n'.join(excerpt)+'\n')
summary['stock_boundary'] = {'failure_lines': excerpt, 'qualified': False}
notice = [line for line in (OLD9/'mtp0-a-post-kernel-journal.txt').read_text().splitlines() if 'coredump' in line.lower()]
summary['old_9b'] = {'aborted': (OLD9/'ABORTED').read_text().strip(), 'journal_notice': notice,
    'new_gpu_fault_proven_by_notice': False, 'interpretation': 'Deletion of an existing Xe coredump is a lifecycle notice, not evidence of a new GPU fault. Old runner matched generic coredump text and aborted qualification.', 'qualification_complete': False}
PREVIOUS = ROOT / 'qwen35-4b-w4a16-20260912-r304'
previous = {'scope': 'Matched strict workload regression against previous R304 image; no claim for untested prompts/shapes.',
            'model_weight_content_hash_verified': False,
            'model_identity_limit': 'Same read-only model mount path and quantization; retained receipts do not independently hash model weight bytes.',
            'arms': {}}
for name in ('config.txt', 'repo-head.txt', 'boot-id.txt'):
    copy(PREVIOUS/name)
for arm in arms:
    old = load(PREVIOUS/arm/'strict/performance.json')
    new = arms[arm]
    inspections = []
    for root in (PREVIOUS, STRICT):
        value = load(root/arm/'container-inspect.json')
        inspections.append(value[0] if isinstance(value, list) else value)
    old_i, new_i = inspections
    old_env = dict(x.split('=',1) for x in old_i['Config']['Env'])
    new_env = dict(x.split('=',1) for x in new_i['Config']['Env'])
    env_diff = {key: {'r304': old_env.get(key), 'r307': new_env.get(key)}
                for key in set(old_env)|set(new_env) if old_env.get(key) != new_env.get(key)}
    # The only observed environment delta substitutes this literal launcher flag.
    material_env = {k:v for k,v in env_diff.items() if not (k == 'REPRO_PREFIX_CACHING_ARG' and v == {'r304': None, 'r307': '--no-enable-prefix-caching'})}
    def effective_args(inspect):
        return [x.replace('${REPRO_PREFIX_CACHING_ARG}', '--no-enable-prefix-caching') for x in inspect['Args']]
    model_mounts = [[m for m in value['Mounts'] if m['Destination'] == '/model'] for value in inspections]
    matched = not material_env and effective_args(old_i) == effective_args(new_i) and model_mounts[0] == model_mounts[1]
    checks = []
    old_rows = {r['prompt_id']:r for r in old['rows']}
    for row in new['rows']:
        prior = old_rows[row['prompt_id']]
        checks.append({'prompt_id': row['prompt_id'], 'tokens': len(row['token_ids']),
            'numeric_complete': all(numeric(r['token_ids']) and len(r['token_ids']) == r['completion_tokens'] == r['stream_token_id_count'] for r in (row, prior)),
            'ids_exact': prior['token_ids'] == row['token_ids'], 'prompt_hash_equal': prior['prompt_sha256'] == row['prompt_sha256'],
            'cache_zero': prior['cached_tokens'] == row['cached_tokens'] == 0})
    previous['arms'][arm] = {'r304_image': old_i['Image'], 'r307_image': new_i['Image'],
        'environment_differences': env_diff, 'material_environment_differences': material_env,
        'effective_arguments_equal': effective_args(old_i) == effective_args(new_i), 'model_mounts_equal': model_mounts[0] == model_mounts[1],
        'runtime_configuration_matched_except_image_and_cache_directory': matched,
        'same_prompt_set': set(old_rows) == {r['prompt_id'] for r in new['rows']},
        'checks': checks, 'recomputed_pass': matched and all(all(v for k,v in c.items() if k not in ('prompt_id','tokens')) for c in checks)}
    if matched:
        for name in ('performance.json','campaign-identity.json','canaries.json','models.json'):
            copy(PREVIOUS/arm/'strict'/name)
    previous['arms'][arm]['runtime_identity'] = {'r304': {'args': old_i['Args'], 'repro_environment': {k:v for k,v in old_env.items() if k.startswith('REPRO_')}, 'model_mounts': model_mounts[0]},
        'r307': {'args': new_i['Args'], 'repro_environment': {k:v for k,v in new_env.items() if k.startswith('REPRO_')}, 'model_mounts': model_mounts[1]}}
summary['previous_r304_regression'] = previous
(OUT/'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False)+'\n')
(OUT/'source-manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
print(json.dumps({'copied_files': len(manifest), 'copied_bytes': sum(x['bytes'] for x in manifest), 'strict': {k:v['recomputed_pass'] for k,v in summary['strict'].items()}, 'depth': summary['depth']['recomputed_pass'], 'alias': summary['alias']}))
