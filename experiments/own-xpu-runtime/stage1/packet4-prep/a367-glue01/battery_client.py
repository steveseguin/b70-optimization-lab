#!/usr/bin/env python3
"""A367 assertions port. Timed cold suite first; no server lifecycle or retries."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
MODEL = 'qwen38-flash-next-fp8-tp4'
PYTHON = '/home/steve/.venvs/vllm-xpu/bin/python'
TOKENIZER = '/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8'
RESULT = 'realistic-suite-v1-result.json'
RECORD = 'experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json'
SUITE = 'repro/rapid-model-snapshots-b70/realistic-suite-v1.json'
FIXTURE = 'data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json'
CHECKER = 'repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/check-replay-result.py'
QUALITY = 'scripts/qwen38-text-quality-suite.py'
SHORT = 'scripts/bench-openai-concurrency.py'
DEPTH = 'scripts/bench-openai-token-depth-suite.py'
DEPENDENCIES = {
    RECORD: 'f88da9b4e041255dc36363363bd78756ebcd10418953e1ea7477d63e7b8014dc',
    SUITE: '0ad543d1c1f379a0b6cee88e06236e495c45eee7ba12cfcef062b6e03303e812',
    FIXTURE: 'c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d',
    CHECKER: 'a35291eec001f55766305cc853e2ee08f27e08f196732b6fb8558ca75cba955f',
    QUALITY: '268f6de4a3e4353191d4f75c48b6b0f243ca30196fcb4c582e1db2e2935db656',
    SHORT: 'd590c63c87b1e664417b4198dbbb873cbe4f252509fa8f9fc50830efca2b4cf4',
    DEPTH: '8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067',
    'scripts/bench-openai-realistic-suite.py': '7b4aef6fca0ffebf6ab83ac0b70bb13505cb4b93010f45529623dcf8892fc130',
}
DEPTH_PINS = {
    2048: ('a173e60e5047c0f080e0ea45680eecbb533d30946cfc2ae0e028c684bf18d1ba', '3aa1bba4d0ade3c07e7cad10bb5ee01245dc194d28dc17359311ece3b4ab6f36', 'afffd2110812762164862b6388f054bb56696ee57b07eadce411a702c40bc714'),
    4096: ('aedf2eb779bfa4aad8f533c644ca94646977deae1c10221bff592f06785c76d0', '2d92a2857d5cf45c3dcbc9d856cba714e2a36003295159fb5fcf1a8effb930be', '1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc'),
}
REPEAT_PIN = '3b0b3192cd70de9c19caf7a6f6f69a4dda63cc4e66049c2cf9c15633103896b7'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def token_hash(ids):
    return hashlib.sha256(json.dumps(ids, separators=(',', ':'), sort_keys=True).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, obj):
    with Path(path).open('x') as out:
        json.dump(obj, out, indent=2, sort_keys=True)
        out.write('\n')


def verify_dependencies():
    for path, expected in DEPENDENCIES.items():
        require(sha(REPO / path) == expected, 'dependency hash changed: ' + path)


def usage_gate(usage, *, created=True):
    require(usage['total_tokens'] == usage['prompt_tokens'] + usage['completion_tokens'], 'usage total mismatch')
    details = usage['prompt_tokens_details']
    require(details['cached_tokens'] == 0, 'cached tokens nonzero')
    if created:
        require(details['created_cache_tokens'] == 0, 'created cache tokens nonzero')


def validate_realistic(result, record):
    require(len(result['rows']) == len(record['rows']) == 12, 'need complete 12 prompt suite')
    for key in ('prompt_sha256s', 'output_sha256s'):
        require(result[key] == record[key], key + ' differs')
    for section in ('fresh_response_validity', 'realistic_final_gate'):
        for key, value in record[section].items():
            if isinstance(value, bool):
                require(result[section].get(key) is value, section + '.' + key + ' differs')
    require(result['realistic_final_gate']['passed'] is True, 'realistic final gate failed')
    for i, (row, oracle) in enumerate(zip(result['rows'], record['rows'])):
        for key in ('prompt_id', 'prompt_index', 'prompt_class', 'prompt_sha256', 'text', 'token_ids', 'finish_reasons', 'completion_tokens', 'prompt_tokens'):
            require(row[key] == oracle[key], f'realistic row {i}: {key} differs')
        require(hashlib.sha256(row['text'].encode()).hexdigest() == row['sha256'] == result['output_sha256s'][i], 'text/hash mismatch')
        require(row['prompt_sha256'] == result['prompt_sha256s'][i], 'prompt/hash mismatch')
        require(row['cached_tokens'] == 0, 'realistic cache nonzero')
        usage_gate(row['usage'], created=False)
        require(row['usage']['completion_tokens'] == len(row['token_ids']), 'incomplete output token array')
    identity = result['run_identity']
    for key in ('api_mode', 'model', 'max_tokens', 'seed', 'request_extra', 'system_prompt', 'return_token_ids', 'selected_prompt_ids'):
        require(identity[key] == record['run_identity'][key], 'request identity differs: ' + key)
    return True


def validate_quality(q, returncode):
    require(q['baseline_status'] == 'not_run' and q['baseline_match_all'] is None, 'quality baseline changed')
    cases = q['exact_cases']
    require(len(cases) == 7 and len({c['name'] for c in cases}) == 7, 'quality cases incomplete')
    failures = [case for case in cases if case['pass'] is not True]
    require(not failures or (len(failures) == 1 and failures[0]['name'] == 'code_execution' and failures[0]['normalized'] == '30'), 'new quality failure')
    require(returncode == len(failures), 'quality returncode mismatch')
    repeat = q['repeat_case']
    require(repeat['pass'] is True and repeat['repeats'] == 16 and len(repeat['runs']) == 16, 'need 16/16 repeats')
    require(repeat['unique_hashes'] == [REPEAT_PIN], 'repeat oracle changed')
    for run in repeat['runs']:
        require(run['sha256'] == REPEAT_PIN and hashlib.sha256(run['normalized'].encode()).hexdigest() == REPEAT_PIN, 'repeat bytes changed')
    needle = q['long_context_case']
    require(needle['pass'] is True and needle['usage']['prompt_tokens'] == 2048, 'needle failed')
    require(needle['needle'] == 'B70_QWEN38_NEEDLE_20260816' and needle['needle'] in needle['normalized'], 'needle bytes differ')
    for case in [*cases, *repeat['runs'], needle]:
        usage_gate(case['usage'])
    return {'exact_cases_passed': 7 - len(failures), 'known_code_execution_30_exception': bool(failures), 'repeats': 16, 'needle': True}


def validate_depth(item, depth):
    prompt, payload, output = DEPTH_PINS[depth]
    require(item['status'] == 'passed' and item['gate']['passed'] is True, 'depth gate failed')
    require(item['request']['prompt_token_ids_sha256'] == prompt, 'depth prompt changed')
    require(item['request']['request_payload_sha256'] == payload, 'depth request changed')
    require(item['run_identity']['configured_context_capacity'] == 4352, 'depth capacity changed')
    response = item['response']; usage = response['usage']
    require((usage['prompt_tokens'], usage['completion_tokens'], usage['total_tokens']) == (depth, 128, depth + 128), 'depth usage changed')
    usage_gate(usage, created=False)
    require(response['finish_reasons'] == ['length'] and len(response['token_ids']) == 128, 'depth finish/output length changed')
    require(response['output_token_ids_sha256'] == output and token_hash(response['token_ids']) == output, 'depth token-array pin changed')
    return True


def validate_short(items):
    require(len(items) == 3, 'short diagnostics incomplete')
    for item in items:
        validate_short_record(item)


def validate_short_record(item):
    require(len(item['scenarios']['c1']['records']) == 1, 'short diagnostic request count changed')
    row = item['scenarios']['c1']['records'][0]
    require((row['prompt_tokens'], row['completion_tokens'], row['total_tokens']) == (146, 256, 402), 'short usage changed')
    require(row['sha256'] == '5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0', 'short hash changed')


def validate_canary(result):
    choice = result['choices'][0]; usage = result['usage']
    require(result['model'] == MODEL and choice['finish_reason'] == 'stop' and choice['message']['content'].strip() == 'OK', 'recovery canary changed')
    require((usage['prompt_tokens'], usage['completion_tokens'], usage['total_tokens']) == (17, 2, 19), 'canary usage changed')
    usage_gate(usage)


def prefix():
    # Future supervised launches inherit the record's nice0. CPU build/test
    # commands themselves run at nice19; that is not a benchmark treatment.
    return ['taskset', '-c', '4-15,20-31', PYTHON, '-B']


def commands(root, base_url):
    def task(name, script, args, allowed=(0,)):
        return {'name': name, 'command': prefix() + [str(script)] + args, 'allowed_returncodes': list(allowed)}
    jobs = [task('realistic-suite-v1-result', HERE / 'realistic_entry.py', [
        '--base-url', base_url, '--model', MODEL, '--api-mode', 'chat', '--suite', str(REPO / SUITE),
        '--max-tokens', '512', '--metric-tokens', '100', '--seed', '20260609', '--timeout', '900',
        '--return-token-ids', '--request-extra-json', '{"chat_template_kwargs":{"enable_thinking":false},"seed":20260609,"temperature":0,"top_p":1.0}', '--out', str(root / RESULT)]),
        task('check-replay-result', REPO / CHECKER, [str(root / RESULT)]),
        task('quality-current', REPO / QUALITY, ['--base-url', base_url, '--model', MODEL, '--tokenizer', TOKENIZER,
        '--timeout', '900', '--seed', '20260609', '--repeat-runs', '16', '--request-id-prefix', 'a367-glue01',
        '--long-context-tokens', '2157', '--chat-template-kwargs-json', '{"enable_thinking":false}', '--output-json', str(root / 'quality-current.json')], (0, 1))]
    for i in range(1, 4):
        jobs.append(task(f'bench-short-r{i}', REPO / SHORT, ['--base-url', base_url, '--tokenizer', TOKENIZER,
            '--prompt-tokens', '128', '--output-tokens', '256', '--concurrency', '1', '--warmups', str(int(i == 1)),
            '--timeout', '300', '--seed', '20260828', '--output-json', str(root / f'bench-short-r{i}.json')]))
    for depth in (2048, 4096):
        for i in (1, 2):
            name = f'exact-depth-{depth // 1024}k-r{i}'
            jobs.append(task(name, REPO / DEPTH, ['--execute', '--fixture', str(REPO / FIXTURE), '--depth', str(depth),
                '--context-capacity', '4352', '--base-url', base_url, '--model', MODEL, '--response-adapter', 'vllm',
                '--timeout', '900' if depth == 2048 else '1400', '--out', str(root / (name + '.json'))]))
    return jobs


def metrics_snapshot(base_url):
    try:
        with urllib.request.urlopen(base_url.rstrip('/') + '/metrics', timeout=20) as response:
            return response.read().decode()
    except Exception as exc:
        return '# unavailable: ' + type(exc).__name__ + '\n'


def parse_counters(text):
    counters = {}
    for line in text.splitlines():
        match = re.fullmatch(r'([a-zA-Z_:][\w:]*)(\{[^\n]*\})?\s+([-+\d.eE]+)(?:\s+\d+)?', line)
        if match and ('spec_decode' in match[1] or 'cudagraph' in match[1]):
            value = float(match[3])
            if math.isfinite(value):
                counters[match[1] + (match[2] or '')] = value
    return counters


def report(result, before='', after=''):
    rows = result['rows']; groups = {}
    for row in rows:
        offsets = row['token_id_offsets_s']
        require(len(offsets) >= 100 and offsets[99] > offsets[0], 'invalid metric timestamps')
        rate = 99 / (offsets[99] - offsets[0])
        groups.setdefault(row['prompt_class'], []).append(rate)
    medians = {key: statistics.median(values) for key, values in groups.items()}
    first, last = parse_counters(before), parse_counters(after)
    deltas = {key: value - first[key] for key, value in last.items() if key in first and value >= first[key]}
    def total(name):
        values = [value for key, value in deltas.items() if key.split('{')[0] == name]
        return sum(values) if values else None
    accepted = total('vllm:spec_decode_num_accepted_tokens_total')
    drafted = total('vllm:spec_decode_num_draft_tokens_total')
    return {'class_balanced_99_interval_median_tok_s': statistics.median(medians.values()),
        'class_medians_tok_s': medians, 'all_prompt_99_interval_median_tok_s': statistics.median([v for values in groups.values() for v in values]),
        'ttft_s': [r['ttft_s'] for r in rows], 'ttft_median_s': statistics.median(r['ttft_s'] for r in rows),
        'full_response_wall_s': [r['elapsed_s'] for r in rows], 'full_response_wall_total_s': sum(r['elapsed_s'] for r in rows),
        'full_response_wall_median_s': statistics.median(r['elapsed_s'] for r in rows),
        'acceptance': {'accepted_tokens': accepted, 'draft_tokens': drafted, 'ratio': accepted / drafted if accepted is not None and drafted else None,
            'scope': 'timed realistic suite only; null means endpoint counters unavailable'},
        'M1_steps': None, 'M2_steps': None, 'step_count_status': 'not exposed by the unchanged untraced record runtime; raw graph counters retained if available',
        'counter_deltas': deltas, 'metric_events': 100, 'metric_intervals': 99, 'metric_numerator': 99,
        'metric_endpoints': [{'prompt_id': r['prompt_id'], 'first_s': r['token_id_offsets_s'][0], 'last_s': r['token_id_offsets_s'][99]} for r in rows],
        'speed_is_pass_gate': False, 'promotion_eligible': False,
        'limitation': 'One control/candidate pair is a screen, not fresh-candidate determinism or a record.'}


def run(root, base_url, arm, *, run_command=subprocess.run, snapshot=metrics_snapshot, canary=None):
    verify_dependencies()
    root.mkdir(parents=True, exist_ok=True)
    jobs = commands(root, base_url)
    for name in [RESULT, 'battery-result.json', 'report.json', 'recovery-canary.json', 'metrics-before-suite.prom', 'metrics-after-suite.prom'] + [j['name'] + suffix for j in jobs for suffix in ('.json', '.log', '.rc')]:
        require(not (root / name).exists(), 'refusing overwrite: ' + name)
    before = snapshot(base_url); (root / 'metrics-before-suite.prom').write_text(before)
    receipts = []; started = time.monotonic()
    for job in jobs:
        with (root / (job['name'] + '.log')).open('x') as log:
            completed = run_command(job['command'], cwd=REPO, stdout=log, stderr=subprocess.STDOUT, check=False)
        rc = completed.returncode
        (root / (job['name'] + '.rc')).write_text(str(rc) + '\n')
        receipts.append({'name': job['name'], 'returncode': rc})
        require(rc in job['allowed_returncodes'], job['name'] + ' failed')
        if job['name'] == 'realistic-suite-v1-result':
            after = snapshot(base_url); (root / 'metrics-after-suite.prom').write_text(after)
            validate_realistic(read(root / RESULT), read(REPO / RECORD))
        elif job['name'] == 'check-replay-result':
            payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': 'Reply with exactly: OK'}],
                'chat_template_kwargs': {'enable_thinking': False}, 'temperature': 0, 'top_p': 1.0,
                'seed': 20260609, 'max_tokens': 8, 'stream': False}
            if canary is None:
                request = urllib.request.Request(base_url.rstrip('/') + '/v1/chat/completions', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
                with urllib.request.urlopen(request, timeout=180) as response:
                    response_json = json.load(response)
            else:
                response_json = canary(payload)
            write(root / 'recovery-canary.json', response_json); validate_canary(response_json)
        elif job['name'] == 'quality-current':
            quality = validate_quality(read(root / 'quality-current.json'), rc)
        elif job['name'].startswith('bench-short-'):
            validate_short_record(read(root / (job['name'] + '.json')))
        elif job['name'].startswith('exact-depth-'):
            validate_depth(read(root / (job['name'] + '.json')), 2048 if '2k' in job['name'] else 4096)
    validate_short([read(root / f'bench-short-r{i}.json') for i in (1, 2, 3)])
    result = report(read(root / RESULT), before, after)
    result.update({'arm': arm, 'exact': True, 'quality': quality, 'exact_depth_repeats': {'2048': 2, '4096': 2},
                   'battery_wall_s': time.monotonic() - started, 'jobs': receipts})
    write(root / 'report.json', result)
    write(root / 'battery-result.json', {'schema': 'a367-glue01-battery-v1', 'arm': arm, 'exact': True, 'passed': True,
        'timed_suite_first': True, 'record_sha256': DEPENDENCIES[RECORD], 'report_sha256': sha(root / 'report.json'),
        'artifacts': {path.name: sha(path) for path in root.iterdir() if path.name in {
            RESULT, 'report.json', 'recovery-canary.json', 'metrics-before-suite.prom', 'metrics-after-suite.prom',
            *[j['name'] + '.json' for j in jobs]}}})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--base-url', default='http://127.0.0.1:19980')
    parser.add_argument('--arm', required=True, choices=('control', 'candidate'))
    parser.add_argument('--plan', action='store_true')
    args = parser.parse_args()
    if args.plan:
        verify_dependencies()
        print(json.dumps({'native_executed': False, 'arm': args.arm, 'commands': commands(args.output, args.base_url), 'canary_position': 'after checker, before quality', 'timed_suite_first': True}, indent=2))
        return 0
    run(args.output, args.base_url, args.arm)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
