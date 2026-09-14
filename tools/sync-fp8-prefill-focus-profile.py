#!/usr/bin/env python3
"""Publish only replay-verified prefill baselines from the final FP8 focus."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DATA = 'experiments/qwen38-27b-b70/data/2026-09-14-fp8-prefill-focus'
SOURCE = DATA + '/summary.json'
REPORT = 'experiments/qwen38-27b-b70/notes/2026-09-14-fp8-prefill-focus-results.md'
PACKAGES = {'27b-fp8': ('qwen38-27b-fp8-tp2-b70', 'qwen38-27b-fp8-vllm-tp2-asrock-b70', 2, 1, 'FP8')}


def profiles():
    data = json.loads((ROOT / SOURCE).read_text())
    if data.get('complete') is not True:
        raise ValueError('Follow-up measurements incomplete')
    result = {}
    for key, (_, _, cards, depth, quant) in PACKAGES.items():
        measured = data['profiles'][key]
        if not measured.get('complete') or not measured.get('quality_exact'):
            raise ValueError(f'{key}: incomplete or failed output gate')
        identity = measured['identity']
        if identity.get('parent_image') != 'sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2':
            raise ValueError(f'{key}: parent runtime identity differs')
        for field, expected in [('tensor_parallel_size', cards), ('speculative_tokens', depth), ('quantization', quant), ('max_model_len', 4096), ('max_num_batched_tokens', 4096)]:
            if identity[field] != expected:
                raise ValueError(f'{key}: {field} identity differs')
        points = [{'context_tokens': point['prompt_tokens'],
                   'value': point['mean_controls']['server_prefill_tokens_per_s'],
                   'samples': point['samples']} for point in measured['points']]
        if [p['context_tokens'] for p in points] != [512, 2048] or any(p['samples'] != 18 for p in points):
            raise ValueError('unexpected measured lengths or samples')
        card_label = f'{cards} GPU' + ('s' if cards != 1 else '')
        result[key] = {
            'id': 'server-prefill-fp8-focus-' + key,
            'label': f'Reading speed at 512 and 2,048 input tokens · {card_label}',
            'public_label': f'Reading speed · {card_label} · {depth}-token draft · 4K capacity',
            'metric': 'prefill', 'unit': 'tok/s', 'x_metric': 'context_tokens',
            'x_label': 'Input length (tokens)', 'measurement_kind': 'server_prefill',
            'scope': f'One user, {card_label}, 512–2,048 input tokens; 4096-token capacity and batch budget; no saved prompt cache. Separate test on the published R304 runtime.',
            'public_scope': 'How fast the server reads your prompt before making its first token. One user, room for 4,096 tokens, no saved prompt cache. Unrepeated prose, code and documents.',
            'evidence': REPORT, 'source_data': SOURCE,
            'operating_profile': {
                'tensor_parallel_size': cards, 'speculative_tokens': depth,
                'quantization': quant, 'parent_runtime': 'R304',
                'image_id': 'sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2',
                'activations': 'FP16', 'kv_cache': 'native', 'concurrency': 1,
                'max_model_len': 4096, 'max_num_batched_tokens': 4096,
                'max_num_seqs': 1, 'prefix_caching': False, 'classpad': 0,
                'rowchunk': 32, 'draft_shortlist_rows': None,
                'profiler_configured': True, 'profiler_active_during_measurement': False,
            },
            'technical_method': 'Measured 2026-09-14 UTC on ASRock B70. Input tokens divided by vLLM server prefill duration from first scheduled execution to first token, obtained from one-request histogram deltas; not isolated GPU throughput or HTTP TTFT. Each point averages two control-arm rates. Each arm takes the median of three repeats per prose/code/documentation class, then the median across classes (18 measured requests per length). Unrepeated source excerpts truncated to exact numeric input IDs, 128 output tokens with ignore_eos, zero cached tokens; warmups and the optional profiler request excluded. Complete outputs repeat exactly. All 12 natural-completion strict-suite outputs matched the qualified reference. One loaded server per setup; no runtime optimization or new decode record promoted. The earlier short-prefill test used another corpus and a 1024-token capacity/batch budget; it is preserved separately and does not establish a speedup. At 2048 scheduled rows, W8A16 uses its natural oneDNN catalog beyond the fixed-K hook’s 512-row range.',
            'promotion_qualified': False, 'points': points,
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    measured = profiles()
    manifest = json.loads((ROOT / DATA / 'evidence/manifest.json').read_text())
    dependencies = [REPORT, SOURCE, DATA + '/verification.json', DATA + '/evidence/manifest.json']
    dependencies += [DATA + '/evidence/' + a['archive'] for a in manifest['archives']]
    dependencies += [s['repository_path'] for s in manifest['source_files']]
    errors = []
    for key, profile in measured.items():
        path = ROOT / 'packages' / PACKAGES[key][0] / 'package.json'
        package = json.loads(path.read_text())
        rows = package.setdefault('performance_profiles', [])
        existing = next((p for p in rows if p['id'] == profile['id']), None)
        missing = [p for p in dependencies if p not in package['dependencies']]
        if existing != profile or missing:
            if args.check:
                errors.append(str(path.relative_to(ROOT)))
            else:
                rows[:] = [p for p in rows if p['id'] != profile['id']]
                rows.append(profile)
                package['dependencies'].extend(missing)
                path.write_text(json.dumps(package, indent=2, ensure_ascii=False) + '\n')
    if errors:
        raise SystemExit('\n'.join(errors))
    print('Verified FP8 focus prefill profile.' if args.check else 'Updated FP8 focus prefill profile.')


if __name__ == '__main__':
    main()
