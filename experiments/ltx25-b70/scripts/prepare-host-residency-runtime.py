#!/usr/bin/env python3
"""Prepare packet13: text-encoder full residency by lowering the VRAM reserve.

The ONLY numerical-source change is none: every `source/` and `graphs/` byte is
inherited unchanged from packet12. Exactly two launch files change -- the
launcher's `--reserve-vram` value and the checker's `verify_packet`, which is
replaced by one that pins this packet to packet12's verified manifest instead of
re-deriving the ten-generation ancestry it already established.

No native imports, no endpoint calls, no device discovery, no application action.
"""
import argparse
import ast
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PARENT = ROOT / 'prepared-encoder-host-residency-parent'
PARENT_NAME = 'prepared-encoder-host-embedding-12'
PARENT_SHA = 'b29b750c31feda9d4be7fdc768e876a1f5d58ad11a699022b1d8ae6bdaa59666'
OUTPUT = ROOT / 'prepared-encoder-host-residency-13'
CHECKER = 'launch/encoder_runtime_common.py'
LAUNCHER = 'launch/serve-encoder.py'
PROV = 'provenance/host-residency/parent/'
PARENT_MANIFEST_FILE = 'host-embedding-12-parent-manifest.json'
OLD_RESERVE, NEW_RESERVE = '6', '2'

NEW_VERIFY = '''def verify_packet(packet, expected_manifest_sha256):
    """Packet13 gate: inherit packet12 wholesale, permit one launch-argument change.

    Packet12's own manifest digest is pinned here, and packet12 was verified by
    its own checker against the full encoder/compiler/RMS/activation/multiblock/
    adjacent-state/onepass/na-axis/host-embedding ancestry. Requiring every
    packet12 file to reappear byte-identically therefore transitively preserves
    that entire chain, including all numerical source and every original graph.
    """
    packet = Path(packet)
    require(packet.is_absolute() and packet.parent == ROOT and
            re.fullmatch(r'prepared-encoder-[a-z0-9-]+', packet.name), 'Unexpected packet path')
    manifest_path = safe_path(packet, 'manifest.json')
    require(re.fullmatch(r'[0-9a-f]{64}', expected_manifest_sha256) is not None,
            'Explicit manifest SHA256 required')
    require(sha(manifest_path) == expected_manifest_sha256, 'Packet manifest changed')
    manifest = json.loads(manifest_path.read_text())
    require(manifest['schema'] == 'ltx.host-residency-runtime-packet.v1', 'Launcher requires residency packet')
    require(manifest['source_commit'] == PIN, 'Core revision changed')
    require(manifest['model_verification_sha256'] == MODEL_VERIFICATION_SHA256, 'Model identity changed')
    require(manifest['status'] == 'prepared-inactive-not-deployed', 'Unexpected packet status')
    for name, digest in manifest['files'].items():
        p = safe_path(packet, name)
        require(p.is_file() and sha(p) == digest, 'Packet file changed: ' + name)
    actual = set()
    for p in packet.rglob('*'):
        require(not p.is_symlink(), 'Unexpected packet symlink')
        if p.is_file():
            actual.add(str(p.relative_to(packet)))
    require(actual == set(manifest['files']) | {'manifest.json', 'STATUS.txt'},
            'Uninventoried packet files; inspect before use')
    require(set(manifest['extension_sha256s']) == set(EXTENSIONS), 'Extension set changed')
    for name, digest in manifest['extension_sha256s'].items():
        require(manifest['files']['source/scripts/' + name] == digest, 'Extension hash disagrees')
    for node, helper in NODES.items():
        require(manifest['files'][f'source/custom_nodes/{node}/__init__.py'] ==
                manifest['extension_sha256s'][helper], 'Custom node copy differs from helper')
    for name, digest in manifest['startup_tools'].items():
        require(manifest['files']['launch/' + name] == digest, 'Startup tool hash disagrees')

    residency = manifest['host_residency']
    require(residency['parent_packet'] == 'prepared-encoder-host-embedding-12' and
            residency['parent_manifest_sha256'] ==
            'b29b750c31feda9d4be7fdc768e876a1f5d58ad11a699022b1d8ae6bdaa59666',
            'Unexpected residency parent')
    parent_path = safe_path(packet, 'host-embedding-12-parent-manifest.json')
    require(sha(parent_path) == residency['parent_manifest_sha256'], 'Parent manifest changed')
    parent = json.loads(parent_path.read_text())
    require(parent['schema'] == 'ltx.host-embedding-runtime-packet.v2', 'Unexpected parent schema')
    require(manifest['runtime'] == parent['runtime'], 'Residency runtime differs from parent')
    require(manifest['model_verification_sha256'] == parent['model_verification_sha256'] and
            manifest['source_commit'] == parent['source_commit'], 'Parent identity differs')

    # Every packet12 byte reappears here, except the two launch files whose
    # originals are preserved verbatim under provenance.
    changed = ('launch/encoder_runtime_common.py', 'launch/serve-encoder.py')
    for name, digest in parent['files'].items():
        if name in changed:
            require(manifest['files']['provenance/host-residency/parent/' + name] == digest,
                    'Original launch source changed: ' + name)
        else:
            require(manifest['files'].get(name) == digest, 'Inherited packet12 file changed: ' + name)
    added = {'provenance/host-residency/parent/' + n for n in changed} | {'host-embedding-12-parent-manifest.json'}
    require(set(manifest['files']) == set(parent['files']) | added, 'Packet13 file inventory changed')
    for name in parent['files']:
        if name.startswith(('source/', 'graphs/')):
            require(manifest['files'][name] == parent['files'][name],
                    'Numerical source or graph changed: ' + name)

    # The launcher differs from packet12 by exactly the reserved-VRAM literal.
    original = safe_path(packet, 'provenance/host-residency/parent/launch/serve-encoder.py').read_text()
    current = safe_path(packet, 'launch/serve-encoder.py').read_text()
    diff = [line for line in difflib.unified_diff(original.splitlines(), current.splitlines(), n=0)
            if line.startswith(('+', '-')) and not line.startswith(('+++', '---'))]
    require(len(diff) == 2 and diff[0].startswith('-') and diff[1].startswith('+') and
            diff[0][1:].replace("'--reserve-vram', '6'", "'--reserve-vram', '2'") == diff[1][1:] and
            "'--reserve-vram', '6'" in diff[0] and "'--reserve-vram', '2'" in diff[1],
            'Launcher differs from packet12 beyond the reserved-VRAM literal')
    module = ast.parse(current)
    fn, = [n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'server_args']
    literals = [n.value for n in ast.walk(fn) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    require(literals.count('--reserve-vram') == 1 and
            literals[literals.index('--reserve-vram') + 1] == '2', 'Reserved VRAM literal is not 2')
    require(residency == {
        'parent_packet': 'prepared-encoder-host-embedding-12',
        'parent_manifest_sha256': 'b29b750c31feda9d4be7fdc768e876a1f5d58ad11a699022b1d8ae6bdaa59666',
        'change': 'launcher --reserve-vram 6 -> 2 GiB; checker verify_packet replaced',
        'reserve_vram_gb': 2.0, 'parent_reserve_vram_gb': 6.0,
        'intent': 'let the ~25.1 GB text encoder load fully resident on xpu:2 instead of '
                  'offloading 457-600 MB that are re-copied by blocking pageable transfers each forward',
        'numerical_source_changed': False, 'graphs_changed': False, 'extensions_changed': False,
        'force_full_load': False, 'reserve_override': True,
        'expected_outputs': 'bitwise identical; weight values are unchanged, only their residence',
        'native_gpu_qualified': False, 'full_clip_qualified': False, 'speed_qualified': False,
    }, 'Residency contract changed')
    return manifest
'''


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def build_checker(text):
    start = text.index('def verify_packet(packet, expected_manifest_sha256):')
    end = text.index('def verify_model_receipt():')
    require(start < end, 'Unexpected checker layout')
    require(text.count('def verify_packet(') == 1, 'Ambiguous verify_packet')
    updated = text[:start] + NEW_VERIFY + '\n\n' + text[end:]
    require('import difflib' not in text, 'Checker already imports difflib')
    updated = updated.replace('import copy\n', 'import copy\nimport difflib\n', 1)
    require(updated.count('import difflib') == 1, 'difflib import not added exactly once')
    ast.parse(updated)
    return updated


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--parent', type=Path, default=ROOT / PARENT_NAME)
    ap.add_argument('--output', type=Path, default=OUTPUT)
    a = ap.parse_args()
    parent, output = a.parent, a.output
    require(parent.is_dir() and parent.name == PARENT_NAME, 'Unexpected parent packet')
    require(sha(parent / 'manifest.json') == PARENT_SHA, 'Parent manifest is not the verified packet12')
    require(not output.exists(), 'Output packet already exists; refuse to overwrite')
    parent_manifest = json.loads((parent / 'manifest.json').read_text())

    # Verify the parent inventory before copying anything.
    for name, digest in parent_manifest['files'].items():
        p = parent / name
        require(p.is_file() and not p.is_symlink() and sha(p) == digest, 'Parent file changed: ' + name)

    staging = output.with_name(output.name + '.staging')
    require(not staging.exists(), 'Stale staging directory')
    shutil.copytree(parent, staging, symlinks=False)

    launcher = staging / LAUNCHER
    text = launcher.read_text()
    needle = "'--reserve-vram', '" + OLD_RESERVE + "'"
    require(text.count(needle) == 1, 'Expected exactly one reserved-VRAM literal')
    launcher_new = text.replace(needle, "'--reserve-vram', '" + NEW_RESERVE + "'", 1)
    ast.parse(launcher_new)

    checker_new = build_checker((staging / CHECKER).read_text())

    prov = staging / PROV
    prov.mkdir(parents=True, exist_ok=False)
    (prov / 'launch').mkdir(exist_ok=False)
    shutil.copyfile(parent / LAUNCHER, prov / LAUNCHER)
    shutil.copyfile(parent / CHECKER, prov / CHECKER)
    shutil.copyfile(parent / 'manifest.json', staging / PARENT_MANIFEST_FILE)
    launcher.write_text(launcher_new)
    (staging / CHECKER).write_text(checker_new)

    files = {}
    for p in sorted(staging.rglob('*')):
        require(not p.is_symlink(), 'Unexpected symlink while inventorying')
        if p.is_file():
            rel = str(p.relative_to(staging))
            if rel in ('manifest.json', 'STATUS.txt'):
                continue
            files[rel] = sha(p)

    added = {PROV + LAUNCHER, PROV + CHECKER, PARENT_MANIFEST_FILE}
    require(set(files) == set(parent_manifest['files']) | added, 'Unexpected packet13 inventory')
    for name, digest in parent_manifest['files'].items():
        if name in (CHECKER, LAUNCHER):
            require(files[PROV + name] == digest, 'Provenance copy differs from parent')
            require(files[name] != digest, 'Changed launch file is unchanged')
        else:
            require(files[name] == digest, 'Inherited file drifted: ' + name)

    manifest = {
        'schema': 'ltx.host-residency-runtime-packet.v1',
        'status': 'prepared-inactive-not-deployed',
        'source_commit': parent_manifest['source_commit'],
        'model_verification_sha256': parent_manifest['model_verification_sha256'],
        'runtime': parent_manifest['runtime'],
        'files': files,
        'extension_sha256s': parent_manifest['extension_sha256s'],
        'startup_tools': {'encoder_runtime_common.py': files[CHECKER],
                          'serve-encoder.py': files[LAUNCHER]},
        'preparer_sha256': sha(Path(__file__)),
        'host_residency': {
            'parent_packet': PARENT_NAME,
            'parent_manifest_sha256': PARENT_SHA,
            'change': 'launcher --reserve-vram 6 -> 2 GiB; checker verify_packet replaced',
            'reserve_vram_gb': 2.0, 'parent_reserve_vram_gb': 6.0,
            'intent': 'let the ~25.1 GB text encoder load fully resident on xpu:2 instead of '
                      'offloading 457-600 MB that are re-copied by blocking pageable transfers each forward',
            'numerical_source_changed': False, 'graphs_changed': False, 'extensions_changed': False,
            'force_full_load': False, 'reserve_override': True,
            'expected_outputs': 'bitwise identical; weight values are unchanged, only their residence',
            'native_gpu_qualified': False, 'full_clip_qualified': False, 'speed_qualified': False,
        },
        'limitations': [
            'Prepared offline only: no native import, endpoint call, device discovery or application action.',
            'A lower reserve is not proof of sufficient headroom; actual residency must be read from the server log.',
            'Bitwise output equality is expected but unproven until the four original raw oracles pass on this packet.',
            'No speed result is promoted by preparation.',
            'The parent packet, its evidence and every earlier packet remain unmodified.',
        ],
    }
    with (staging / 'manifest.json').open('w') as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write('\n')
    (staging / 'STATUS.txt').write_text(
        'PREPARED, INACTIVE text-encoder residency packet. Quality/speed unqualified.\n')
    staging.rename(output)
    digest = sha(output / 'manifest.json')
    print(json.dumps({'status': 'prepared', 'packet': str(output), 'manifest_sha256': digest,
                      'parent_manifest_sha256': PARENT_SHA, 'changed_files': sorted((CHECKER, LAUNCHER)),
                      'inherited_files': len(parent_manifest['files']) - 2,
                      'added_files': sorted(added)}, indent=2))


if __name__ == '__main__':
    main()
