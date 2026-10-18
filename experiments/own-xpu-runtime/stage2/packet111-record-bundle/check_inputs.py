#!/usr/bin/env python3
"""CPU-only prerequisite closure for every chain window; never launch a binary.

Static files must exist now. Outputs of earlier windows are explicit producer
edges, not silently ignored missing files. --window requires those edges to
exist too, immediately before the coordinator launches that window.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import sys
from write_paths import inventory as write_inventory
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
WINDOWS = ('K0', 'K1a', 'K1b', 'K2', 'W0p', 'KD', 'W2m', 'WS', 'WSs', 'WS128x', 'WS128')


class Inventory:
    def __init__(self):
        self.files = {}
        self.errors = []
        self.generated = []

    def file(self, path, windows, expected=None, size=None, metadata_only=False):
        path = Path(path).absolute()
        key = str(path)
        row = self.files.setdefault(key, dict(path=key, resolved=str(path.resolve()), windows=[]))
        row['windows'] = sorted(set(row['windows']) | set(windows), key=WINDOWS.index)
        try:
            if not path.is_file():
                raise ValueError('missing file')
            stat = path.stat()
            row['bytes'] = stat.st_size
            if size is not None and stat.st_size != size:
                raise ValueError(f'wrong size: {stat.st_size}, expected {size}')
            if expected and row.get('sha256') != expected:
                with path.open('rb') as stream:
                    row['sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
                if row['sha256'] != expected:
                    raise ValueError('SHA256 differs')
            if metadata_only:
                row['payload_read'] = False
        except (OSError, ValueError) as error:
            self.errors.append(f'{key}: {error}')
        return path

    def read(self, path, windows):
        path = self.file(path, windows)
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError) as error:
            self.errors.append(f'{path}: {error}')
            return {}

    def produced(self, path, producer, consumer, require_now=False):
        if WINDOWS.index(producer) >= WINDOWS.index(consumer):
            self.errors.append('invalid producer order: ' + str(path))
        self.generated.append(dict(path=str(path), producer=producer, consumer=consumer))
        if require_now:
            self.file(path, [consumer])


def fixture_files(inv):
    windows = ('K1a', 'K1b', 'K2')
    manifest = inv.read(P / 'input-fixtures.json', windows)
    root = P / 'build/fusion-fixtures'
    for name, item in manifest.get('files', {}).items():
        inv.file(root / name, windows, item['sha256'], item['bytes'])
    try:
        names = (root / 'cases.txt').read_text().split()
        if len(names) != 72 or len(set(names)) != 72:
            raise ValueError('expected 72 distinct fixture names')
        if not set(names) <= set(manifest.get('files', {})):
            raise ValueError('unbound fixture name')
        for name in names:
            if Path(name).name != name:
                raise ValueError('unsafe fixture name')
            inv.file(root / name, windows)
    except (OSError, ValueError) as error:
        inv.errors.append(str(root) + ': ' + str(error))


def bundle(inv, directory, windows, hashes=None):
    inp = inv.read(directory / 'input.json', windows)
    for name, expected in (hashes or inp.get('files', {})).items():
        inv.file(directory / name, windows, expected)
    for name in ('tokens.txt', 'plan.tsv', 'identity.tsv', 'vocab.bin'):
        inv.file(directory / name, windows)
    # Only stat model files. No model payload read, mapping, or CPU inference.
    try:
        model = Path(inp['model_dir'])
        for line in (directory / 'identity.tsv').read_text().splitlines():
            fields = line.split()
            if fields:
                inv.file(model / fields[0], windows, size=int(fields[1]), metadata_only=True)
        for line in (directory / 'plan.tsv').read_text().splitlines():
            fields = line.split()
            if fields:
                path = inv.file(model / fields[0], windows, metadata_only=True)
                if path.is_file() and path.stat().st_size < int(fields[4]) + int(fields[5]):
                    inv.errors.append(str(path) + ': tensor extent exceeds file')
    except (OSError, ValueError, KeyError, IndexError) as error:
        inv.errors.append(str(directory) + ': invalid input bundle: ' + str(error))


def check(output_root=None, prefix_windows=None, window=None):
    from storage import B, REGISTERED_CHAIN
    import queue_runner as queue
    out = queue.admitted_output(output_root or B / REGISTERED_CHAIN)
    inv = Inventory()
    if (out / 'STOP').exists():
        inv.errors.append(str(out / 'STOP') + ': latched output cannot be reused')
    seal = inv.read(P / 'build-receipt.json', WINDOWS)
    if not seal.get('passed') or not seal.get('sources') or not seal.get('artifacts_sha256'):
        inv.errors.append('complete chain build receipt required')
    for name, expected in seal.get('sources', {}).items():
        inv.file(ROOT / name, WINDOWS, expected)
    for name, expected in seal.get('artifacts_sha256', {}).items():
        inv.file(P / 'build' / name, WINDOWS, expected)
    fixture_files(inv)
    for name in ('dispatch-p45.json', 'dispatch-speed6.json', 'dispatch-speed6-provenance.json',
                 'selection.json', 'memory-plan.json', 'mtp-manifest.tsv', 'p56_config.hpp'):
        inv.file(P / name, WINDOWS)
    # Native __FILE__ constants belong to each actual sealed engine's source.
    inv.read(P / 'chain-binding.json', WINDOWS)
    screen = P.parent / ('packet56w-spin' if P.name == 'packet56w-chain' else P.name)
    for engine in (screen, P.parent / 'packet56-draft-prefix'):
        inv.file(engine / 'rope.bf16', WINDOWS[5:])
        inv.file(engine / 'mtp-manifest.tsv', WINDOWS[5:])
    draft_model = Path('/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8')
    try:
        for line in (P / 'mtp-manifest.tsv').read_text().splitlines():
            fields = line.split()
            if fields:
                inv.file(draft_model / fields[1], WINDOWS[5:], size=int(fields[8]), metadata_only=True)
    except (OSError, ValueError, IndexError) as error:
        inv.errors.append('draft manifest: ' + str(error))
    bundle(inv, P / 'build/input', ('KD', 'W2m'))
    oracle = P / 'oracle/results'
    completion = inv.read(oracle / 'completion.json', WINDOWS[5:])
    for key, name in (('manifest_sha256', 'suite-manifest.json'),
                      ('determinism_sha256', 'determinism.json'),
                      ('old_v_new_sha256', 'old-v-new.json'), ('kd_capture_sha256', 'kd-capture.json')):
        inv.file(oracle / name, WINDOWS[5:], completion.get(key))
    for name in ('build-receipt.json', 'arithmetic.json', 'suite_check.py', 'oracle_job.py'):
        inv.file(P / 'oracle' / name, WINDOWS[5:])
    oracle_build = inv.read(P / 'oracle/build-receipt.json', WINDOWS[5:])
    for mapping in ('sources', 'frozen_sources'):
        for name, digest in oracle_build.get(mapping, {}).items():
            inv.file(ROOT / name, WINDOWS[5:], digest)
    oracle_external = oracle.resolve().parent
    inv.file(oracle_external / 'build/oracle', WINDOWS[5:], oracle_build.get('binary_sha256'))
    for name, digest in oracle_build.get('generated_sources', {}).items():
        inv.file(oracle_external / 'build/src' / name, WINDOWS[5:], digest)
    inv.file(P.parent / 'suite-inputs-20261012-cap128/suite-manifest.json', WINDOWS[5:],
             completion.get('old_manifest_sha256'))
    capture = inv.read(oracle / 'kd-capture.json', ('KD',))
    table = oracle / 'capture-incident-retrospective.tsv'
    inv.file(table, ('KD',), capture.get('table_sha256'))
    for name, expected in capture.get('streams', {}).items():
        inv.file(Path(name), ('KD',), expected, 20480)
    try:
        for line in table.read_text().splitlines():
            name = line.split(maxsplit=3)[3]
            if name not in capture.get('streams', {}):
                inv.errors.append('unbound KD capture stream: ' + name)
            inv.file(name, ('KD',), size=20480)
    except (OSError, IndexError) as error:
        inv.errors.append('KD table: ' + str(error))
    manifest = inv.read(oracle / 'suite-manifest.json', WINDOWS[6:])
    if not manifest.get('complete') or len(manifest.get('prompts', [])) != 12:
        inv.errors.append('complete 12-prompt suite manifest required')
    for entry in manifest.get('prompts', []):
        windows = WINDOWS[6:] if entry['prompt_id'] == 'incident-retrospective' else WINDOWS[7:]
        bundle(inv, ROOT / entry['input_bundle'], windows, entry['input_bundle_hashes'])
        directory = ROOT / entry['oracle_directory']
        receipt = inv.read(directory / 'receipt.json', windows)
        inv.file(directory / 'receipt.json', windows, entry['oracle_receipt_sha256'])
        for leaf, key in (('input.json', 'input_sha256'), ('result.json', 'result_sha256'),
                          ('validation.json', 'validation_sha256'), ('arithmetic.json', 'arithmetic_sha256')):
            inv.file(directory / leaf, windows, receipt.get(key))
        validation = inv.read(directory / 'validation.json', windows)
        result = inv.read(directory / 'result.json', windows)
        count = len(result.get('tokens', []))
        expected = {f'step{i}/layer-{j:02}.bf16' for i in range(1, count + 1)
                    if i <= 8 or 97 <= i <= 104 for j in range(48)}
        if not expected or set(validation.get('fixture_hashes', {})) != expected:
            inv.errors.append(str(directory) + ': incomplete oracle fixture inventory')
        for name, digest in validation.get('fixture_hashes', {}).items():
            inv.file(directory / name, windows, digest, 20480)
        for i in range(1, count + 1):
            if i <= 8 or 97 <= i <= 104:
                inv.file(directory / f'step{i}/layers.jsonl', windows)
    parent = P.parent / 'packet56-draft-prefix'
    prefixes = prefix_windows or [parent / 'evidence/head-k-a/window.json', parent / 'evidence/head-k-b/window.json']
    for path in prefixes:
        receipt = inv.read(path, WINDOWS)
        for name, digest in {**receipt.get('native_files', {}), **receipt.get('kernel_files', {}),
                             'summary.json': receipt.get('summary_sha256')}.items():
            inv.file(path.parent / name, WINDOWS, digest)
    # Existing prefix verifier also checks current boot and distinct fresh owners.
    if not inv.errors:
        try:
            queue.prefix_prerequisites(prefixes)
            # Run the real read-only completion validator as well as enumerating
            # its paths. It verifies token/fixture semantics and all authority pins.
            from shared_oracle import completed_binding
            with contextlib.redirect_stdout(io.StringIO()):
                completed_binding()
        except (OSError, ValueError, KeyError, RuntimeError) as error:
            inv.errors.append('prefix/oracle admission: ' + str(error))
    for consumer, command in queue.commands(out).items():
        for flag in ('--k0', '--k1a', '--k1b', '--k2', '--w0p', '--kd', '--exactness-window', '--dispatch'):
            if flag not in command:
                continue
            path = Path(command[command.index(flag) + 1])
            if path.is_relative_to(out):
                producer = path.relative_to(out).parts[0]
                inv.produced(path, producer, consumer, window == consumer)
                if path.name == 'window.json':
                    inv.produced(out / (producer + '-lane-admission.json'), producer, consumer, window == consumer)
                if window == consumer and path.name == 'window.json' and path.is_file():
                    receipt = inv.read(path, [consumer])
                    admission = receipt.get('lane_admission', {})
                    if not admission.get('path') or not admission.get('sha256'):
                        inv.errors.append(str(path) + ': missing admission-sidecar binding')
                    else:
                        inv.file(Path(admission['path']), [consumer], admission['sha256'])
                    for leaf, digest in receipt.get('receipts', {}).items():
                        raw = path.parent / leaf
                        if raw.is_file():
                            inv.file(raw, [consumer], digest)
                            continue
                        retained = receipt.get('retained_artifacts', {}).get(leaf, {})
                        if retained.get('disposition') == 'sha256-only':
                            for field, hash_field in (('native_receipt_path', 'native_receipt_sha256'),
                                                      ('children_path', 'children_sha256')):
                                inv.file(path.parent / retained[field], [consumer], retained[hash_field])
                            dispatch = retained.get('restoration_dispatch', {})
                            if dispatch:
                                inv.file(dispatch['path'], [consumer], dispatch['sha256'])
                        elif retained.get('path'):
                            inv.file(path.parent / retained['path'], [consumer], retained['sha256'])
                        else:
                            inv.file(raw, [consumer], digest)
    write_paths, write_errors = write_inventory(P, B, out, WINDOWS, [e['prompt_id'] for e in manifest.get('prompts', [])])
    inv.errors.extend(write_errors)
    rows = {name: dict(write_paths=sum(r['window'] == name for r in write_paths), static_files=sum(name in r['windows'] for r in inv.files.values()),
                       generated_prerequisites=sum(r['consumer'] == name for r in inv.generated)) for name in WINDOWS}
    return dict(schema='own-runtime.chain-input-check.v1', passed=not inv.errors,
                device_executed=False, model_payload_read=False, output_root=str(out),
                write_paths=write_paths, write_path_count=len(write_paths), windows=rows, static_files=len(inv.files), generated_prerequisites=inv.generated,
                errors=sorted(set(inv.errors)), files=list(inv.files.values()),
                scope='Static closure now; generated prerequisites required immediately before each window. Device correctness remains pending.')


def summary(row):
    return {key: row[key] for key in ('passed', 'device_executed', 'model_payload_read', 'output_root', 'windows', 'static_files', 'write_path_count', 'errors')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', choices=('packet111-record-bundle', 'packet61-spin-hcfusion', 'packet56w-chain'),
                        help='Read-only audit using that packet’s own queue and path rules')
    parser.add_argument('--resume-from', type=Path)
    parser.add_argument('--output-root', type=Path)
    parser.add_argument('--prefix-windows', type=Path, nargs=2)
    parser.add_argument('--window', choices=WINDOWS)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or not set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)):
        raise ValueError('nice19 and helper cores required')
    global P
    if args.packet and args.packet != P.name:
        P = P.parent / args.packet
        sys.path.insert(0, str(P))
    row = check(args.output_root, args.prefix_windows, args.window)
    if args.resume_from:
        from resume_chain import validate
        try:
            validate(args.resume_from, Path(row['output_root']), prepared=(Path(row['output_root'])/'resume-manifest.json').exists())
        except (OSError, ValueError, KeyError, RuntimeError) as error:
            row['errors'].append(str(error)); row['passed'] = False
    if args.report:
        args.report.write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(summary(row)))
    return 0 if row['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
