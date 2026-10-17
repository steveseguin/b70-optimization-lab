#!/usr/bin/env python3
"""Seal verified CPU preparation. Never starts a device or health probe."""
from datetime import datetime, timezone
import json
from pathlib import Path

from preparation import limits
from window_support import HERE, REPO, require, sha, verify_files

GATES = ('python-gates.json', 'cpu-layer-gates.json',
         'cpu-expert/evidence/test/receipt.json', 'cpu-expert/evidence/bench/receipt.json',
         'diagnostics/evidence/cpu-gate/receipt.json')


def load_gate(relative):
    row = json.loads((HERE / relative).read_text())
    require(row.get('passed') is True and row.get('device_executed') is False,
            'CPU gate missing/failed: ' + relative)
    return row


def main():
    admission = limits()  # Large compiled-input hashing also waits for the protected window.
    source_pins, artifacts, gate_pins = {}, {}, {}
    def merge_sources(mapping):
        verify_files(mapping, REPO)
        for name, digest in mapping.items():
            require(name not in source_pins or source_pins[name] == digest, 'source identity conflict: ' + name)
            source_pins[name] = digest
    builds = {}
    for mode in ('host', 'device'):
        path = HERE / f'build-layer-{mode}.json'
        row = json.loads(path.read_text())
        require(row.get('passed') is True and row.get('device_executed') is False and row.get('mode') == mode,
                'incomplete CPU-only layer build: ' + mode)
        merge_sources(row['source_hashes'])
        verify_files(row['baseline_provenance'], REPO)
        verify_files(row['artifacts'], REPO)
        for name, digest in row['artifacts'].items():
            artifacts[str((REPO / name).relative_to(HERE))] = digest
        builds[mode] = sha(path)
        gate_pins[path.name] = sha(path)
    gates = {name: load_gate(name) for name in GATES}
    python = gates['python-gates.json']
    merge_sources(python['sources'])
    layer = gates['cpu-layer-gates.json']
    require(layer['build_receipt_sha256'] == builds['host'], 'CPU layer gate belongs to another build')
    merge_sources(layer['source_hashes'])
    verify_files(layer['artifacts'], REPO)
    require(layer['exact_capture_manifest_sha256'] == sha(HERE / 'exact-capture-manifest.json'),
            'capture manifest changed after CPU gate')
    require(len(layer['repeats']) == 2 and layer['repeats'][0]['receipt']['exact_output_identity'] ==
            layer['repeats'][1]['receipt']['exact_output_identity'], 'fresh CPU layer repeats missing/different')
    from summarize import exact
    for row in layer['repeats']:
        verify_files(row['files'], REPO)
        receipt_name = next(name for name in row['files'] if name.endswith('/receipt.json'))
        exact((REPO / receipt_name).parent, cpu=True, manifest_path=HERE / 'exact-capture-manifest.json')
    expert = gates['cpu-expert/evidence/test/receipt.json']
    require(expert.get('fresh_process_repeats_equal') is True and len(expert['results']) == 2,
            'fresh CPU expert gate missing')
    expert_sources = {str((HERE / 'cpu-expert' / name).resolve().relative_to(REPO)): digest
                      for name, digest in expert['build']['sources'].items()}
    merge_sources(expert_sources)
    artifacts['cpu-expert/build/cpu-expert'] = expert['build']['binary_sha256']
    bench = gates['cpu-expert/evidence/bench/receipt.json']
    require(bench['build'] == expert['build'] and bench.get('repeat_processes') == 2,
            'CPU throughput belongs to another arithmetic build or lacks fresh repeat')
    diagnostic = gates['diagnostics/evidence/cpu-gate/receipt.json']
    require(diagnostic.get('fresh_process_repeats_equal') is True,
            'fresh diagnostic mock gate missing')
    merge_sources({str((HERE / name).relative_to(REPO)): digest
                   for name, digest in diagnostic['source_sha256'].items()})
    artifacts['build/diagnostics/cpu-mock'] = diagnostic['binary_sha256']
    verify_files(artifacts, HERE)
    # Bind both mock/gate source and coordinator executable commands. Markdown
    # review notes can evolve; the actual runbook/preregistration cannot drift.
    own_files = [p for p in HERE.iterdir() if p.is_file() and p.suffix in ('.py', '.sh', '.cpp', '.hpp')]
    own_files += [HERE / name for name in ('CMakeLists.txt', 'WINDOW.md', 'PREREGISTRATION.md',
                 'dispatch-baseline.json', 'exact-capture-manifest.json', 'cache-budget.json')]
    merge_sources({str(p.relative_to(REPO)): sha(p) for p in own_files})
    gate_pins.update({name: sha(HERE / name) for name in GATES})
    result = dict(schema='own-runtime.packet46.seal.v1', passed=True, device_executed=False,
                  device_qualified=False, model_speed_claim=False, card=0, context_capacity=4096,
                  integration_bar_saved_gpu_us_per_layer=80, sources=source_pins, artifacts=artifacts,
                  gates=gate_pins, cpu_preparation=admission,
                  completed_utc=datetime.now(timezone.utc).isoformat(),
                  pending=['fresh card-0 every-intermediate/state exactness',
                           'two fresh GPU timing owners and 80 us bar',
                           'CPU nonfinite device-oracle parity', 'one-card runtime fit and integration'])
    (HERE / 'seal.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, seal_sha256=sha(HERE / 'seal.json'),
                          sources=len(source_pins), artifacts=len(artifacts), device_executed=False)))


if __name__ == '__main__':
    main()
