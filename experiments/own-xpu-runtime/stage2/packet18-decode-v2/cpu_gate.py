#!/usr/bin/env python3
"""CPU-only real-model v2 gates, with every retained layer and token compared."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from window import AUTHORITY, compare_layers, oracle_gate, read, require, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ORACLE = ROOT / 'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gemv', choices=['frozen', 'r5'], required=True)
    parser.add_argument('--cards', type=int, choices=[1,2], default=None, help='CPU owners; default frozen streaming1, R5 resident2')
    parser.add_argument('--max-new', type=int, default=None)
    parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args()
    cards = a.cards if a.cards is not None else (1 if a.gemv == 'frozen' else 2)
    if cards==2:
        available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))*1024
        require(available>70*1024**3, 'resident CPU gate needs >70 GiB available RAM; use --cards 1 on smaller host')
    count = a.max_new if a.max_new is not None else (64 if a.gemv == 'frozen' else 8)
    require(count == 64 if a.gemv == 'frozen' else 8 <= count <= 64, 'frozen requires 64 tokens; r5 requires 8..64')
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and os.environ.get('OMP_NUM_THREADS') == '2', 'nice19 OMP_NUM_THREADS=2 required')
    require('idle' in subprocess.check_output(['ionice', '-p', str(os.getpid())], text=True, timeout=2), 'ionice idle required')
    binary, inp = HERE / 'build/host/own-rt-iq3', HERE / 'build/input'
    require(not a.output.exists() and (HERE / 'build').resolve() in a.output.resolve().parents, 'new output under packet18 build required')
    dynamic = subprocess.check_output(['readelf', '-d', str(binary)], text=True, timeout=5)
    require(not any(s in dynamic.lower() for s in ('libsycl', 'libze_loader', 'libur_loader', 'libopencl')), 'host binary depends on device runtime')
    input_meta = read(inp / 'input.json')
    hashes, expected = oracle_gate(ORACLE, input_meta['tokens'], 8, count)
    bindings = {str(path): sha(path) for path in (binary, inp / 'input.json', ORACLE / 'arithmetic.json', ORACLE / 'input.json', ORACLE / 'result.json')}
    bindings.update({str(inp / name): digest for name, digest in input_meta['files'].items()})
    bindings.update({str(ORACLE / name): digest for name, digest in hashes.items()})
    for path, digest in bindings.items():
        require(sha(Path(path)) == digest, 'bound input changed: ' + path)
    args = [str(binary), '--stage', 'decode', '--prompt-tokens', str(inp / 'tokens.txt'), '--plan', str(inp / 'plan.tsv'),
            '--identity', str(inp / 'identity.tsv'), '--model-dir', input_meta['model_dir'], '--output', str(a.output),
            '--cards', str(cards), '--card', '0', '--memory', 'resident' if cards==2 else 'layer-streaming',
            '--max-new', str(count), '--context', '256', '--nongemv', 'parallel', '--gemv', a.gemv,
            '--oracle', str(ORACLE), '--seconds', '10800']
    started = time.monotonic()
    with (HERE / f'cpu-{a.gemv}.log').open('w') as log:
        run = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, timeout=10900)
    native_path = a.output / 'receipt.json'
    receipt = read(native_path) if native_path.exists() else {}
    comparison = compare_layers(a.output, ORACLE, hashes)
    tokens = receipt.get('tokens', [])
    first_token = next((i + 1 for i in range(max(len(tokens), len(expected))) if i >= len(tokens) or i >= len(expected) or tokens[i] != expected[i]), None)
    binding_ok = all(Path(path).is_file() and sha(Path(path)) == digest for path, digest in bindings.items())
    passed = binding_ok and run.returncode == 0 and receipt.get('passed') is True and receipt.get('arithmetic') == AUTHORITY and tokens == expected and comparison['layer_matches'] == 384
    result = dict(comparison, passed=passed, arithmetic=AUTHORITY, bindings=bindings, bindings_unchanged=binding_ok,
                  device_executed=False, argv=args, binary_sha256=sha(binary), wall_seconds=time.monotonic()-started,
                  returncode=run.returncode, tokens=tokens, expected_tokens=expected,
                  token_matches=sum(x == y for x, y in zip(tokens, expected)), first_differing_token=first_token,
                  missing_fixtures=sum(row['sha256'] is None for row in comparison['layers']),
                  run_receipt={**receipt, 'teardown': [{k: v for k, v in row.items() if k != 'sequence'} for row in receipt.get('teardown', [])]})
    (HERE / f'cpu-real-{a.gemv}.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('layers', 'layer_hashes', 'run_receipt', 'argv', 'bindings')}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
