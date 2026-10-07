#!/usr/bin/env python3
"""Plan or explicitly build a separate packet99 runtime candidate; never launch.

Input source-only packet remains immutable. Dependency-pending output is useful
for CPU review but its launcher refuses admission. No existing output overwrite.
"""
import argparse
import difflib
import importlib.util
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
LANE = HERE.parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


C = load(HERE / 'check-runtime-99.py', 'runtime99_checker_builder')


def plan():
    source_builder = load(HERE / 'prepare-upstream-99.py', 'source99_builder_runtimeplan')
    source_checker = load(HERE / 'check-upstream-source-99.py', 'source99_checker_runtimeplan')
    source_plan, _, _, _ = source_builder.plan()
    source_checker.validate_plan(source_plan)
    parent = C.historical_manifest()
    overlays = {}
    for path in sorted(set(C.PORT_PINS) | set(C.ATTENTION_FILES)):
        raw = C.regular(C.HISTORICAL / 'source' / path)
        C.require(C.digest(raw) == source_plan['source_files'][path]['sha256'], 'Unexpected original port source')
        modified = C.port_source(path, raw, source_plan['source_files'])
        overlays[path] = {'before_sha256': C.digest(raw), 'after_sha256': C.digest(modified),
                          'diff': ''.join(difflib.unified_diff(raw.decode().splitlines(keepends=True),
                              modified.decode().splitlines(keepends=True), fromfile='source99/' + path,
                              tofile='runtime99/' + path))}
    return {'status': 'runtime99-build-plan-not-materialized-not-qualified',
            'input': str(C.SOURCE_INPUT), 'output': str(C.PACKET),
            'upstream_commit': C.PIN, 'historical_manifest_sha256': C.OLD_MANIFEST,
            'source_files': len(source_plan['source_files']), 'source_bytes': source_plan['source_bytes'],
            'non_source_dependencies': sum(not p.startswith('source/') for p in parent['files']),
            'runtime_source_overlays': overlays,
            'launch_gates': ['all historical packet gates on preserved historical packet',
                'source99 independent input check plus exact runtime port edits',
                'frozen B1/W2/23-25/shared-pool/card2/256x256 control',
                'matched isolated application dependencies (pending)',
                'actual application NOFILE soft>=65536 hard1048576',
                '50GiB reserve plus4GiB declared write allowance',
                'mandatory fresh four-card health receipt and unchanged ownership/journal gates',
                'process-local CPU-tested progress display lock cleanup'],
            'qualification': False, 'model_requests': 0}


def write_new(path, raw, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), mode); os.fsync(stream.fileno())


def build(source, output, runner, memory_helper, dependencies=None):
    C.require(source == C.SOURCE_INPUT and output == C.PACKET, 'Only agreed source/runtime packet paths admitted')
    C.require(not output.exists() and not output.is_symlink() and output.parent.is_dir() and
              not any(p.is_symlink() for p in output.parents), 'New output with regular parent required')
    checker = load(HERE / 'check-upstream-source-99.py', 'source99_checked_build')
    checked = checker.check(source)
    source_plan_raw = C.regular(source / 'source-plan.json'); source_plan = C.load_json(source_plan_raw)
    parent = C._LEGACY.verify_packet(C.HISTORICAL, C.OLD_MANIFEST)
    dependency_raw = None
    if dependencies is not None:
        C.require(dependencies == C.DEPENDENCY_RECEIPT, 'Unexpected dependency receipt path')
        dependency_raw = C.regular(dependencies)
        C.verify_dependencies(dependency_raw, parent['runtime'])
    C.require(runner is not None and memory_helper is not None, 'Explicit reviewed runner and memory helper required')
    bindings = {}
    for name, path in [('runner', runner), ('memory_helper', memory_helper)]:
        raw = C.regular(path)
        bindings[name] = {'source': str(path), 'sha256': C.digest(raw),
                          'packet_path': 'campaign/' + path.name}
    storage = load(HERE.parents[2] / 'scripts/check-storage-headroom.py', 'runtime99_build_storage')
    allowance = 384 * 1024**2
    admission = storage.inspect_destination(output, C.MIN_FREE, allowance)
    C.require(admission['admitted'], 'Runtime preparation requires50GiB reserve plus384MiB')
    # All preflight checks precede creating the owned output. Failure leaves an
    # explicitly incomplete candidate for review, never removes old evidence.
    output.mkdir(mode=0o700)
    write_new(output / 'STATUS.txt', C.STATUS)
    for path, row in source_plan['source_files'].items():
        raw = C.regular(source / 'source' / path)
        C.require(C.digest(raw) == row['sha256'], 'Source changed after input verification')
        if path in C.PORT_PINS or path in C.ATTENTION_FILES:
            write_new(output / 'provenance/source-before-port' / path, raw)
            raw = C.port_source(path, raw, source_plan['source_files'])
        write_new(output / 'source' / path, raw, int(row['mode'], 8) & 0o777)
    for path, expected in parent['files'].items():
        if path.startswith('source/'):
            continue
        raw = C.regular(C.HISTORICAL / path)
        C.require(C.digest(raw) == expected, 'Historical non-source dependency changed')
        target = 'provenance/packet98/' + path if path.startswith('launch/') else path
        write_new(output / target, raw)
    for filename in ['prepare-upstream-99.py', 'check-upstream-source-99.py']:
        write_new(output / 'provenance/source99' / filename, C.regular(HERE / filename))
    write_new(output / 'provenance/source99/source-plan.json', source_plan_raw)
    write_new(output / 'provenance/source99/source-check.json',
              (json.dumps(checked, indent=2, sort_keys=True) + '\n').encode())
    for name in ['packet98-manifest.json', 'upstream-source.tar']:
        write_new(output / 'provenance/source99' / name, C.regular(source / 'provenance' / name))
    write_new(output / 'provenance/build-runtime-99.py', C.regular(Path(__file__).resolve()))
    check_raw = C.regular(HERE / 'check-runtime-99.py')
    write_new(output / 'provenance/check-runtime-99.py', check_raw)
    write_new(output / 'launch/encoder_runtime_common.py', check_raw)
    write_new(output / 'launch/serve-encoder.py', C.launcher_source(C.regular(C.HISTORICAL / 'launch/serve-encoder.py')))
    write_new(output / 'launch/check-storage-headroom.py', C.regular(HERE.parents[2] / 'scripts/check-storage-headroom.py'))
    progress = LANE / 'recovery/20261007-progress-lock'
    for name in ['launch_with_progress_lock.py', 'refresh.original.py', 'refresh.candidate.py',
                 'identity.json', 'result.json', 'TQDM-LICENCE']:
        write_new(output / 'provenance/progress-lock' / name, C.regular(progress / name))
    write_new(output / 'launch/progress_lock.py', C.progress_module(C.regular(progress / 'launch_with_progress_lock.py').decode()))
    for name in ['refresh.original.py', 'refresh.candidate.py']:
        write_new(output / 'launch' / name, C.regular(progress / name))
    for binding in bindings.values():
        raw = C.regular(Path(binding['source']))
        C.require(C.digest(raw) == binding['sha256'], 'Campaign helper changed during build')
        write_new(output / binding['packet_path'], raw)
    if dependency_raw is not None:
        write_new(output / 'provenance/dependencies.json', dependency_raw)
    proposal = plan()
    write_new(output / 'provenance/runtime-port.json', (json.dumps(proposal, indent=2, sort_keys=True) + '\n').encode())
    files = {str(p.relative_to(output)): C.sha(p) for p in output.rglob('*')
             if p.is_file() and p != output / 'STATUS.txt'}
    transition = {'schema': 'ltx.upstream99.runtime-transition.v1',
                  'source_input': str(source), 'source_plan_sha256': C.digest(source_plan_raw),
                  'historical_manifest_sha256': C.OLD_MANIFEST,
                  'source_runtime_overlays': proposal['runtime_source_overlays'],
                  'campaign_bindings': bindings,
                  'dependencies': {'state': 'pending', 'reason': 'Isolated new-upstream application dependencies not yet bound'},
                  'historical_contract_sections': 'Retained as historical behavior contracts; upstream source changes explicitly recorded separately',
                  'progress_overlay': {'source': 'launch/progress_lock.py', 'sha256': files['launch/progress_lock.py'],
                                       'original_refresh_sha256': files['launch/refresh.original.py'],
                                       'candidate_refresh_sha256': files['launch/refresh.candidate.py']},
                  'control': {'layout': 'two-way', 'blocks': [23, 25], 'workers': 2, 'batch': 1,
                              'shared_pool': 1, 'decode_replica': 'xpu:2', 'size': '256x256', 'references': 'w93c'},
                  'storage_admission': admission,
                  'qualification': False, 'model_requests': 0}
    if dependency_raw is not None:
        transition['dependencies'] = {'state': 'matched', 'receipt_sha256': C.digest(dependency_raw),
                                      'receipt_source': str(dependencies), 'overlay_root': str(C.DEPENDENCY_ROOT)}
    manifest = C.semantic_manifest(parent, files, C.sha(Path(__file__).resolve()), transition)
    write_new(output / 'manifest.json', (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode())
    for directory in [p for p in output.rglob('*') if p.is_dir()] + [output, output.parent]:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    digest = C.sha(output / 'manifest.json')
    C.verify_packet(output, digest)
    return {'status': ('prepared-candidate-for-controlled-qualification' if dependency_raw is not None
                      else 'prepared-candidate-dependencies-pending-launch-refused'), 'packet': str(output),
            'manifest_sha256': digest, 'qualification': False, 'model_requests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--source', type=Path, default=C.SOURCE_INPUT)
    parser.add_argument('--output', type=Path, default=C.PACKET)
    parser.add_argument('--runner', type=Path)
    parser.add_argument('--memory-helper', type=Path)
    parser.add_argument('--dependencies', type=Path, help='Completed isolated dependency receipt; omitted means launch refused')
    args = parser.parse_args()
    result = build(args.source, args.output, args.runner, args.memory_helper, args.dependencies) if args.build else plan()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
