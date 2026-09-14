#!/usr/bin/env python3
"""Publish only replay-verified prefill baselines from the bounded follow-up."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DATA = 'experiments/qwen38-27b-b70/data/2026-09-14-prefill-followup'
SOURCE = DATA + '/summary.json'
REPORT = 'experiments/qwen38-27b-b70/notes/2026-09-14-prefill-followup-results.md'
PACKAGES = {
    '4b-tp2': ('qwen35-4b-w4a16-b70', 'qwen35-4b-w4a16-b70', 2, 3, 'W4A16'),
    '9b-tp2': ('qwen35-9b-w4a16-b70', 'qwen35-9b-w4a16-b70', 2, 3, 'W4A16'),
    '27b-int4-tp1': ('qwen38-27b-int4-fixed-k-tp2-b70', 'qwen38-27b-autoround-int4-b70', 1, 4, 'INT4'),
}


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
        for field, expected in [('tensor_parallel_size', cards), ('speculative_tokens', depth), ('quantization', quant)]:
            if identity[field] != expected:
                raise ValueError(f'{key}: {field} identity differs')
        points = [{'context_tokens': point['prompt_tokens'],
                   'value': point['mean_controls']['server_prefill_tokens_per_s'],
                   'samples': point['samples']} for point in measured['points']]
        if [p['context_tokens'] for p in points] != [256, 512] or any(p['samples'] != 18 for p in points):
            raise ValueError('unexpected measured lengths or samples')
        card_label = f'{cards} GPU' + ('s' if cards != 1 else '')
        result[key] = {
            'id': 'short-prompt-server-prefill-followup-' + key,
            'label': f'Reading speed with a short prompt · {card_label}',
            'public_label': f'Reading speed · {card_label} · {depth}-token draft',
            'metric': 'prefill', 'unit': 'tok/s', 'x_metric': 'context_tokens',
            'x_label': 'Input length (tokens)', 'measurement_kind': 'server_prefill',
            'scope': f'One user, {card_label}, 256–512 input tokens; no saved prompt cache. Separate short-input test on the published R304 runtime.',
            'public_scope': 'How fast the server reads a short prompt before making its first token. One user; no saved prompt cache. Unrepeated prose, code and documents.',
            'evidence': REPORT, 'source_data': SOURCE,
            'operating_profile': {
                'tensor_parallel_size': cards, 'speculative_tokens': depth,
                'quantization': quant, 'parent_runtime': 'R304',
                'image_id': 'sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2',
                'activations': 'FP16', 'kv_cache': 'native', 'concurrency': 1,
                'max_model_len': 1024, 'max_num_batched_tokens': 1024,
                'max_num_seqs': 1, 'prefix_caching': False, 'classpad': 0,
                'rowchunk': 32, 'draft_shortlist_rows': 67248,
                'profiler_configured': key == '4b-tp2', 'profiler_active_during_measurement': False,
            },
            'technical_method': 'Measured 2026-09-14 UTC on ASRock B70. Input tokens divided by vLLM server prefill duration from first scheduled execution to first token, obtained from one-request histogram deltas; not isolated GPU throughput or HTTP TTFT. Each point averages two control-arm rates. Each arm takes the median of three repeats per prose/code/documentation class, then the median across classes (18 measured requests per length). Unrepeated source excerpts truncated to exact numeric input IDs, 128 output tokens with ignore_eos, zero cached tokens; warmups and the optional profiler request excluded. Complete outputs repeat exactly. All 12 natural-completion strict-suite outputs matched the qualified reference. One loaded server per setup; no runtime optimization or new decode record promoted. Earlier short-prefill tests used a different prompt corpus and do not provide a matched scaling comparison.',
            'promotion_qualified': False, 'points': points,
        }
    return result


def row_matches(key, row):
    heading = row.split('</th>', 1)[0]
    if key == '27b-int4-tp1':
        return all(text in heading for text in ('1&times; B70', 'AutoRound INT4', 'MTP depth 4'))
    model = 'Qwen3.5-4B' if key == '4b-tp2' else 'Qwen3.5-9B'
    return all(text in heading for text in (model, '2&times; B70', 'INT4 W4A16', 'MTP depth 3'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    measured = profiles()
    manifest = json.loads((ROOT / DATA / 'evidence/manifest.json').read_text())
    dependencies = [REPORT, SOURCE, DATA + '/evidence/manifest.json']
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
    path = ROOT / 'index.html'
    html = path.read_text()
    for key, profile in measured.items():
        matches = [m for m in re.finditer(r'<tr\b[^>]*>.*?</tr>', html, re.S) if row_matches(key, m.group())]
        if len(matches) != 1:
            raise ValueError(f'expected one matching homepage row: {key}')
        row = matches[0].group()
        value = next(p['value'] for p in profile['points'] if p['context_tokens'] == 512)
        cell = (f'<td class="num r model-prefill" data-label="Prefill" data-prefill-profile="{key}" '
                'title="Reading speed at 512 input tokens, one user. Separate short-prompt test with unrepeated text; open for setup and timing details.">'
                f'<a href="models/{PACKAGES[key][1]}.html#prefill">{value:,.0f}</a>&dagger;</td>')
        updated, count = re.subn(r'<td\b[^>]*class="[^"]*model-prefill[^\"]*"[^>]*>.*?</td>', lambda _: cell, row, flags=re.S)
        if count != 1:
            raise ValueError(f'expected one prefill cell: {key}')
        if updated != row:
            if args.check:
                errors.append('index.html: ' + key)
            else:
                html = html[:matches[0].start()] + updated + html[matches[0].end():]
    if not args.check and html != path.read_text():
        path.write_text(html)
    if errors:
        raise SystemExit('\n'.join(errors))
    print('Verified three follow-up prefill profiles.' if args.check else 'Updated three follow-up prefill profiles.')


if __name__ == '__main__':
    main()
