#!/usr/bin/env python3
"""CPU-only draft recipe helper. Never launches an engine or changes the host."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(name):
    return json.loads((HERE / name).read_text())


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


def write(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def verify_packet():
    for row in read('packet-files.json')['files']:
        path = HERE / row['path']
        require(path.is_file() and not path.is_symlink(), 'missing packet file: ' + row['path'])
        require(path.stat().st_size == row['bytes'] and digest(path) == row['sha256'],
                'packet file changed: ' + row['path'])


def verify_source(root):
    rows = read('source-inputs.json')['files']
    for row in rows:
        path = root / row['path']
        require(path.is_file() and not path.is_symlink(), 'missing source: ' + row['path'])
        require(path.stat().st_size == row['bytes'] and digest(path) == row['sha256'],
                'source changed: ' + row['path'])
    return len(rows)


def export_source(repo, output):
    spec = read('source-inputs.json')
    commit = spec['source_commit']
    require(not output.exists(), 'source output must be new')
    subprocess.run(['git', '-C', str(repo), 'cat-file', '-e', commit + '^{commit}'], check=True)
    output.mkdir(parents=False)
    # Read immutable Git objects, never the active worktree or its index.
    for row in spec['files']:
        relative = Path(row['path'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'unsafe source path')
        data = subprocess.check_output(['git', '-C', str(repo), 'show', commit + ':' + row['path']])
        require(len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256'],
                'pinned source mismatch: ' + row['path'])
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
        path.chmod(0o755 if row['mode'] == '100755' else 0o644)
    return {'source_commit': commit, 'verified_files': verify_source(output),
            'output': str(output), 'device_execution': False}


def download_plan(root, components):
    rows = [r for r in read('model-downloads.json')['files'] if r['component'] in components]
    lines = ['#!/bin/sh', 'set -eu', '# Public pinned downloads; run explicitly after reviewing storage.']
    for row in rows:
        directory = root / row['component']
        path = directory / row['name']
        partial = path.with_name(path.name + '.partial')
        q = shlex.quote
        lines += [f'mkdir -p {q(str(directory))}',
                  f'test ! -e {q(str(path))}', f'test ! -e {q(str(partial))}',
                  f'curl --fail --location --proto =https --proto-redir =https --output {q(str(partial))} {q(row["url"])}',
                  f'printf \'%s\\n\' {q(row["sha256"] + "  " + str(partial))} | sha256sum --check --status',
                  f'mv {q(str(partial))} {q(str(path))}']
    return '\n'.join(lines) + '\n'


def materialize(args):
    config = read('configs/' + args.profile + '.json')
    workload = read('workloads.json')[args.workload]
    targets = args.target_bdf
    all_cards = targets + [args.provider_bdf]
    require(len(targets) == len(config['boundaries']) - 1, 'wrong target card count')
    require(len(set(all_cards)) == len(all_cards) and all(
        re.fullmatch(r'0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]', card) for card in all_cards),
        'distinct canonical physical PCI BDFs required')
    require(not args.output.exists(), 'configuration output must be new')
    adapter_path = args.adapter.resolve(strict=True)
    receipt_path = args.receipt.resolve(strict=True)
    adapter = json.loads(adapter_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    require(adapter.get('schema') == 'ownrt.gsq.rank-adapter-plan.v1', 'local adapter schema')
    require(receipt.get('schema') == 'ownrt.engine.build.v1', 'local receipt schema')
    argv = adapter['rank_argv'][0]
    require(argv.count('--draft-manifest') == 1, 'one local draft manifest required')
    manifest = Path(argv[argv.index('--draft-manifest') + 1]).resolve(strict=True)
    tokens = json.loads(gzip.decompress((HERE / workload['prompt']).read_bytes()))
    require(len(tokens) == workload['prompt_count'] and all(type(t) is int and 0 <= t < 248320 for t in tokens),
            'invalid prompt tokens')
    raw = struct.pack('<' + 'i' * len(tokens), *tokens)
    require(hashlib.sha256(raw).hexdigest() == workload['prompt_i32_sha256'], 'prompt identity')
    args.output.mkdir()
    prompt = args.output / 'prompt.i32'
    with prompt.open('xb') as stream:
        stream.write(raw)
    write(args.output / 'prompt.json', tokens)
    full = args.policy == 'qualification'
    config.update(adapter_plan=str(adapter_path), build_receipt=str(receipt_path),
                  bdfs=targets, provider_bdf=args.provider_bdf,
                  output=str(args.output / 'run'), prompt_tokens=tokens,
                  max_new=workload['max_new'], admitted_max_new=workload['max_new'],
                  dedicated_prefill_prompt=str(prompt),
                  dedicated_prefill_prompt_sha256=workload['prompt_i32_sha256'],
                  trusted_draft_manifest_sha256=digest(manifest),
                  check_policy=args.policy, verify_restore=full, verify_recursive_restore=full,
                  verify_provider_survival=full, measured_policy_admitted=not full)
    write(args.output / 'config.json', config)
    result = {'device_execution': False, 'runtime_admitted': False,
              'config': str(args.output / 'config.json'), 'policy': args.policy,
              'scope': 'Configuration materialization only; no adapter, build, model, environment, or hardware qualification.',
              'adapter_sha256': digest(adapter_path), 'build_receipt_sha256': digest(receipt_path)}
    write(args.output / 'materialization.json', result)
    return result


def check_output(path, workload):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    expected = read(read('workloads.json')[workload]['expected'])
    require([r.get('index') for r in rows] == list(range(len(rows))), 'output indices invalid')
    actual = [r['token'] for r in rows]
    require(all(type(t) is int for t in actual), 'noninteger output token')
    differences = [i for i, (a, b) in enumerate(zip(actual, expected)) if a != b]
    passed = len(actual) == len(expected) and not differences
    return {'passed': passed, 'actual_tokens': len(actual), 'expected_tokens': len(expected),
            'first_mismatch': differences[0] if differences else None,
            'scope': 'GPU baseline output comparison only; not independent CPU fidelity, complete state, or speed qualification.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    v = sub.add_parser('verify'); v.add_argument('--source-root', type=Path)
    s = sub.add_parser('export-source'); s.add_argument('--repo', type=Path, required=True); s.add_argument('--output', type=Path, required=True)
    d = sub.add_parser('download-plan'); d.add_argument('--root', type=Path, required=True); d.add_argument('--component', action='append', choices=['target', 'draft', 'tokenizer'])
    c = sub.add_parser('configure'); c.add_argument('--profile', choices=['2plus1', '3plus1'], required=True)
    c.add_argument('--workload', choices=['short', 'long'], default='short'); c.add_argument('--policy', choices=['qualification', 'measured'], default='qualification')
    c.add_argument('--adapter', type=Path, required=True); c.add_argument('--receipt', type=Path, required=True)
    c.add_argument('--target-bdf', action='append', required=True); c.add_argument('--provider-bdf', required=True); c.add_argument('--output', type=Path, required=True)
    o = sub.add_parser('check-output'); o.add_argument('--tokens', type=Path, required=True); o.add_argument('--workload', choices=['short', 'long'], required=True)
    args = p.parse_args()
    verify_packet()
    if args.command == 'verify':
        result = {'packet_verified': True, 'source_files_verified': verify_source(args.source_root.resolve()) if args.source_root else None, 'device_execution': False}
    elif args.command == 'export-source':
        result = export_source(args.repo.resolve(), args.output.absolute())
    elif args.command == 'download-plan':
        print(download_plan(args.root.absolute(), args.component or ['target', 'draft', 'tokenizer']), end=''); return
    elif args.command == 'configure':
        args.output = args.output.absolute(); result = materialize(args)
    else:
        result = check_output(args.tokens, args.workload)
    print(json.dumps(result, indent=2))
    if result.get('passed') is False:
        raise SystemExit(1)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
