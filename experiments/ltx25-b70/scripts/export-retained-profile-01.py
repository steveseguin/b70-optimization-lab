#!/usr/bin/env python3
"""Read-only postmortem for the failed recorder01; never attach or submit."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from types import SimpleNamespace

LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
CAMPAIGN = 'retained-multiblock-profile-01'
SOURCE_SHA = '11b34a0104818c0d3aa627b1799daf7f545633f42216495fa4ce12b38a6a0db8'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    source = LANE / 'scripts/record-retained-multiblock-profile.py'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA
    diagnostic = load('profile01_postmortem', source)
    exporter = load('profile01_export_helpers', LANE / 'scripts/export-multiblock-screen-v3.py')
    client = diagnostic.load_client()
    directory = ROOT / CAMPAIGN
    args = SimpleNamespace(packet=ROOT / 'prepared-encoder-compiler-08',
        server_run=ROOT / 'encoder-server-compiler-08', manifest_sha256=diagnostic.PACKET_SHA)
    common = client.load('profile01_common', args.packet / 'launch/encoder_runtime_common.py')
    identity, _ = client.identity_binding(common, args.packet, args.manifest_sha256, args.server_run)
    binding = diagnostic.terminal_binding(client, args, identity)
    prereg = json.loads((directory / 'preregistration.json').read_text())
    failure = json.loads((directory / 'failure.json').read_text())
    assert prereg['source_sha256'] == SOURCE_SHA and prereg['identity'] == identity
    assert failure['phase'] == 'profiled-compiled-request'
    assert failure['error'] == "RuntimeError('unregistered/protected run')"
    run = CAMPAIGN + '-compiled-boat'
    assert not (ROOT / 'requests' / (CAMPAIGN + '-restored-boat')).exists()
    parity = json.loads((directory / (run + '-parity.json')).read_text())
    assert diagnostic.passed_parity(parity)
    receipts = client.receipt_helpers().validate_compiler_receipts(args.server_run, run, 'compiled',
        'all48', client.sha(args.server_run / 'server-identity.json'), 2)
    client.validate_owner_continuity(binding['owners'], receipts['request'])
    assert diagnostic.graph_bindings(receipts) == binding['graphs']
    profile = diagnostic.profile_summary(directory / 'stacks.json')
    exit_receipt = json.loads((directory / 'profiler-late-exit.json').read_text())
    assert exit_receipt['exit_code'] == 0
    assert not Path('/proc/' + str(exit_receipt['worker_pid'])).exists()
    kernel = (directory / 'kernel-postflight.log').read_text()
    matches = [line for line in kernel.splitlines() if re.search(
        r'Fault response|CAT error|engine reset|GPU HANG|GuC.*reset|coredump', line, re.I)]
    assert not matches and not (ROOT / 'FAULT.json').exists()
    postflight = {'campaign_status': 'failed-after-exact-clip', 'client_exit_code': 1,
        'failure': failure, 'native_requests_completed': 1, 'restored_request_submitted': False,
        'all_four_outputs_exact': True, 'retained_graph_evidence_unchanged': True,
        'pid': identity['pid'], 'boot_id': identity['boot_id'], 'last_dispatch': 'compiled',
        'queue': client.screen.get_json('/queue'), 'kernel_matches': matches,
        'fault_latch': False, 'profiler_exit_code': 0, 'profile': profile,
        'request_timing': json.loads((ROOT / 'requests' / run / 'profile.json').read_text()),
        'action': 'No new GPU requests after recorder failure; offline analysis and correction continue',
        'speed_promotion': False, 'streaming_qualification': False,
        'raw_media_retained': True, 'restoration_claim': False}
    assert not postflight['queue']['queue_running'] and not postflight['queue']['queue_pending']
    diagnostic.write(directory / 'postflight.json', postflight)
    paths = {source, Path(__file__).resolve(), args.server_run / 'server-identity.json',
        args.packet / 'manifest.json', LANE / 'data/retained-multiblock-profile-analysis-01.json',
        ROOT / 'output/validation' / run / 'summary.json'}
    for tree in (directory, ROOT / 'requests' / run, args.server_run / ('compiler-' + run)):
        exporter.add_tree(paths, tree)
    paths.add(args.server_run / ('encoder-placement-' + run + '.json'))
    # Existing screen03 export holds the full qualified graph/source closure.
    linked = LANE / 'data/multiblock-screen-03/evidence.json.gz'
    text, stable, total = {}, {}, 0
    for path in sorted(paths):
        raw, stable[path] = exporter.read_stable(path)
        total += len(raw)
        assert total <= exporter.MAX_TOTAL_BYTES
        text[exporter.archive_name(path)] = raw.decode('utf-8')
    compressed = gzip.compress(json.dumps(text, ensure_ascii=False).encode(), mtime=0)
    assert json.loads(gzip.decompress(compressed)) == text
    for path, before in stable.items():
        assert exporter.identity(path.stat()) == before
    output = LANE / 'data' / CAMPAIGN
    output.mkdir(exist_ok=False)
    (output / 'evidence.json.gz').write_bytes(compressed)
    summary = {**postflight, 'profile': {'sha256': profile['profile_sha256']},
        'archive_sha256': exporter.digest(compressed), 'archive_bytes': len(compressed),
        'text_files': len(text), 'linked_qualification_archive': str(linked.relative_to(LANE)),
        'linked_qualification_sha256': exporter.digest(linked.read_bytes())}
    diagnostic.write(output / 'summary.json', summary)
    diagnostic.write(output / 'inventory.json', {name: exporter.digest(value.encode()) for name, value in text.items()})
    print(json.dumps({'output': str(output), 'archive_bytes': len(compressed),
        'text_files': len(text), 'status': summary['campaign_status']}, indent=2))


if __name__ == '__main__':
    main()
