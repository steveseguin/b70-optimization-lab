#!/usr/bin/env python3
"""Capture and independently validate completed R307 one-active-request qualification.

Only reads the two explicitly supplied roots. Never launches a server. Nonzero
exit means mandatory evidence is incomplete or failed, regardless of DONE files.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil

IMAGE = 'sha256:9be49c62baabf4611ecf08419d836a2e2f171adba5d2a28509b6fd796e7d28c3'
FAULT = re.compile(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup', re.I)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def numeric(values):
    return isinstance(values, list) and bool(values) and all(type(x) is int and x >= 0 for x in values)


def boundary(data, oracle=None):
    require(data['status'] == 'complete' and data['passed'] is True, 'boundary status is not complete/passed')
    require(data['max_model_len'] == 256 and data['configuration']['concurrency'] == [1], 'boundary context/concurrency mismatch')
    require(data['configuration']['iters'] >= 2, 'boundary requires repeats')
    require(data['mode'] == ('compare' if oracle else 'oracle'), 'boundary mode mismatch')
    expected = {}
    if oracle:
        for case in oracle['cases']:
            expected[case['id']] = case
        tail = expected['L14']
        for n in range(236, 242):
            expected[f'L14-tail{n}'] = {'id': f'L14-tail{n}', 'prompt_ids': tail['prompt_ids'] + tail['expected_ids'][:n],
                'expected_ids': tail['expected_ids'][n:], 'max_tokens': 242-n}
    else:
        expected = {c['id']: c for c in data['cases']}
    wanted_keys = {f'L{i}' for i in range(8,28)} | ({f'L14-tail{n}' for n in range(236,242)} if oracle else set())
    cases = {c['id']: c for c in data['cases']}
    require(set(cases) == wanted_keys and len(cases) == len(data['cases']), 'missing/duplicate boundary cases')
    for key, case in cases.items():
        require(numeric(case['prompt_ids']) and numeric(case['expected_ids']), 'boundary IDs missing/non-numeric')
        require(len(case['prompt_ids']) + case['max_tokens'] == 256 and len(case['expected_ids']) == case['max_tokens'], 'boundary incomplete case')
        if key.startswith('L') and '-tail' not in key:
            require(len(case['prompt_ids']) == int(key[1:]), 'boundary prompt length differs from case label')
        require(case == expected[key], f'case changed from oracle: {key}')
    seen = Counter()
    for row in data['rows']:
        case = cases[row['case']]
        require(row['concurrency'] == 1 and row['passed'] is True and row['exact'] is True, 'boundary row flags failed')
        require(numeric(row.get('token_ids')) and row['token_ids'] == case['expected_ids'], 'boundary actual token IDs differ')
        require(row['usage']['completion_tokens'] == len(row['token_ids']) == case['max_tokens'], 'boundary output incomplete')
        require(row['usage']['prompt_tokens'] == len(case['prompt_ids']), 'boundary prompt usage mismatch')
        require(row['cached_tokens'] and all(type(x) is int and x == 0 for x in row['cached_tokens']), 'boundary cache-zero evidence missing')
        require(row['finish_reason'] == 'length', 'boundary did not reach limit')
        require(row['repeat'] in list(range(data['configuration']['iters'])) + ([-1] if oracle is None else []), 'invalid repeat')
        seen[(row['case'], row['repeat'])] += 1
    required = {(key, repeat) for key in cases for repeat in range(data['configuration']['iters'])}
    if oracle is None:
        required |= {(key, -1) for key in cases}
    require(set(seen) == required and all(n == 1 for n in seen.values()), 'boundary repeat coverage incomplete/duplicated')
    return {'passed': True, 'cases': len(cases), 'rows': len(data['rows']), 'actual_numeric_ids_recomputed': True}


class Capture:
    def __init__(self, out, image=IMAGE):
        self.out = out
        self.image = image
        self.manifest = []

    def file(self, path, label, root):
        require(path.is_file(), f'missing evidence: {path}')
        relative = Path(label) / path.relative_to(root)
        dest = self.out / 'evidence' / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
        self.manifest.append({'source': str(path), 'path': str(Path('evidence') / relative), 'sha256': sha(path), 'bytes': path.stat().st_size})

    def contract(self, folder, root, label):
        log = folder / 'server.log'
        lines = [x for x in log.read_text(errors='replace').splitlines() if 'IMAGE CONTRACT' in x]
        require(lines and all('IMAGE CONTRACT PASS:' in x and self.image in x for x in lines), f'contract absent/bypassed: {folder}')
        target = self.out/'evidence'/label/folder.relative_to(root)/'image-contract-lines.txt'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('\n'.join(lines)+'\n')
        return {'source_sha256': sha(log), 'lines': lines}

    def health(self, root, prefix, label, style='boundary'):
        if style == 'boundary':
            names = [f'{prefix}-before-journal.txt', f'{prefix}-after-journal.txt', f'{prefix}-compute-xccl.txt', f'{prefix}-discovery.txt']
        else:
            names = [f'{prefix}-kernel-journal.txt', f'{prefix}-compute-xccl.txt', f'{prefix}-xpu-smi-discovery.txt']
        for name in names:
            self.file(root/name, label, root)
            text = (root/name).read_text()
            if 'journal' in name:
                require(not any(FAULT.search(x) and 'Xe device coredump has been deleted.' not in x for x in text.splitlines()), f'kernel fault: {name}')
            if 'compute-xccl' in name:
                require(text.count('ok 2097152.0') >= 2 and all(f'rank {n} allreduce ok 2.0' in text for n in (0,1)), f'compute/XCCL incomplete: {name}')
            if 'discovery' in name:
                require(text.count('Device State: normal') == 2, f'devices not normal: {name}')
        return {'passed': True, 'receipts': names}


def validate_output(single, failed, out):
    destination = out.resolve()
    require(not any(destination.is_relative_to(root.resolve()) for root in (single, failed)),
            'output cannot be inside either source root')


def check_inventory(observed, expected):
    def inventory(path):
        entries = {}
        for line in path.read_text().splitlines():
            digest, name = line.split(maxsplit=1)
            name = name.lstrip('*')
            require(re.fullmatch(r'[0-9a-f]{64}', digest) and name not in entries, 'invalid/duplicate inventory entry')
            entries[name] = digest
        require(len(entries) == 17, 'rebuild contract must contain exactly17 files')
        return entries
    require(inventory(observed) == inventory(expected), 'rebuilt file inventory differs from candidate contract')
    return {'files':17, 'inventory_equal':True, 'observed_inventory_sha256':sha(observed),
            'committed_inventory_sha256':sha(expected)}


def candidate_identity(image, candidate):
    require(re.fullmatch(r'sha256:[0-9a-f]{64}', image), 'image must be immutable sha256 ID')
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,39}', candidate), 'invalid candidate label')


def campaign_identity(start, image, candidate, inventory):
    require(start['image'] == image and start.get('candidate', 'r307') == candidate, 'campaign candidate/image mismatch')
    if 'inventory_sha256' in start or image != IMAGE or candidate != 'r307':
        require(start.get('inventory_sha256') == sha(inventory), 'campaign inventory hash mismatch')


def analyze(single, failed, out, image=IMAGE, candidate='r307', inventory=None, rebuild_root=None):
    validate_output(single, failed, out)
    rebuild = rebuild_root or failed/'rebuild'
    require(not out.resolve().is_relative_to(rebuild.resolve()), 'output cannot be inside rebuild root')
    cap = Capture(out, image)
    contract_path = inventory or Path(__file__).resolve().parents[3]/'experiments/qwen38-27b-b70/docker/rebase-v0290/r307-contract-digests.sha256'
    summary = {'schema': 'r307-final-single-request-qualification-v1', 'passed': False,
        'candidate': candidate, 'image': image, 'inventory_path': str(contract_path), 'rebuild_root': str(rebuild),
        'scope': {'models': ['4B','9B'], 'tensor_parallel_size': 1, 'mtp_depth': 3, 'active_requests': 1, 'max_num_seqs': 1,
                  'c4_qualified': False, 'public_performance_promotion': False}, 'boundary': {}, 'strict9b': {}, 'health': {}, 'contracts': {}}
    try:
        candidate_identity(image, candidate)
        require(inventory is not None or (image == IMAGE and candidate == 'r307'), 'explicit inventory required for another candidate')
        require((single/'DONE').exists() and not (single/'FAILED').exists(), 'single-request campaign still active, missing DONE, or failed')
        start = read(single/'campaign-start.json')
        campaign_identity(start, image, candidate, contract_path)
        require('concurrency=1;' in start['scope'] and 'max_num_seqs=1;' in start['scope'], 'single-request campaign identity mismatch')
        for name in ('DONE', 'campaign-start.json', 'campaign.log', 'image-inspect.json'):
            cap.file(single/name,'single',single)
        inspected=read(single/'image-inspect.json')
        require(len(inspected)==1 and inspected[0]['Id']==image, 'campaign image inspect mismatch')
        if 'inventory_sha256' in start:
            check_inventory(single/'candidate-contract.sha256',contract_path)
            check_inventory(single/'candidate-observed.sha256',contract_path)
            for receipt in ('candidate-contract.sha256','candidate-observed.sha256','candidate-image-contract.log'):
                cap.file(single/receipt,'single',single)
            lines=(single/'candidate-image-contract.log').read_text().splitlines()
            require(any('IMAGE CONTRACT PASS:' in line and image in line for line in lines) and not any('SKIPPED' in line or 'FAIL' in line for line in lines), 'candidate preflight contract failed')
        for model in ('4b','9b'):
            oracle_path = single/f'{model}-oracle/result.json'
            oracle = read(oracle_path)
            for arm in ('oracle','mtp3-a','mtp3-b'):
                stage = f'{model}-{arm}'
                folder = single/stage
                data = read(folder/'result.json')
                env = read(folder/'launch-env.json')
                require(env['MAX_NUM_SEQS'] == '1' and env['SKIP_IMAGE_CONTRACT'] == '0' and env['IMAGE'] == image and env['EXPECTED_IMAGE_ID'] == image and env['MTP_DEPTH'] == ('0' if arm == 'oracle' else '3'), f'launch mismatch: {stage}')
                require(f'model={model};' in data['identity'] and image in data['identity'], f'probe identity mismatch: {stage}')
                if arm != 'oracle':
                    require(data['oracle_sha256'] == sha(oracle_path), 'oracle hash mismatch')
                summary['boundary'][stage] = boundary(data, None if arm == 'oracle' else oracle)
                for name in ('result.json','launch-env.json'):
                    cap.file(folder/name,'single',single)
                summary['contracts'][stage] = cap.contract(folder,single,'single')
                inspect_path = single/f'{candidate}-qual-{stage}-inspect.json'
                cap.file(inspect_path,'single',single)
                inspection = read(inspect_path)
                inspection = inspection[0] if isinstance(inspection,list) else inspection
                actual_env = dict(x.split('=',1) for x in inspection['Config']['Env'])
                require(inspection['Image'] == image and actual_env['REPRO_MAX_NUM_SEQS'] == '1' and actual_env['REPRO_TP'] == '1', f'actual boundary runtime mismatch: {stage}')
                summary['contracts'][stage]['runtime'] = {'source_sha256':sha(inspect_path),'image':inspection['Image'], 'args':inspection['Args'], 'repro_env':{k:v for k,v in actual_env.items() if k.startswith('REPRO_')}}
                for kind in ('preflight','postflight'):
                    summary['health'][f'{stage}-{kind}'] = cap.health(single,f'{stage}-{kind}','single')
        strict = single/'9b-strict'
        require((strict/'campaign-end.txt').exists() and not (strict/'ABORTED').exists(), 'strict campaign incomplete/aborted')
        all_rows = {}
        for arm in ('mtp0-a','mtp0-b','mtp3-a','mtp3-b'):
            folder = strict/arm
            cap.file(folder/'container-inspect.json','single',single)
            inspection = read(folder/'container-inspect.json')
            inspection = inspection[0] if isinstance(inspection,list) else inspection
            env = dict(x.split('=',1) for x in inspection['Config']['Env'])
            require(inspection['Image'] == image and env['REPRO_MAX_NUM_SEQS'] == '1' and env['REPRO_TP'] == '1', f'strict runtime identity mismatch: {arm}')
            data = read(folder/'strict/performance.json')
            rows = data['rows']
            require(len(rows) == 12 and len({r['prompt_id'] for r in rows}) == 12, 'strict needs full unique12')
            require(data['realistic_final_gate']['passed'] and data['fresh_response_validity']['valid'], 'strict workload gate failed')
            for row in rows:
                require(numeric(row['token_ids']) and len(row['token_ids']) == row['completion_tokens'] == row['stream_token_id_count'] and row['cached_tokens'] == 0, 'strict incomplete/nonzero-cache row')
            all_rows[arm] = {r['prompt_id']:r for r in rows}
            require(read(folder/'strict/canaries.json')['pass_all'], 'strict canaries failed')
            for name in ('performance.json','canaries.json','campaign-identity.json','models.json'):
                cap.file(folder/'strict'/name,'single',single)
            summary['contracts'][f'9b-strict-{arm}'] = cap.contract(folder,single,'single')
            summary['contracts'][f'9b-strict-{arm}']['runtime'] = {'image':inspection['Image'], 'args':inspection['Args'], 'repro_env':{k:v for k,v in env.items() if k.startswith('REPRO_')}}
            summary['health'][f'9b-strict-{arm}'] = cap.health(strict,f'{arm}-post','single-strict','strict')
        for left,right in [('mtp0-a','mtp0-b'),('mtp3-a','mtp3-b'),('mtp3-a','mtp0-a'),('mtp3-b','mtp0-a')]:
            a,b = all_rows[left],all_rows[right]
            require(set(a)==set(b), 'strict prompt set differs')
            require(all(a[k]['token_ids']==b[k]['token_ids'] and a[k]['prompt_sha256']==b[k]['prompt_sha256'] for k in a), f'strict actual IDs differ: {left}/{right}')
            summary['strict9b'][f'{left}-vs-{right}'] = {'passed': True, 'prompts': 12, 'tokens': sum(len(r['token_ids']) for r in a.values())}
        comparisons = list(strict.glob('compare-*.json'))
        require(len(comparisons)==4, 'strict comparison receipts missing')
        for path in comparisons:
            comparison = read(path)
            require(comparison['qualification']['strict_pair_qualified'], 'stored strict comparison failed')
            for side in ('left','right'):
                for artifact in comparison[side]['artifacts'].values():
                    original = Path(artifact['path'])
                    source = strict.parent.parent/original if not original.is_absolute() else original
                    require(source.is_relative_to(single), 'comparison source outside single campaign')
                    require(sha(source) == artifact['sha256'], 'strict comparison source hash mismatch')
            cap.file(path,'single',single)
        summary['health']['final'] = cap.health(single,'final','single')
        require((failed/'FAILED').exists(), 'failed c4 campaign marker missing')
        for name in ('FAILED','campaign-start.json','4b-oracle/result.json','4b-mtp3-a/result.json'):
            cap.file(failed/name,'failed',failed)
        negative = read(failed/'4b-mtp3-a/result.json')
        require(negative['status']=='complete' and negative['passed'] is False, 'negative c4 evidence has wrong status')
        cases = {c['id']:c for c in negative['cases']}
        differences = []
        for row in negative['rows']:
            want = cases[row['case']]['expected_ids']
            got = row.get('token_ids')
            if got != want:
                differences.append({'case':row['case'],'repeat':row['repeat'],'concurrency':row['concurrency'],
                    'got':got,'want':want,'error':row.get('error'), 'passed':False})
        require(differences and any(r['concurrency']==4 for r in differences), 'no independently verified c4 failures')
        summary['failed_c4'] = {'passed':False,'promotable':False,'different_rows':len(differences),'differences':differences}
        for name in ('observed.sha256','parent.txt','build-inputs.sha256','build.log','publication-baseline-remote.log','image.txt'):
            cap.file(rebuild/name,'rebuild',rebuild)
        require('Successfully built' in (rebuild/'build.log').read_text(), 'rebuild missing successful build receipt')
        inventory = check_inventory(rebuild/'observed.sha256', contract_path)
        cap.file(contract_path,'inventory',contract_path.parent)
        summary['rebuild'] = {'recorded':True,'image_identity_may_differ':True,'source_file_hashes_receipt':'evidence/rebuild/observed.sha256', **inventory}
        summary['passed'] = True
    except Exception as exc:
        summary['error'] = f'{type(exc).__name__}: {exc}'
    out.mkdir(parents=True,exist_ok=True)
    (out/'.gitattributes').write_text('evidence/** -whitespace\n')
    (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    (out/'source-manifest.json').write_text(json.dumps(cap.manifest,indent=2,ensure_ascii=False)+'\n')
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--single-root',type=Path,required=True)
    p.add_argument('--failed-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--image',default=IMAGE)
    p.add_argument('--candidate',default='r307')
    p.add_argument('--inventory',type=Path)
    p.add_argument('--rebuild-root',type=Path)
    a=p.parse_args()
    validate_output(a.single_root,a.failed_root,a.out)
    result=analyze(a.single_root,a.failed_root,a.out,a.image,a.candidate,a.inventory,a.rebuild_root)
    print(json.dumps({'passed':result['passed'],'error':result.get('error'),'out':str(a.out)}))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
