#!/usr/bin/env python3
"""Preregistered fresh-process native reference campaign; no serving daemon."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=False)
for name in ['smoke', 'baseline-a', 'baseline-b']:
    output = args.out / (name + '.json')
    command = [sys.executable, str(ROOT / 'run-baseline.py'), '--out', str(output)]
    if name == 'smoke':
        command += ['--smoke-only']
    print('BEGIN ' + name, flush=True)
    subprocess.run(command, check=True, timeout=7200)
    result = json.loads(output.read_text())
    assert result['status'] == 'complete'
    if name == 'smoke':
        assert result['rows'][0]['final_text'].strip() == '4', result['rows'][0]['decoded_text']
    print('PASS ' + name, flush=True)
