#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Freeze existing split24 conditioning evidence; stdlib/file reads only."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANE = HERE.parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PARENT_SHA = '67ec59a5b0c5131d0b129e4c0b9187386c29c0395ac225dc28422516684991ad'
seen = {}


def read(path):
    raw = path.read_bytes()
    seen[str(path)] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def main():
    parent = ROOT / 'prepared-continuation-stream-132'
    read(parent / 'manifest.json')
    assert seen[str(parent / 'manifest.json')] == PARENT_SHA
    run129 = ('encoder-server-continuation-stream-129-frame-dg0-adcone-bo1-pa1-smfp-'
              'two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-gc60-ssbackground-sdc1-mi.completed-')
    runs = [ROOT / (run129 + stamp) for stamp in ('20261010T114323Z', '20261010T124818Z')]
    current = ROOT / ('encoder-server-continuation-stream-132-frame-dg1-adcone-bo1-pa1-smfp-'
                      'two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-dseager-display-ra0-ssfull-'
                      'ddxpu2-gc60-ssbackground-sdc1-mi-cmreplica-release-audioxpu2')
    prompts = {}
    fresh_count = 0
    for run in [*runs, current]:
        for path in sorted((run / 'receipts').glob('receipt-*.json')):
            # Stopped historical runs; never inspect a live client directory.
            suffix = path.stem.rsplit('-c', 1)[-1]
            if suffix.isdigit() and int(suffix) > 200:
                continue
            row = read(path)
            text = row.get('text', {})
            if text.get('reused') is not False:
                continue
            key, tensors = text['prompt_sha256'], text['tensors']
            assert len(key) == 64 and tensors
            assert all(len(t['sha256']) == 64 and t['shape'] and t['dtype'] for t in tensors)
            value = prompts.setdefault(key, {'tensors': tensors, 'witnesses': []})
            assert value['tensors'] == tensors, ('Historical conditioning mismatch', path)
            value['witnesses'].append({'path': str(path), 'sha256': seen[str(path)]})
            fresh_count += 1
    scenes_path = LANE / 'data/stream/kittens-01.json'
    scenes = read(scenes_path)
    scenes = scenes.get('scenes', scenes.get('fixtures')) if isinstance(scenes, dict) else scenes
    scene_hashes = [hashlib.sha256(s['prompt'].encode()).hexdigest() for s in scenes]
    assert len(scene_hashes) == 10 and set(scene_hashes) <= prompts.keys()
    probe_path = current / 'text-window-probe-stream132-window-probe.json'
    probe = read(probe_path)
    assert probe['passed'] is True and len(probe['rows']) == 40
    keys = ('prompt', 'real_tokens', 'window', 'full_sha256', 'window_sha256')
    window = {k: probe[k] for k in ('admitted', 'prompt_tokens', 'prompts_file_sha256')}
    window['rows'] = [{k: r[k] for k in keys} for r in probe['rows']]
    assert all(len(set(r['full_sha256'])) == len(set(r['window_sha256'])) == 1 for r in window['rows'])
    out = dict(schema='ltx.stream133.text-oracle.v1', parent_manifest_sha256=PARENT_SHA,
               source_split=24, candidate_split=36, prompts=prompts, window_probe=window,
               scene_prompt_sha256=scene_hashes, fresh_receipt_count=fresh_count,
               evidence_files=seen,
               scope='Saved split24 outputs only; candidate must compare fresh conditioning before sampling. '
                     'Unknown prompts refuse in split36 mode. No candidate output or GPU result is asserted.')
    target = HERE / 'continuation133-text-oracle.json'
    target.write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'file': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                      'prompts': len(prompts), 'window_rows': len(window['rows']),
                      'fresh_receipts': fresh_count, 'evidence_files': len(seen)}))


if __name__ == '__main__':
    main()
