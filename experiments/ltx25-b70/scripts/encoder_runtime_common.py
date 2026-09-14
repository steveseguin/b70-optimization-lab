"""CPU-only source/runtime identity checks shared by encoder launch and clients."""
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import re
import sys

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PIN = '19e1058f4c445ef74047e77a23f9ca7684c1e4b6'
MODEL_VERIFICATION_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
EXTENSIONS = ('resident_node.py', 'ltx_layer_shard.py', 'capture_node.py',
              'encoder_diagnostics.py', 'encoder_identity_node.py')
NODES = {'ltx_speed_lab': 'resident_node.py', 'ltx_baseline_capture': 'capture_node.py',
         'ltx_encoder_diagnostics': 'encoder_diagnostics.py',
         'ltx_encoder_identity': 'encoder_identity_node.py'}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def safe_path(root, name):
    relative = Path(name)
    require(not relative.is_absolute() and relative.parts and '..' not in relative.parts,
            'Unsafe packet-relative path')
    target = Path(root) / relative
    require(not any(p.is_symlink() for p in [target, *target.parents]), 'Symlink in packet path')
    return target


def runtime_fingerprints():
    # Resolve package metadata without importing Torch or enumerating devices.
    origin = Path(importlib.util.find_spec('torch').origin)
    files = [origin, origin.parent / '_inductor/config.py', Path(sys.executable).resolve()]
    return {'torch': importlib.metadata.version('torch'), 'python': platform.python_version(),
            'python_executable': str(Path(sys.executable).absolute()),
            'files': {str(p): sha(p) for p in files}}


def verify_runtime(expected):
    actual = runtime_fingerprints()
    require(actual == expected, 'Runtime files/version differ from prepared packet')
    require(actual['torch'] == '2.14.0+xpu' and actual['python'] == '3.12.13',
            'Unexpected baseline Python/Torch version')
    return actual


def verify_packet(packet, expected_manifest_sha256):
    packet = Path(packet)
    require(packet.is_absolute() and packet.parent == ROOT and
            re.fullmatch(r'prepared-encoder-[a-z0-9-]+', packet.name), 'Unexpected packet path')
    manifest_path = safe_path(packet, 'manifest.json')
    require(re.fullmatch(r'[0-9a-f]{64}', expected_manifest_sha256) is not None,
            'Explicit manifest SHA256 required')
    require(sha(manifest_path) == expected_manifest_sha256, 'Packet manifest changed')
    manifest = json.loads(manifest_path.read_text())
    require(manifest['schema'] == 'ltx.encoder-runtime-packet.v2', 'Launcher requires v2 packet')
    require(manifest['source_commit'] == PIN, 'Core revision changed')
    require(manifest['model_verification_sha256'] == MODEL_VERIFICATION_SHA256,
            'Model identity changed')
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
    return manifest


def verify_model_receipt():
    receipt = ROOT / 'model-verification.json'
    require(sha(receipt) == MODEL_VERIFICATION_SHA256, 'Model verification receipt changed')
    require(json.loads(receipt.read_text())['status'] == 'passed', 'Model gate not passed')
    require(not (ROOT / 'FAULT.json').exists(), 'Fault recorded; halt new work')


def process_ticks(pid):
    return Path(f'/proc/{pid}/stat').read_text().split(') ')[1].split()[19]
