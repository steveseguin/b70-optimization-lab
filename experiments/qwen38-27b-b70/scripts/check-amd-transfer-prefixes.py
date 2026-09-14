#!/usr/bin/env python3
"""Fail-fast, six-class output-prefix screen. No restart or promotion policy."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

REPO = Path(__file__).resolve().parents[3]
SUITE = REPO / 'repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json'
CLASSES = {'analysis', 'code', 'documentation', 'operations', 'prose', 'structured-writing'}
LIMIT = 64


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def token_ids(value):
    return isinstance(value, list) and bool(value) and all(type(x) is int and x >= 0 for x in value)


def load_plan(suite_path, reference_path, model):
    suite_raw, reference_raw = suite_path.read_bytes(), reference_path.read_bytes()
    suite, reference = json.loads(suite_raw), json.loads(reference_raw)
    identity = reference['run_identity']
    require(identity['api_mode'] == 'completions', 'Reference must use raw completions.')
    require(identity['seed'] == 42 and identity['request_extra'] == {'temperature': 0, 'top_p': 1},
            'Reference sampling parameters differ from temperature0/top_p1/seed42.')
    require(identity['system_prompt'] is None and identity['max_tokens'] == 512
            and identity['require_natural_eos'] is True and identity['return_token_ids'] is True,
            'Reference must contain natural-completion, full512 token-ID evidence.')
    require(reference['realistic_final_gate']['passed'] is True
            and reference['fresh_response_validity']['valid'] is True,
            'Reference workload/cache gate did not pass.')
    require(identity['suite']['suite_id'] == suite['suite_id'], 'Reference suite identity differs.')
    rows = reference['rows']
    indexed = {row['prompt_id']: row for row in rows}
    prompts = suite['prompts']
    require(len(indexed) == len(rows) == len(prompts)
            and set(indexed) == {p['id'] for p in prompts}, 'Reference prompt coverage differs.')
    selected, seen = [], set()
    for prompt in prompts:
        row = indexed[prompt['id']]
        require(row['prompt_sha256'] == sha(prompt['prompt'].encode()),
                'Reference prompt text hash differs: ' + prompt['id'])
        require(row['prompt_class'] in CLASSES, 'Unrecognized reference workload class.')
        require(type(row['prompt_tokens']) is int and row['prompt_tokens'] > 0
                and row['usage']['prompt_tokens'] == row['prompt_tokens'],
                'Reference input token count is missing/inconsistent: ' + prompt['id'])
        require(type(row['cached_tokens']) is int and row['cached_tokens'] == 0
                and type(row['usage']['prompt_tokens_details']['cached_tokens']) is int
                and row['usage']['prompt_tokens_details']['cached_tokens'] == 0,
                'Reference cache receipt is missing/nonzero: ' + prompt['id'])
        ids = row['token_ids']
        require(token_ids(ids) and len(ids) == row['completion_tokens']
                == row['usage']['completion_tokens'] and len(ids) <= 512,
                'Reference output token evidence is incomplete: ' + prompt['id'])
        require(row['finish_reasons'] and row['finish_reasons'][-1] in ('stop', 'length'),
                'Reference finish reason is unknown: ' + prompt['id'])
        if row['prompt_class'] not in seen:
            seen.add(row['prompt_class'])
            selected.append({
                'prompt_id': prompt['id'], 'prompt_class': row['prompt_class'],
                'prompt_sha256': row['prompt_sha256'], 'prompt_tokens': row['prompt_tokens'],
                'expected_token_ids': ids[:LIMIT],
                'expected_finish_reason': 'length' if len(ids) > LIMIT else row['finish_reasons'][-1],
                'request': {'model': model, 'prompt': prompt['prompt'], 'max_tokens': LIMIT,
                            'temperature': 0, 'top_p': 1, 'seed': 42,
                            'return_token_ids': True, 'stream': False},
            })
    require(seen == CLASSES and len(selected) == 6, 'Reference must cover all six classes.')
    return {'suite_sha256': sha(suite_raw), 'reference_sha256': sha(reference_raw),
            'suite_path': str(suite_path), 'reference_path': str(reference_path),
            'reference_model': identity['model'], 'candidate_model': model, 'selected': selected}


def compare_response(case, response):
    require(isinstance(response, dict) and 'error' not in response, 'Server returned an error object.')
    choices = response['choices']
    require(len(choices) == 1, 'Expected exactly one completion.')
    choice, usage = choices[0], response['usage']
    actual = choice.get('token_ids')
    require(token_ids(actual), 'Completion token IDs are missing or nonnumeric.')
    require(type(usage['completion_tokens']) is int and len(actual) == usage['completion_tokens'],
            'Returned token IDs do not cover the complete response.')
    require(type(usage['prompt_tokens']) is int and usage['prompt_tokens'] == case['prompt_tokens'],
            'Candidate input token count differs from reference.')
    cached = usage['prompt_tokens_details']['cached_tokens']
    require(type(cached) is int and cached == 0, 'Cache receipt must explicitly report integer zero.')
    expected = case['expected_token_ids']
    first = next((i for i in range(max(len(expected), len(actual)))
                  if (expected[i] if i < len(expected) else None)
                  != (actual[i] if i < len(actual) else None)), None)
    finish = choice.get('finish_reason')
    return {'passed': first is None and finish == case['expected_finish_reason'],
            'actual_token_ids': actual, 'expected_token_ids': expected,
            'first_mismatch_index': first, 'finish_reason': finish,
            'expected_finish_reason': case['expected_finish_reason'],
            'prompt_tokens': usage['prompt_tokens'], 'cached_tokens': cached,
            'reason': None if first is None and finish == case['expected_finish_reason']
                      else 'Combined candidate output or termination differs from the captured control.'}


def run(args):
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    summary = {'schema': 'neural.download.amd-transfer-prefix-screen.v1',
               'created_at': dt.datetime.now(dt.timezone.utc).isoformat(),
               'status': 'preflight', 'screening_only': True, 'passed': False,
               'realistic_final_gate': {'passed': False}, 'requests_sent': 0, 'rows': [],
               'interpretation': 'This screens the combined candidate against captured controls. '
                                 'A difference does not identify the drafter as its cause. '
                                 'A pass is not full-suite quality, determinism or performance promotion.'}
    write_json(output / 'summary.json', summary)
    try:
        plan = load_plan(args.suite.resolve(), args.reference_performance.resolve(), args.model)
        write_json(output / 'plan.json', plan)
        if args.check_only:
            summary['status'] = 'preflight_passed_not_run'
            write_json(output / 'summary.json', summary)
            return 0
        base = args.base_url.rstrip('/')
        endpoint = base + '/completions' if base.endswith('/v1') else base + '/v1/completions'
        summary['endpoint'] = endpoint
        summary['status'] = 'running'
        for index, case in enumerate(plan['selected']):
            prefix = output / f'{index:02d}-{case["prompt_id"]}'
            prefix.mkdir()
            write_json(prefix / 'request.json', case['request'])
            row = {k: case[k] for k in ('prompt_id', 'prompt_class', 'prompt_sha256', 'prompt_tokens')}
            summary['rows'].append(row)
            summary['requests_sent'] += 1
            write_json(output / 'summary.json', summary)
            request = urllib.request.Request(endpoint, data=json.dumps(case['request']).encode(),
                                             headers={'Content-Type': 'application/json'}, method='POST')
            started = time.monotonic()
            try:
                with urllib.request.urlopen(request, timeout=args.timeout) as reply:
                    raw = reply.read()
                    row['http_status'] = reply.status
            except urllib.error.HTTPError as exc:
                (prefix / 'response.raw').write_bytes(exc.read())
                row['http_status'] = exc.code
                raise
            (prefix / 'response.raw').write_bytes(raw)
            row['elapsed_s'] = time.monotonic() - started
            row['response_sha256'] = sha(raw)
            response = json.loads(raw)
            write_json(prefix / 'response.json', response)
            comparison = compare_response(case, response)
            write_json(prefix / 'comparison.json', comparison)
            row.update(comparison)
            write_json(output / 'summary.json', summary)
            require(comparison['passed'], comparison['reason'])
        summary.update(status='prefix_screen_passed', passed=True)
        write_json(output / 'summary.json', summary)
        return 0
    except Exception as exc:
        summary.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        if summary['rows'] and not summary['rows'][-1].get('passed', False):
            summary['rows'][-1].update(passed=False, error=summary['error'])
        write_json(output / 'summary.json', summary)
        print(summary['error'], flush=True)
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, default=SUITE)
    parser.add_argument('--reference-performance', type=Path, required=True)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--check-only', action='store_true', help='Validate inputs without contacting the endpoint.')
    args = parser.parse_args()
    parser.error('--timeout must be positive') if args.timeout <= 0 else None
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
