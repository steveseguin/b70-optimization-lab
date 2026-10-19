#!/usr/bin/env python3
"""Seal a future screen candidate after one changed-class CPU byte fixture."""
import argparse
import os
from pathlib import Path

from common import ARITHMETIC, ROOT, read, require, save, sha, verify_map


def create(lineage, profile, build_path, fixture_path, binary, dispatch, output):
    lineage = lineage.resolve()
    build, fixture = read(build_path), read(fixture_path)
    require(not output.exists(), 'never overwrite an existing seal')
    require(build.get('passed') is True and build.get('device_executed') is False,
            'completed CPU build receipt required')
    sources = build.get('sources', build.get('sources_sha256'))
    verify_map(ROOT, sources)
    artifacts = build.get('artifacts', build.get('binaries'))
    verify_map(lineage, artifacts)
    require(artifacts.get(str(binary.resolve().relative_to(lineage))) == sha(binary), 'unbound native binary')
    require(fixture.get('schema') == 'own-runtime.screen.byte-fixture.v1'
            and fixture.get('passed') is True and fixture.get('device_executed') is False,
            'changed-class CPU byte fixture required')
    require(fixture.get('build_receipt_sha256') == sha(build_path), 'fixture belongs to another build')
    require(isinstance(fixture.get('changed_class'), str) and fixture['changed_class'].strip()
            and isinstance(fixture.get('command'), list) and fixture['command'], 'fixture class/command missing')
    verify_map(ROOT, fixture.get('sources'))
    for key in ('expected', 'actual'):
        row = fixture[key]
        verify_map(lineage, {row['path']: row['sha256']})
    require(fixture['actual']['sha256'] == fixture['expected']['sha256'], 'CPU bytes differ')
    require((lineage / fixture['actual']['path']).stat().st_size > 0, 'empty byte fixture')
    sources = dict(sources, **fixture['sources'])
    for path in (dispatch, lineage / 'selection.json', lineage / 'memory-plan.json'):
        sources[str(path.resolve().relative_to(ROOT))] = sha(path)
    gates = {str(path.resolve().relative_to(lineage)): sha(path) for path in (build_path, fixture_path)}
    save(output, dict(schema='own-runtime.screen.cpu-seal.v1', passed=True, device_executed=False,
                      arithmetic=ARITHMETIC, profile=profile, sources=sources, artifacts=artifacts,
                      gates=gates, fixture_files={fixture[k]['path']:fixture[k]['sha256'] for k in ('expected','actual')},
                      qualification='screen only; no full-chain qualification'))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile', choices=('tp2', 'onecard'), required=True)
    for name in ('lineage', 'build-receipt', 'fixture', 'binary', 'dispatch', 'output'):
        ap.add_argument('--' + name, type=Path, required=True)
    args = ap.parse_args()
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(4,16)) | set(range(20,32)), 'CPU affinity')
    create(args.lineage, args.profile, args.build_receipt, args.fixture, args.binary, args.dispatch, args.output)
