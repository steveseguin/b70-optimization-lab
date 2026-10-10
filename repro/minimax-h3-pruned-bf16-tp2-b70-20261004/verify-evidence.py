#!/usr/bin/env python3
"""CPU-only integrity audit; never loads models or imports a GPU runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def verify():
    bindings = json.loads((HERE / 'evidence-manifest.json').read_text())
    for item in bindings['files']:
        assert hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() == item['sha256'], item['path']
    runtime = json.loads((HERE / 'runtime-manifest.json').read_text())
    for item in runtime['files']:
        data = subprocess.check_output(['git', '-C', str(ROOT), 'show', runtime['source_commit'] + ':' + item['path']])
        assert hashlib.sha256(data).hexdigest() == item['sha256'], item['path']
    observed = json.loads((HERE / 'featured-observation.json').read_text())
    log = (ROOT / observed['evidence']).read_text()
    assert 'wall=3173 s' in log and 'MATCH lines: 32' in log and 'DIFFERS lines: 0' in log
    assert '8 REPEAT GATE: bytewise-equal' in log
    assert observed['wall_seconds'] / observed['clips'] == observed['seconds_per_clip'] == 396.625
    lane = ROOT / 'experiments/minimax-h3-b70'
    prompts = [x.strip() for x in (lane / 'notes/h3-soak8-prompts.txt').read_text().splitlines() if x.strip() and not x.startswith('#')]
    assert len(prompts) == 8
    for i, prompt in enumerate(prompts):
        r = json.loads((lane / f'data/2026-10-04-soak8/clip-{i:02d}-receipt.json').read_text())
        assert r['run_name'] == observed['run_name'] and r['prompt'] == prompt
        assert r['seed'] == 42 and r['num_function_evaluations'] == 50
        assert r['batch']['index'] == i and r['batch']['count'] == 8
        for key, value in dict(steps=51, height=544, width=960, frames=124, lora=None,
                               denoiser='pruned', vae_autocast='off', vae_decode='two-proc', split_index=25).items():
            assert r['settings'][key] == value, (i, key)
        for key in ('video_tensor_sha256', 'audio_tensor_sha256', 'video_latents_sha256', 'audio_latents_sha256'):
            assert len(r['hashes'][key]) == 64, (i, key)
    print('PASS: retained eight-clip receipts, arithmetic, evidence hashes and historical source pins.')
    print('Historical reference equality is reported by the session log; missing original receipts are not recreated.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--require-runnable', action='store_true')
    args = ap.parse_args()
    verify()
    if args.require_runnable:
        raise SystemExit('INCOMPLETE: exact AdaLN fit producer, historical weight binding and clean runtime rebuild remain unavailable. No launch authorized by this audit.')
