#!/usr/bin/env python3
"""Extend the frozen encoder packet with startup identity and placement checks."""
import argparse
import ast
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import encoder_runtime_common as common

LANE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('base_preparer', LANE / 'scripts/prepare-encoder-runtime.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def prepare(output):
    # Validate the additional inputs before creating the new snapshot.
    runtime = common.runtime_fingerprints()
    common.verify_runtime(runtime)
    diagnostic_patch = LANE / 'patches/resident-node-encoder-diagnostics.patch'
    inputs = [diagnostic_patch] + [LANE / 'scripts' / name for name in
        ('encoder_diagnostics.py', 'encoder_identity_node.py', 'serve-encoder.py', 'encoder_runtime_common.py')]
    for path in inputs:
        common.require(path.is_file() and not path.is_symlink(), 'Missing v2 input: ' + str(path))
        if path.suffix == '.py':
            ast.parse(path.read_text(), filename=str(path))
    original = base.prepare(output)
    (output / 'manifest.json').rename(output / 'base-manifest.json')
    (output / 'STATUS.txt').write_text('INCOMPLETE: v2 preparation; do not launch.\n')
    patch = output / 'patches' / diagnostic_patch.name
    shutil.copyfile(diagnostic_patch, patch)
    subprocess.run(['git', 'apply', '--check', str(patch)], cwd=output / 'source', check=True)
    subprocess.run(['git', 'apply', str(patch)], cwd=output / 'source', check=True)
    for name in ('encoder_diagnostics.py', 'encoder_identity_node.py'):
        shutil.copyfile(LANE / 'scripts' / name, output / 'source/scripts' / name)
    for node, helper in common.NODES.items():
        target = output / 'source/custom_nodes' / node
        target.mkdir(exist_ok=True)
        shutil.copyfile(output / 'source/scripts' / helper, target / '__init__.py')
    (output / 'launch').mkdir()
    startup_tools = {}
    for name in ('serve-encoder.py', 'encoder_runtime_common.py'):
        target = output / 'launch' / name
        shutil.copyfile(LANE / 'scripts' / name, target)
        startup_tools[name] = common.sha(target)
    shutil.copyfile(LANE / 'data/model-paths.yaml', output / 'model-paths.yaml')
    for variant in ('control', 'crop', 'small_state', 'combined'):
        path = output / 'graphs' / f'{variant}.json'
        graph = json.loads(path.read_text())
        for key in ('positive', 'negative'):
            common.require(graph['365']['inputs'][key] == ['364', 0], 'Unexpected conditioning edge')
        graph['421'] = {'class_type': 'LTXEncoderPlacementCheck', 'inputs': {
            'clip': ['420', 1], 'conditioning': ['364', 0], 'run_name': 'assign-unique-request-name',
            'encoder_variant': variant}}
        for key in ('positive', 'negative'):
            graph['365']['inputs'][key] = ['421', 0]
        path.write_text(json.dumps(graph, indent=2) + '\n')
    manifest = {
        'schema': 'ltx.encoder-runtime-packet.v2', 'status': 'prepared-inactive-not-deployed',
        'source_commit': common.PIN,
        'base_manifest_sha256': common.sha(output / 'base-manifest.json'),
        'preparer_v2_sha256': common.sha(Path(__file__)),
        'model_verification_sha256': common.MODEL_VERIFICATION_SHA256,
        'runtime': runtime, 'startup_tools': startup_tools,
        'extension_sha256s': {name: common.sha(output / 'source/scripts' / name) for name in common.EXTENSIONS},
        'patch_order': original['patch_order'] + [diagnostic_patch.name],
        'patch_sha256s': {**original['patch_sha256s'], diagnostic_patch.name: common.sha(patch)},
        'files': base.inventory(output),
        'limitations': ['Inactive; no process migration is performed by preparation.',
                       'One persistent process, explicit variant transitions, no automatic restart or retry.',
                       'Native-weight XPU placement, full-clip parity and speed remain unqualified.',
                       'Graphs are templates; unique request names are required.',
                       'Compiler candidate is not included.'],
    }
    manifest['files'].pop('STATUS.txt')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'STATUS.txt').write_text('PREPARED, INACTIVE. Startup and client checks required before GPU use.\n')
    digest = common.sha(output / 'manifest.json')
    common.verify_packet(output, digest)
    return digest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    digest = prepare(args.output)
    print(json.dumps({'packet': str(args.output), 'manifest_sha256': digest, 'status': 'prepared-inactive-not-deployed'}, indent=2))
