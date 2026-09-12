#!/usr/bin/env python3
"""Preregistered fresh-process native reference campaign; no serving daemon."""
import argparse
import json
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--smoke-token-limit', type=int, default=256)
parser.add_argument('--publisher-sampling', action='store_true')
parser.add_argument('--system-prompt')
parser.add_argument('--quality-pilot', action='store_true')
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=False)
stages = ['smoke'] + (['pilot-quality'] if args.quality_pilot else []) + ['baseline-a', 'baseline-b']
for name in stages:
    output = args.out / (name + '.json')
    command = [sys.executable, str(ROOT / 'run-baseline.py'), '--out', str(output)]
    if args.publisher_sampling:
        command += ['--publisher-sampling']
    if args.system_prompt:
        command += ['--system-prompt', args.system_prompt]
    if name == 'pilot-quality':
        command += ['--quality-only']
    if name == 'smoke':
        command += ['--smoke-only', '--smoke-token-limit', str(args.smoke_token_limit)]
    print('BEGIN ' + name, flush=True)
    subprocess.run(command, check=True, timeout=7200)
    result = json.loads(output.read_text())
    assert result['status'] == 'complete'
    if name == 'smoke':
        assert result['rows'][0]['final_text'].strip() == '4', result['rows'][0]['decoded_text']
    if name == 'pilot-quality':
        spec = importlib.util.spec_from_file_location('baseline_analysis', ROOT / 'analyze-baseline.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        checks = module.quality(module.primary(result['rows']),
                                json.loads((ROOT / 'quality-canaries-v1.json').read_text())['prompts'])
        (args.out / 'pilot-checks.json').write_text(json.dumps(checks, indent=2) + '\n')
        assert all(c['passed'] for c in checks), checks
    print('PASS ' + name, flush=True)
