#!/usr/bin/env python3
"""Finalize retained per-prompt evidence from a gracefully flushed probe trace.

CPU-only; never calls the service. Existing partial captures stay unchanged.
Outputs are created exclusively, so an existing finalization is not overwritten.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[4]
LANE = ROOT / 'experiments/own-xpu-runtime'
ANALYZER = LANE / 'engine/tools/analyze_draft_depth.py'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace', required=True, type=Path)
    parser.add_argument('--captures', required=True, type=Path)
    parser.add_argument('--control', required=True, type=Path)
    parser.add_argument('--baseline', type=Path, default=LANE / 'gsq-rco-iq3s/service-speed/d-mtp-fp8/suite/f32-suite-297b388764e9.json')
    args = parser.parse_args()
    module_spec = importlib.util.spec_from_file_location('depth_analysis', ANALYZER)
    analyzer = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(analyzer)
    inputs = {}
    def read(path):
        data = path.read_bytes()
        inputs[str(path.resolve())] = {'sha256': sha(data), 'bytes': len(data)}
        return data
    terminal = json.loads(read(args.control / 'terminal.json'))
    require(terminal['passed'] is True and terminal['drained'] is True and terminal['first_error'] is None
            and terminal['monitor_first'] is None, 'clean graceful closure required before final extraction')
    baseline = json.loads(read(args.baseline))
    reference = {row['prompt_id']: row for row in baseline['rows']}
    identity = json.loads(read(args.captures / 'service-identity.json'))
    require(Path(identity['control']['path']).resolve() == args.control.resolve(), 'control identity differs')
    plan_raw = read(args.captures / 'plan.json')
    require(sha(plan_raw) == identity['plan_sha256'], 'retained plan identity differs')
    trace_raw = read(args.trace)
    require(trace_raw.endswith(b'\n'), 'final trace has incomplete last line')
    trace = {}
    for line in trace_raw.splitlines(keepends=True):
        if line.strip():
            row = json.loads(line)
            trace.setdefault(row['request_output'], []).append((line, row))
    sources = sorted(args.captures.glob('*/capture.json'))
    require({p.parent.name for p in sources} == set(reference), 'full fixed suite capture set differs from baseline')
    completed = []
    writes = []
    all_probes = []
    for capture_path in sources:
        folder = capture_path.parent
        capture = json.loads(read(capture_path))
        require(capture['plan_sha256'] == identity['plan_sha256'], 'per-request plan mismatch')
        prompt_raw = read(folder / 'prompt-token-ids.json')
        native_raw = read(folder / 'rank0/native-result.json')
        response_raw = read(folder / 'http-response.json')
        native, prompt, response = json.loads(native_raw), json.loads(prompt_raw), json.loads(response_raw)
        require(sha(native_raw) == capture['native_result_sha256'], 'captured native result changed')
        require(response['ownrt']['request'] == capture['request'] and native['tokens'] == response['ownrt']['output_token_ids'],
                'HTTP/native capture mismatch')
        require(response['usage']['prompt_tokens_details']['cached_tokens'] == 0, 'request was not cold')
        expected = reference[folder.name]
        require(prompt == expected['prompt_token_ids'], 'baseline prompt token identity differs')
        selected = trace.get(capture['request_output'], [])
        require(selected, 'request absent from flushed trace')
        final_raw = b''.join(line for line, _ in selected)
        probes = [row for _, row in selected]
        partial_raw = read(folder / 'rank0/draft-depth-probe-partial.jsonl')
        partial = [json.loads(line) for line in partial_raw.splitlines() if line]
        require(partial == probes[:len(partial)], 'partial capture is not a prefix of the flushed request trace')
        result = analyzer.analyze(prompt, native, probes, require_verified=True)
        result.update(prompt_id=folder.name, request=capture['request'],
                      reference_output_ids_exact=native['tokens'] == expected['output_token_ids'],
                      reference_text_hash_exact=sha(response['choices'][0]['message']['content'].encode()) == expected['output_sha256'],
                      partial_cycles=len(partial), final_cycles=len(probes),
                      sources_sha256={'prompt_ids': sha(prompt_raw), 'native_result': sha(native_raw),
                                      'partial_trace': sha(partial_raw), 'final_trace': sha(final_raw),
                                      'baseline_suite': sha(args.baseline.read_bytes())},
                      analyzer_sha256=sha(ANALYZER.read_bytes()))
        completed.append(result)
        all_probes += probes
        writes += [(folder / 'rank0/draft-depth-probe-final.jsonl', final_raw),
                   (folder / 'depth-analysis.json', (json.dumps(result, indent=2, ensure_ascii=False) + '\n').encode())]
    pooled = {}
    for depth in ('1', '2', '3'):
        row = {key: sum(r['conditional_depth'][depth][key] for r in completed)
               for key in ('eligible', 'accepted', 'prior_rejected', 'censored', 'unavailable')}
        row['conditional_acceptance'] = row['accepted'] / row['eligible'] if row['eligible'] else None
        row['observable_prefix_cycles'] = row['eligible'] + row['prior_rejected']
        row['complete_prefix_acceptance'] = row['accepted'] / row['observable_prefix_cycles'] if row['observable_prefix_cycles'] else None
        require(sum(row[k] for k in ('eligible', 'prior_rejected', 'censored', 'unavailable')) == len(all_probes), 'pooled censor accounting differs')
        pooled[depth] = row
    closure = {}
    for name in ('terminal.json', 'monitor.json', 'run.json', 'selftest-result.json', 'prefill-gate.json'):
        data = read(args.control / name)
        closure[name] = json.loads(data)
        writes.append((args.captures / 'closure' / name, data))
    gate_dir = LANE / 'gsq-rco-iq3s/serving/lan/evidence'
    for gate in sorted(gate_dir.glob('*' + identity['binary_sha256'][:16] + '*')):
        data = read(gate)
        closure[gate.name] = json.loads(data)
        writes.append((args.captures / 'closure' / gate.name, data))
    summary = dict(schema='ownrt.draft-depth.suite-finalization.v1', diagnostic_only=True, qualifying=False,
                   binary_sha256=identity['binary_sha256'], prompts=len(completed),
                   generated_tokens=sum(r['generated_tokens'] for r in completed), cycles=len(all_probes),
                   mutable_bytes_verified_cycles=sum(r['mutable_bytes_verified_cycles'] for r in completed),
                   full_output_ids_exact=all(r['reference_output_ids_exact'] for r in completed),
                   full_output_text_hashes_exact=all(r['reference_text_hash_exact'] for r in completed),
                   baseline=str(args.baseline), pooled_conditional_depth=pooled,
                   cycle_weighted_extra_pass_wall_ms={str(depth): statistics.mean(r['extra_pass_wall_ms'][depth - 2] for r in all_probes
                                                  if len(r['extra_pass_wall_ms']) >= depth - 1) for depth in (2, 3)},
                   diagnostic_cost_ms={key: dict(mean=statistics.mean(r[key] for r in all_probes), median=statistics.median(r[key] for r in all_probes))
                                       for key in ('snapshot_ms', 'restore_ms', 'probe_total_ms')},
                   per_prompt=completed, closure=closure, input_sources=inputs,
                   analyzer_sha256=sha(ANALYZER.read_bytes()), finalizer_sha256=sha(Path(__file__).read_bytes()),
                   limitations=['One fixed suite, greedy outputs, this model/draft/runtime identity only.',
                                'Depth-2 and depth-3 conditional rates use only positions whose preceding guesses were right.',
                                'Complete-prefix rates exclude unavailable/censored positions; do not multiply conditional rates with different denominators.',
                                'Probes are discarded and full draft restoration is checked; instrumented timings are not serving speed or PP4 performance.',
                                'Unresolved CPU-reference disagreements remain; exactness here is versus retained GPU baseline 297b388764e9.',
                                'The cumulative flushed RAM trace includes startup gates; only request_output-matched suite rows enter this result.'])
    writes.append((args.captures / 'depth-summary.json', (json.dumps(summary, indent=2, ensure_ascii=False) + '\n').encode()))
    require(not any(path.exists() for path, _ in writes), 'a final output already exists; refusing overwrite')
    # Complete validation precedes creation; partial capture bytes are untouched.
    (args.captures / 'closure').mkdir(exist_ok=False)
    for path, data in writes:
        with path.open('xb') as f:
            f.write(data)
    print(json.dumps({key: summary[key] for key in ('prompts', 'generated_tokens', 'cycles', 'mutable_bytes_verified_cycles',
                                                   'full_output_ids_exact', 'full_output_text_hashes_exact', 'pooled_conditional_depth')}, indent=2))


if __name__ == '__main__':
    main()
