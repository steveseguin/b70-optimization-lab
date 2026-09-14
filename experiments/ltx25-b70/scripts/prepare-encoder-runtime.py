#!/usr/bin/env python3
"""Build an inactive, hash-bound source packet. Never import or start ComfyUI."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile

LANE = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/steve/src/ComfyUI-ltx25-baseline')
EVIDENCE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PIN = '19e1058f4c445ef74047e77a23f9ca7684c1e4b6'
PATCHES = (
    'encoder-small-state-residency.patch',
    'encoder-small-state-policy-guard.patch',
    'encoder-crop-before-cpu-opt-in.patch',
    'encoder-clip-options.patch',
    'resident-node-encoder-options.patch',
)
HELPERS = {
    'resident_node.py': '4ba038673b97f45e5c283511fa97389c4e9b4301eb98c6090a4b576705ab7277',
    'ltx_layer_shard.py': '0c836c2c19ef678360c4e5dddb09173d60e0fd011e44430370485abd63336d3b',
    'capture_node.py': '6495b0c4de7ac054e35a39fb00e7c7b979d5fb51d6e77bc0dee18bad9d0ec9da',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(['git', '-C', str(SOURCE), *args], timeout=60)


def inventory(root):
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise RuntimeError(f'Unexpected symlink: {p}')
        if p.is_file():
            result[str(p.relative_to(root))] = sha(p.read_bytes())
    return result


def unpack_source(data, destination):
    """Only regular tracked files/directories; no links, devices or traversal."""
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
        members = archive.getmembers()
        if sum(m.size for m in members) > 128 * 1024**2:
            raise RuntimeError('Unexpected source archive size')
        for member in members:
            p = PurePosixPath(member.name)
            if p.is_absolute() or '..' in p.parts or '.git' in p.parts:
                raise RuntimeError(f'Unsafe archive path: {p}')
            if not (member.isdir() or member.isfile()):
                raise RuntimeError(f'Unsupported archive entry: {p}')
        for member in members:
            target = destination / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as handle:
                    handle.write(archive.extractfile(member).read())
                target.chmod(0o755 if member.mode & 0o111 else 0o644)


def prepare(output):
    # Fixed evidence parent and new packet only. No in-place source edits.
    if output.parent != EVIDENCE or not re.fullmatch(r'prepared-encoder-[a-z0-9-]+', output.name):
        raise ValueError('Output must be a new prepared-encoder-* directory in the evidence root')
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    if git('rev-parse', 'HEAD').decode().strip() != PIN:
        raise RuntimeError('Unexpected frozen source revision')
    if git('diff', 'HEAD', '--'):
        raise RuntimeError('Frozen tracked core has changed')
    helper_bytes = {name: (LANE / 'scripts' / name).read_bytes() for name in HELPERS}
    for name, data in helper_bytes.items():
        if sha(data) != HELPERS[name]:
            raise RuntimeError(f'Frozen helper changed: {name}')
    patch_bytes = {name: (LANE / 'patches' / name).read_bytes() for name in PATCHES}
    if shutil.disk_usage(EVIDENCE).free < 5 * 1024**3:
        raise RuntimeError('Less than 5 GiB available')
    archive = git('archive', '--format=tar', PIN)
    output.mkdir()
    (output / 'STATUS.txt').write_text('INCOMPLETE: source preparation in progress; do not launch.\n')
    staged = output / 'source'
    staged.mkdir()
    unpack_source(archive, staged)
    (staged / 'scripts').mkdir(exist_ok=False)
    for name, data in helper_bytes.items():
        (staged / 'scripts' / name).write_bytes(data)
    before = inventory(staged)
    (output / 'patches').mkdir()
    for name, data in patch_bytes.items():
        patch = output / 'patches' / name
        patch.write_bytes(data)
        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=staged, check=True, timeout=30)
        subprocess.run(['git', 'apply', str(patch)], cwd=staged, check=True, timeout=30)
    after = inventory(staged)
    changed = {name: {'before': before.get(name), 'after': after.get(name)}
               for name in sorted(before.keys() | after.keys())
               if before.get(name) != after.get(name)}
    expected_changes = {'comfy/model_patcher.py', 'comfy/sd1_clip.py',
                        'comfy/text_encoders/lt.py', 'comfy/sd.py', 'scripts/resident_node.py'}
    if set(changed) != expected_changes or before.keys() != after.keys():
        raise RuntimeError('Unexpected source paths changed by encoder patches')
    for name in changed:
        if name.endswith('.py'):
            ast.parse((staged / name).read_text(), filename=name)
    # No absolute symlinks back to the running extension or workspace code.
    for node, helper in [('ltx_speed_lab', 'resident_node.py'),
                         ('ltx_baseline_capture', 'capture_node.py')]:
        target = staged / 'custom_nodes' / node
        target.mkdir(exist_ok=False)
        shutil.copyfile(staged / 'scripts' / helper, target / '__init__.py')
    graphs = output / 'graphs'
    graphs.mkdir()
    baseline = json.loads((LANE / 'data/speed-resident-split-api.json').read_text())
    for variant in ('control', 'crop', 'small_state', 'combined'):
        graph = json.loads(json.dumps(baseline))
        graph['420']['inputs']['encoder_variant'] = variant
        (graphs / f'{variant}.json').write_text(json.dumps(graph, indent=2) + '\n')
    # Recheck protected source after staging. Failure leaves the packet inactive.
    if git('rev-parse', 'HEAD').decode().strip() != PIN or git('diff', 'HEAD', '--') or any(
            (LANE / 'scripts' / name).read_bytes() != data for name, data in helper_bytes.items()):
        raise RuntimeError('Protected source changed during preparation')
    manifest = {
        'schema': 'ltx.encoder-source-packet.v1',
        'status': 'prepared-inactive-not-deployed',
        'source_commit': PIN,
        'source_archive_sha256': sha(archive),
        'preparer_sha256': sha(Path(__file__).read_bytes()),
        'frozen_helper_sha256s': HELPERS,
        'patch_order': list(PATCHES),
        'patch_sha256s': {name: sha(data) for name, data in patch_bytes.items()},
        'changed_sources': changed,
        'files': inventory(output),
        'limitations': [
            'No launcher or process migration is included; do not run main.py directly.',
            'New startup identity, locks, fault monitor and receipt directory still required.',
            'Graphs are templates: assign unique capture and preview names before any submission.',
            'No XPU residency, native-model parity or speed qualification.',
            'Compiler candidate is not included in this encoder-only packet.',
        ],
    }
    # STATUS is human-readable, not part of the immutable content inventory.
    manifest['files'].pop('STATUS.txt')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'STATUS.txt').write_text('PREPARED, INACTIVE. Read manifest limitations. No launcher included.\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.output)
    print(json.dumps({'output': str(args.output), 'status': result['status'],
                      'files': len(result['files']), 'changed_sources': result['changed_sources']}, indent=2))
