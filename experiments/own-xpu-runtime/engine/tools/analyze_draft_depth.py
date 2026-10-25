#!/usr/bin/env python3
"""Join discarded depth-2/3 proposals to verified output. No throughput projection."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def analyze(prompt, native, probes, require_verified=False, allow_output_only=False):
    require(isinstance(prompt, list) and len(prompt) >= 2 and all(type(t) is int and t >= 0 for t in prompt),
            'full prompt token IDs required')
    tokens = native['tokens']
    require(tokens and all(type(t) is int and t >= 0 for t in tokens), 'verified output IDs required')
    n = len(prompt)
    full = prompt + tokens
    drafts = {}
    have_controller = 'draft_rows' in native
    require(have_controller or allow_output_only, 'controller rows missing; explicitly allow output-only join')
    for row in native.get('draft_rows', []):
        position = row['position']
        require(type(position) is int and position not in drafts, 'duplicate/invalid controller draft position')
        drafts[position] = row
    seen = set()
    counts = {str(d): dict(eligible=0, accepted=0, prior_rejected=0, censored=0, unavailable=0) for d in (1, 2, 3)}
    timings = {str(d): [] for d in (2, 3)}
    verified = 0
    request_outputs = set()
    for row in probes:
        require(row.get('schema') == 'ownrt.draft-depth.cycle.v1' and row.get('discarded') is True
                and row.get('diagnostic_only') is True, 'not a discarded depth probe')
        position = row['d1_position']
        require(type(position) is int and position >= n and position not in seen, 'duplicate/shifted/non-decode probe position')
        seen.add(position)
        request_outputs.add(row['request_output'])
        require(row['confirmed_position'] == position - 1 and 0 <= position - 1 < len(full), 'confirmed prefix position mismatch')
        require(row['confirmed_token'] == full[position - 1], 'confirmed prefix token mismatch')
        require(row['restored_position'] == row['confirmed_position'], 'restored position mismatch')
        guesses = row['guesses']
        requested = row['requested_depth']
        require(requested in (2, 3) and 1 <= len(guesses) <= requested
                and all(type(t) is int and t >= 0 for t in guesses), 'invalid proposal depth/tokens')
        require(len(row['extra_pass_wall_ms']) == len(guesses) - 1, 'pass timing coverage mismatch')
        for value in row['extra_pass_wall_ms'] + [row[k] for k in ('snapshot_ms', 'restore_ms', 'probe_total_ms')]:
            require(type(value) in (int, float) and math.isfinite(value) and value >= 0, 'invalid diagnostic timing')
        require(type(row['snapshot_bytes']) is int and 0 < row['snapshot_bytes'] <= 32 * 1024**2,
                'snapshot exceeds declared memory reserve')
        require(row.get('mutable_bytes_verified') in (True, False), 'restoration verification status missing')
        if require_verified:
            require(row['mutable_bytes_verified'] is True, 'probe restoration not byte-verified')
        verified += int(row['mutable_bytes_verified'])
        if have_controller:
            control = drafts.get(position)
            require(control is not None and control['guess'] == guesses[0] and control['provider_error'] == 0,
                    'probe/controller d1 join mismatch')
            if position < len(full):
                require(control['actual'] == full[position], 'controller actual differs from emitted token')
        prefix_hit = True
        for depth in (1, 2, 3):
            result = counts[str(depth)]
            if depth > requested or depth > len(guesses):
                result['unavailable'] += 1
            elif position + depth - 1 >= len(full):
                result['censored'] += 1
            elif not prefix_hit:
                result['prior_rejected'] += 1
            else:
                result['eligible'] += 1
                hit = guesses[depth - 1] == full[position + depth - 1]
                result['accepted'] += int(hit)
                prefix_hit = prefix_hit and hit
        for depth, value in enumerate(row['extra_pass_wall_ms'], 2):
            timings[str(depth)].append(value)
    expected = ({position for position, row in drafts.items()
                 if position >= n and type(row['guess']) is int and row['guess'] >= 0 and row['provider_error'] == 0}
                if have_controller else set(range(n, n + len(tokens))))
    require(seen == expected, 'missing/extra probe positions; flush last probe before analysis')
    require(seen and len(request_outputs) == 1, 'one nonempty request trace required')
    for result in counts.values():
        result['conditional_acceptance'] = result['accepted'] / result['eligible'] if result['eligible'] else None
    return dict(schema='ownrt.draft-depth.analysis.v1', diagnostic_only=True, qualifying=False,
                alignment='controller-and-output' if have_controller else 'request-position-and-output-only',
                request_output=next(iter(request_outputs)),
                prompt_tokens=n, generated_tokens=len(tokens), cycles=len(seen),
                mutable_bytes_verified_cycles=verified, conditional_depth=counts,
                extra_pass_wall_ms_mean={key: statistics.mean(values) if values else None for key, values in timings.items()},
                target_tokens_sha256=digest(json.dumps(tokens, separators=(',', ':')).encode()),
                limitation='Acceptance and perturbed diagnostic costs only; no PP4 speed, general quality, or losslessness claim.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prompt-ids', required=True, type=Path, help='JSON array of full prompt token IDs')
    parser.add_argument('--native-result', required=True, type=Path)
    parser.add_argument('--probes', required=True, type=Path)
    parser.add_argument('--reference-result', type=Path, help='optional baseline native-result; output IDs must match')
    parser.add_argument('--require-verified', action='store_true')
    parser.add_argument('--allow-output-only', action='store_true', help='accept token-only result; require full output-position coverage')
    parser.add_argument('--request-output', help='exact request_output string selecting a request from the persistent trace')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    raw = {key: getattr(args, key).read_bytes() for key in ('prompt_ids', 'native_result', 'probes')}
    native = json.loads(raw['native_result'])
    probes = [json.loads(line) for line in raw['probes'].splitlines() if line]
    if args.request_output is not None:
        probes = [row for row in probes if row.get('request_output') == args.request_output]
    result = analyze(json.loads(raw['prompt_ids']), native, probes, args.require_verified, args.allow_output_only)
    if args.reference_result:
        raw['reference_result'] = args.reference_result.read_bytes()
        reference = json.loads(raw['reference_result'])
        require(reference['tokens'] == native['tokens'], 'probe output differs from reference')
        result['reference_output_exact'] = True
    result['sources_sha256'] = {key: digest(data) for key, data in raw.items()}
    result['analyzer_sha256'] = digest(Path(__file__).read_bytes())
    with args.output.open('x') as output:
        json.dump(result, output, indent=2, ensure_ascii=False, allow_nan=False)
        output.write('\n')


if __name__ == '__main__':
    main()
