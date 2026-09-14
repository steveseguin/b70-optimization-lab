#!/usr/bin/env python3
"""Bounded offline serializer attribution using frozen all48 call reports.

No model/runtime imports, endpoint calls, subprocesses or host setting changes.
Both writers create files exclusively and synchronously close them in timing.
This does not measure video generation or qualify an application speed change.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import statistics
import sys
import time

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
SERVER = ROOT / 'encoder-server-compiler-06'
RUN = 'multiblock-screen-01-r25-all48-compiled-boat'
SOURCE = SERVER / ('compiler-' + RUN)
PACKET_SHA = '3676b1e47b514f5c28597063b42c9806ed13639cc2dde0f3b25fd44564c08394'
VALIDATOR_SHA = '900f7bdc41bf7f7d5ccd85c66619257a34a52c1f3e812e4eb867a5665a1099e9'
MODEL_SHA = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
CALL_COUNT = 48 * 11


def require(value, message):
    if not value:
        raise RuntimeError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe(path):
    path = Path(path).absolute()
    require('..' not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)),
            'Symlink or parent traversal in benchmark path')
    return path


def original_writer(path, value):
    # Exact packet06/07 node write_json body.
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def compact_writer(path, value):
    # Keep sorted keys, exclusive reservation, synchronous writes and close.
    # Removing indent permits CPython's one-shot C encoder; no record is omitted.
    with path.open('x') as stream:
        stream.write(json.dumps(value, separators=(',', ':'), sort_keys=True))
        stream.write('\n')


def source_records():
    helper = safe(LANE / 'scripts/ltx_multiblock_receipts.py')
    require(digest(helper.read_bytes()) == VALIDATOR_SHA, 'Frozen receipt validator changed')
    spec = importlib.util.spec_from_file_location('serializer_frozen_receipts', helper)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    identity_bytes = safe(SERVER / 'server-identity.json').read_bytes()
    identity = json.loads(identity_bytes)
    require(identity['source_packet_manifest_sha256'] == PACKET_SHA,
            'Frozen request belongs to another packet')
    sizes = []
    for index in range(48):
        for number in range(1, 12):
            path = safe(SOURCE / f'block-{index:02d}' / f'call-{number:02d}.json')
            require(path.is_file(), 'Missing frozen report')
            sizes.append(path.stat().st_size)
    require(max(sizes) <= MAX_FILE_BYTES and sum(sizes) <= MAX_TOTAL_BYTES,
            'Frozen report bounds exceeded before validator load')
    validated = validator.validate_compiler_receipts(SERVER, RUN, 'compiled', 'all48',
                                                    digest(identity_bytes), 2)
    records, inventory, total = [], [], 0
    for index in range(48):
        for number in range(1, 12):
            relative = Path(f'block-{index:02d}') / f'call-{number:02d}.json'
            path = safe(SOURCE / relative)
            require(path.is_file() and path.stat().st_size <= MAX_FILE_BYTES,
                    'Oversized or missing frozen report')
            raw = path.read_bytes()
            total += len(raw)
            require(len(raw) <= MAX_FILE_BYTES and total <= MAX_TOTAL_BYTES, 'Input bound exceeded')
            value = json.loads(raw, object_pairs_hook=validator._pairs)
            require(value == validated['blocks'][str(index)]['calls'][number - 1],
                    'Frozen report changed during validation')
            records.append((relative, value))
            inventory.append({'path': str(relative), 'bytes': len(raw), 'sha256': digest(raw)})
    require(len(records) == CALL_COUNT, 'Expected exactly528 frozen block reports')
    return records, inventory, identity_bytes


def verify_written(directory, records):
    inventory = []
    for relative, expected in records:
        path = safe(directory / relative)
        raw = path.read_bytes()
        require(json.loads(raw) == expected, 'Serialized record changed meaning')
        require(raw.endswith(b'\n'), 'Missing record terminator')
        inventory.append({'path': str(relative), 'bytes': len(raw), 'sha256': digest(raw)})
    require(len(list(directory.glob('block-*/call-*.json'))) == CALL_COUNT,
            'Serialized output count changed')
    return inventory


def context_io_round(expected_model, expected_identity):
    # Attribution of only encoder_diagnostics._context lines45..51: read two
    # files, parse both, require the model verdict, hash both. Directory/FAULT
    # guards, syscall latency elsewhere and runtime ownership checks are omitted.
    started = time.perf_counter_ns()
    for _ in range(CALL_COUNT):
        model_bytes = (ROOT / 'model-verification.json').read_bytes()
        require(json.loads(model_bytes).get('status') == 'passed', 'Frozen model verdict changed')
        identity_bytes = (SERVER / 'server-identity.json').read_bytes()
        json.loads(identity_bytes)
        model_hash = digest(model_bytes)
        identity_hash = digest(identity_bytes)
    elapsed = time.perf_counter_ns() - started
    # Full equality checked after timing; no file mutation is an admitted arm.
    require(model_bytes == expected_model and identity_bytes == expected_identity and
            model_hash == digest(expected_model) and identity_hash == digest(expected_identity),
            'Context source changed')
    return elapsed


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='New child directory of the benchmark evidence root; never reused')
    parser.add_argument('--pairs', type=int, choices=(1, 2, 3), default=3)
    return parser.parse_args(argv)


def run(args):
    output = safe(args.output_dir)
    require(output.parent == ROOT and output.name.startswith('serializer-replay-') and
            not output.exists(), 'Use a fresh serializer-replay-* directory under the evidence root')
    require(not (ROOT / 'FAULT.json').exists(), 'Recorded host fault; do not start attribution')
    require(shutil.disk_usage(ROOT).free >= 64 * 1024**2, 'Insufficient bounded output space')
    records, inventory, identity_bytes = source_records()
    model_bytes = safe(ROOT / 'model-verification.json').read_bytes()
    require(digest(model_bytes) == MODEL_SHA, 'Frozen model-verification identity changed')
    output.mkdir(exist_ok=False)
    original_writer(output / 'source-inventory.json', inventory)
    original_writer(output / 'preregistration.json', {
        'schema': 'ltx.serializer-replay.v1', 'source': str(SOURCE), 'calls': CALL_COUNT,
        'source_total_bytes': sum(row['bytes'] for row in inventory), 'pairs': args.pairs,
        'writer_order': [['original', 'compact'] if n % 2 == 0 else ['compact', 'original']
                         for n in range(args.pairs)],
        'script_sha256': digest(Path(__file__).read_bytes()), 'validator_sha256': VALIDATOR_SHA,
        'packet_manifest_sha256': PACKET_SHA, 'identity_sha256': digest(identity_bytes),
        'model_verification_sha256': digest(model_bytes),
        'timing': 'Each of528 file opens, JSON serializations, synchronous writes and closes; directory preparation/input parsing/verification excluded for both arms',
        'context_scope': 'Separate repeated unchanged file-read, JSON-parse and hash subset; no proposal to remove fault or identity guards',
        'storage_semantics': 'Exclusive text-file create; buffered writes plus synchronous close, identical to original node; no added fsync',
        'scope': 'CPU/filesystem attribution only; no native model or video speed claim',
        'failure_action': 'Stop remaining rounds and preserve new output plus source evidence',
        'outputs_retained': True})
    rows, context_rows = [], []
    phase = 'writer-rounds'
    try:
        for pair in range(args.pairs):
            order = ('original', 'compact') if pair % 2 == 0 else ('compact', 'original')
            for name in order:
                require(not (ROOT / 'FAULT.json').exists(), 'Fault appeared; stop remaining rounds')
                directory = output / f'pair-{pair+1:02d}-{name}'
                directory.mkdir(exist_ok=False)
                for index in range(48):
                    (directory / f'block-{index:02d}').mkdir(exist_ok=False)
                writer = original_writer if name == 'original' else compact_writer
                started = time.perf_counter_ns()
                for relative, value in records:
                    writer(directory / relative, value)
                elapsed = time.perf_counter_ns() - started
                files = verify_written(directory, records)
                record = {'pair': pair + 1, 'writer': name, 'elapsed_ns': elapsed,
                          'file_count': len(files), 'bytes': sum(row['bytes'] for row in files)}
                rows.append(record)
                original_writer(output / f'pair-{pair+1:02d}-{name}-inventory.json', files)
                original_writer(output / f'pair-{pair+1:02d}-{name}-result.json', record)
        phase = 'context-attribution'
        for number in range(args.pairs):
            require(not (ROOT / 'FAULT.json').exists(), 'Fault appeared; stop remaining rounds')
            elapsed = context_io_round(model_bytes, identity_bytes)
            record = {'round': number + 1, 'context_calls': CALL_COUNT, 'elapsed_ns': elapsed}
            context_rows.append(record)
            original_writer(output / f'context-{number+1:02d}.json', record)
        phase = 'final-source-check'
        for entry in inventory:
            require(digest(safe(SOURCE / entry['path']).read_bytes()) == entry['sha256'],
                    'Frozen call source changed during replay')
        require((ROOT / 'model-verification.json').read_bytes() == model_bytes and
                (SERVER / 'server-identity.json').read_bytes() == identity_bytes,
                'Context sources changed during replay')
        pairs = []
        for number in range(1, args.pairs + 1):
            arms = {r['writer']: r for r in rows if r['pair'] == number}
            pairs.append({'pair': number,
                          'original_ns': arms['original']['elapsed_ns'],
                          'compact_ns': arms['compact']['elapsed_ns'],
                          'saved_ns': arms['original']['elapsed_ns'] - arms['compact']['elapsed_ns']})
        report = {'schema': 'ltx.serializer-replay-result.v1', 'status': 'passed',
                  'writer_pairs': pairs, 'context_rounds': context_rows,
                  'median_writer_saved_seconds': statistics.median(p['saved_ns'] for p in pairs) / 1e9,
                  'median_context_subset_seconds': statistics.median(r['elapsed_ns'] for r in context_rows) / 1e9,
                  'parsed_json_equal': True, 'source_unchanged': True,
                  'native_imports_present': any(n == 'torch' or n.startswith(('torch.', 'comfy.')) for n in sys.modules),
                  'native_requests': 0, 'application_speed_qualified': False,
                  'scope': 'Offline realistic receipt-writer replay; kernel overlap and application speed remain unmeasured'}
        require(not report['native_imports_present'], 'Unexpected native import')
        original_writer(output / 'result.json', report)
        return report
    except BaseException as error:
        original_writer(output / 'failure.json', {'status': 'failed', 'phase': phase,
            'error': repr(error), 'completed_writer_rounds': rows, 'completed_context_rounds': context_rows,
            'action': 'halt; preserve all generated evidence, no retry'})
        raise


if __name__ == '__main__':
    print(json.dumps(run(parse_args()), indent=2))
