#!/usr/bin/env python3
"""Write data/decode-replica-probe-fixtures.json for packet 91's cross-card probe.

For each of the ten stability-01 fixtures, pick the first f90c-endure prompt
that emitted it with an exact parity verdict, and pin:
- source: that prompt's captured tensors (R/output/validation/<prompt>/tensors.safetensors),
- source_sha256: the file's sha256,
- expected: the fixture REFERENCE's tensor sha256s (summary.json), which the
  probe uses both to certify its input latents and to judge both cards' output.

Reads only (about 190 MB); run it when no server is running. CPU only.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
LANE = Path(__file__).resolve().parents[1]
THROUGHPUT = LANE / 'data/busy-90c/f90c-endure-throughput.json'
OUT = LANE / 'data/decode-replica-probe-fixtures.json'


def sha_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    summary = json.loads(THROUGHPUT.read_text())
    assert summary['all_exact'] is True, 'source run is not all-exact'
    chosen = {}
    for row in summary['rows']:
        if row['fill'] or not row['exact'] or row['emitted_fixture'] in chosen:
            continue
        chosen[row['emitted_fixture']] = row
    assert len(chosen) == 10, sorted(chosen)
    fixtures = []
    for fixture in sorted(chosen):
        row = chosen[fixture]
        source = ROOT / 'output/validation' / row['prompt'] / 'tensors.safetensors'
        ref = json.loads((ROOT / 'output/validation' / row['reference'] / 'summary.json').read_text())
        captured = json.loads((source.parent / 'summary.json').read_text())
        expected = {k: ref['tensors'][k]['sha256'] for k in ('images', 'video_latent', 'audio_latent', 'waveform')}
        assert all(captured['tensors'][k]['sha256'] == v for k, v in expected.items()), (fixture, row['prompt'])
        fixtures.append({'fixture': fixture, 'reference': row['reference'], 'prompt': row['prompt'],
                         'source': str(source), 'source_sha256': sha_file(source), 'expected': expected})
    OUT.write_text(json.dumps({'schema': 'ltx.decode-replica-probe-fixtures.v1',
                               'source_run': 'f90c-endure (data/busy-90c, 117/117 exact)',
                               'fixtures': fixtures}, indent=2) + '\n')
    print(f'wrote {OUT} ({len(fixtures)} fixtures)')


if __name__ == '__main__':
    main()
