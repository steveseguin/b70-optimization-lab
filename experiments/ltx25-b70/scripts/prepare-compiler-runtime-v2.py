#!/usr/bin/env python3
"""Build an offline compiler successor with host-fault detection.

A current fault blocks runtime admission, not copying and checking source.
The model receipt still must have its exact known passed identity.

No Torch imports, process operations, GPU requests, or edits to previous packets.
The one-block candidate is explicit in separate graph templates; existing encoder
control/candidate graphs remain byte-identical. The copied strict launcher only
adds bounded compiler worker/cache environment and records it in server identity.
"""
import argparse
import ast
import copy
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PARENT = ROOT / 'prepared-encoder-03'
PARENT_SHA256 = 'd391ac4236e7ea683af1e1cdae5a4f020e608e20c4ff849d9fe958b524d028e7'
EFFECTIVE_ADAPTER_SHA256 = '79ba260785e16d7e646bfe79b0816e99a8fab6db557a60408c35bd7675121577'
PATCHES = ('ltx-block-compile-ownership-guard.patch',
           'ltx-block-compile-pre-run-lifecycle-v2.patch')
EXTRA_HELPERS = ('ltx_block_compile.py', 'block_compile_node.py')
HOST_FAULT_PATCH = 'encoder-kernel-host-fault-detector.patch'
COMPILER_SCHEMA = 'ltx.compiler-runtime-packet.v1'


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inventory(root, common):
    result = {}
    for path in sorted(root.rglob('*')):
        common.require(not path.is_symlink(), 'Packet symlink refused')
        if path.is_file():
            result[str(path.relative_to(root))] = common.sha(path)
    return result


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError('Parent checker context changed: ' + old)
    return source.replace(old, new, 1)


def compiler_checker(parent_text):
    """Minimal explicit local allowlist/schema delta, retaining all original gates."""
    text = replace_once(parent_text,
        "'encoder_diagnostics.py', 'encoder_identity_node.py')",
        "'encoder_diagnostics.py', 'encoder_identity_node.py',\n              'ltx_block_compile.py', 'block_compile_node.py')")
    text = replace_once(text,
        "'ltx_encoder_identity': 'encoder_identity_node.py'}",
        "'ltx_encoder_identity': 'encoder_identity_node.py',\n         'ltx_block_compile_lab': 'block_compile_node.py'}")
    text = replace_once(text,
        "manifest['schema'] == 'ltx.encoder-runtime-packet.v2', 'Launcher requires v2 packet'",
        "manifest['schema'] == 'ltx.compiler-runtime-packet.v1', 'Launcher requires compiler packet'")
    checks = '''    # This successor adds a dormant node; inherited numerical code and all
    # original graphs are pinned to the audited immutable encoder-03 parent.
    require(manifest['parent_manifest_sha256'] ==
            'd391ac4236e7ea683af1e1cdae5a4f020e608e20c4ff849d9fe958b524d028e7',
            'Unexpected encoder parent')
    parent_path = safe_path(packet, 'encoder-parent-manifest.json')
    require(sha(parent_path) == manifest['parent_manifest_sha256'], 'Parent manifest changed')
    parent = json.loads(parent_path.read_text())
    require(parent['schema'] == 'ltx.encoder-runtime-packet.v2', 'Unexpected parent schema')
    require(manifest['runtime'] == parent['runtime'], 'Compiler runtime differs from parent')
    require(manifest['files']['provenance/serve-encoder.parent.py'] ==
            parent['startup_tools']['serve-encoder.py'], 'Original strict launcher provenance changed')
    for name, digest in parent['files'].items():
        if name in ('launch/encoder_runtime_common.py', 'launch/serve-encoder.py'):
            original_name = 'encoder_runtime_common.parent.py' if name.endswith('encoder_runtime_common.py') else 'serve-encoder.parent.py'
            require(manifest['files']['provenance/' + original_name] == digest,
                    'Original startup provenance changed')
        else:
            require(manifest['files'].get(name) == digest, 'Inherited file changed: ' + name)
    require(manifest['compiler']['effective_adapter_sha256'] ==
            '79ba260785e16d7e646bfe79b0816e99a8fab6db557a60408c35bd7675121577',
            'Compiler adapter differs from reviewed effective patch')
    require(manifest['extension_sha256s']['ltx_block_compile.py'] ==
            manifest['compiler']['effective_adapter_sha256'], 'Adapter inventory mismatch')
    require(manifest['compiler']['encoder_variant'] == 'control' and
            manifest['compiler']['block_index'] == 24, 'Bounded compiler scope changed')
    expected = json.loads(safe_path(packet, 'graphs/control.json').read_text())
    for mode in ('eager', 'compiled', 'restored'):
        graph = json.loads(safe_path(packet, 'graphs/compiler-' + mode + '.json').read_text())
        require(graph.pop('422') == {'class_type': 'LTXCompileOneBlockGate', 'inputs': {
                'model': ['420', 0], 'mode': mode, 'block_index': 24,
                'run_name': 'assign-unique-request-name'}}, 'Compiler graph node changed')
        for node in ('388', '391'):
            require(graph[node]['inputs']['model'] == ['422', 0], 'Compiler graph edge changed')
            graph[node]['inputs']['model'] = ['420', 0]
        require(graph == expected, 'Compiler graph changed original quality recipe')
'''
    return replace_once(text, '    return manifest\n', checks + '    return manifest\n')



def compiler_launcher(parent_text):
    text = replace_once(parent_text,
        '    sys.dont_write_bytecode = True\n    threading.Thread(target=watch_journal, daemon=True).start()',
        "    # Compiler-only successor: one worker and caches outside immutable source.\n"
        "    compiler_environment = {'TORCHINDUCTOR_COMPILE_THREADS': '1',\n"
        "                            'TORCHINDUCTOR_CACHE_DIR': str(run / 'inductor-cache'),\n"
        "                            'TRITON_CACHE_DIR': str(run / 'triton-cache')}\n"
        "    os.environ.update(compiler_environment)\n"
        "    sys.dont_write_bytecode = True\n"
        "    threading.Thread(target=watch_journal, daemon=True).start()")
    return replace_once(text,
        "                'encoder_run_dir': str(run), 'extension_sha256s': manifest['extension_sha256s'],",
        "                'encoder_run_dir': str(run), 'extension_sha256s': manifest['extension_sha256s'],\n"
        "                'compiler_environment': compiler_environment,")



def verify_model_receipt_offline(common):
    """Verify immutable model provenance without granting runtime admission."""
    receipt = common.safe_path(ROOT, 'model-verification.json')
    common.require(common.sha(receipt) == common.MODEL_VERIFICATION_SHA256,
                   'Offline model verification receipt changed')
    common.require(json.loads(receipt.read_text())['status'] == 'passed',
                   'Offline model gate not passed')
    # Do not call common.verify_model_receipt here: it also checks the live
    # fault latch. Launchers and clients retain that runtime admission function.
    fault = ROOT / 'FAULT.json'
    return {'model_verification_sha256': common.sha(receipt),
            'fault_latch_present_at_preparation': fault.exists(),
            'fault_latch_sha256_at_preparation': common.sha(fault) if fault.exists() else None,
            'runtime_admission': 'not attempted; fault latch still blocks runtime'}


def prepare(output):
    common = load_module(PARENT / 'launch/encoder_runtime_common.py', 'compiler_parent_common')
    common.require(output.is_absolute() and output.parent == ROOT and
                   re.fullmatch(r'prepared-encoder-compiler-[a-z0-9-]+', output.name),
                   'Use a new prepared-encoder-compiler-* packet in the evidence root')
    common.safe_path(ROOT, output.name)
    common.require(not output.exists(), 'Packet already exists; never overwrite or repair in place')
    parent = common.verify_packet(PARENT, PARENT_SHA256)
    common.verify_runtime(parent['runtime'])
    offline_receipt = verify_model_receipt_offline(common)
    common.require(shutil.disk_usage(ROOT).free >= 5 * 1024**3, 'Less than 5 GiB disk free')
    inputs = [LANE / 'scripts' / name for name in EXTRA_HELPERS]
    inputs += [LANE / 'patches' / name for name in (*PATCHES, HOST_FAULT_PATCH)]
    inputs.append(LANE / 'scripts/kernel_fault_detector.py')
    for path in inputs:
        common.require(path.is_file() and not path.is_symlink(), 'Missing compiler input: ' + str(path))
        if path.suffix == '.py':
            ast.parse(path.read_text(), filename=str(path))
    input_hashes = {str(path.relative_to(LANE)): common.sha(path) for path in inputs}
    checker_text = compiler_checker((PARENT / 'launch/encoder_runtime_common.py').read_text())
    ast.parse(checker_text, filename='encoder_runtime_common.py')
    launcher_text = compiler_launcher((PARENT / 'launch/serve-encoder.py').read_text())
    ast.parse(launcher_text, filename='serve-encoder.py')
    output.mkdir()
    (output / 'STATUS.txt').write_text('INCOMPLETE compiler packet; do not launch.\n')
    # Copy only parent-inventoried regular files; never follow links or carry
    # transient runtime caches, and never use hard links to immutable evidence.
    for name in parent['files']:
        source = common.safe_path(PARENT, name)
        target = common.safe_path(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(PARENT / 'manifest.json', output / 'encoder-parent-manifest.json')
    provenance = output / 'provenance'
    provenance.mkdir()
    shutil.copyfile(PARENT / 'launch/encoder_runtime_common.py',
                    provenance / 'encoder_runtime_common.parent.py')
    shutil.copyfile(PARENT / 'launch/serve-encoder.py', provenance / 'serve-encoder.parent.py')
    shutil.copyfile(LANE / 'scripts/ltx_block_compile.py',
                    provenance / 'ltx_block_compile.unpatched.py')
    shutil.copyfile(Path(__file__), provenance / Path(__file__).name)
    shutil.copyfile(LANE / 'scripts/kernel_fault_detector.py', provenance / 'kernel_fault_detector.py')
    shutil.copyfile(LANE / 'scripts/ltx_block_compile.py', output / 'source/scripts/ltx_block_compile.py')
    for name in PATCHES:
        target = output / 'patches' / name
        shutil.copyfile(LANE / 'patches' / name, target)
        subprocess.run(['git', 'apply', '--check', str(target)], cwd=output / 'source', check=True, timeout=30)
        subprocess.run(['git', 'apply', str(target)], cwd=output / 'source', check=True, timeout=30)
    adapter = output / 'source/scripts/ltx_block_compile.py'
    common.require(common.sha(adapter) == EFFECTIVE_ADAPTER_SHA256, 'Effective adapter hash differs')
    ast.parse(adapter.read_text(), filename=str(adapter))
    shutil.copyfile(LANE / 'scripts/block_compile_node.py', output / 'source/scripts/block_compile_node.py')
    node = output / 'source/custom_nodes/ltx_block_compile_lab'
    node.mkdir()
    shutil.copyfile(output / 'source/scripts/block_compile_node.py', node / '__init__.py')
    (output / 'launch/encoder_runtime_common.py').write_text(checker_text)
    (output / 'launch/serve-encoder.py').write_text(launcher_text)
    host_patch = output / 'patches' / HOST_FAULT_PATCH
    shutil.copyfile(LANE / 'patches' / HOST_FAULT_PATCH, host_patch)
    subprocess.run(['git', 'apply', '--check', str(host_patch)], cwd=output, check=True, timeout=30)
    subprocess.run(['git', 'apply', str(host_patch)], cwd=output, check=True, timeout=30)
    ast.parse((output / 'launch/serve-encoder.py').read_text(), filename='serve-encoder.py')
    control = json.loads((output / 'graphs/control.json').read_text())
    common.require(control['420']['inputs']['encoder_variant'] == 'control', 'Control graph variant changed')
    for mode in ('eager', 'compiled', 'restored'):
        graph = copy.deepcopy(control)
        common.require('422' not in graph, 'Compiler node ID is occupied')
        graph['422'] = {'class_type': 'LTXCompileOneBlockGate', 'inputs': {
            'model': ['420', 0], 'mode': mode, 'block_index': 24,
            'run_name': 'assign-unique-request-name'}}
        for key in ('388', '391'):
            common.require(graph[key]['inputs']['model'] == ['420', 0], 'Model edge changed')
            graph[key]['inputs']['model'] = ['422', 0]
        (output / 'graphs' / ('compiler-' + mode + '.json')).write_text(json.dumps(graph, indent=2) + '\n')
    # Revalidate parent and all mutable repository inputs before sealing.
    common.verify_packet(PARENT, PARENT_SHA256)
    common.require(all(common.sha(LANE / name) == digest for name, digest in input_hashes.items()),
                   'Compiler inputs changed during preparation')
    local = load_module(output / 'launch/encoder_runtime_common.py', 'compiler_packet_common')
    manifest = {**parent,
        'schema': COMPILER_SCHEMA,
        'parent_packet': str(PARENT), 'parent_manifest_sha256': PARENT_SHA256,
        'compiler_preparer_sha256': common.sha(Path(__file__)),
        'offline_preparation': offline_receipt,
        'host_fault_detection': {'patch': HOST_FAULT_PATCH,
                                 'scope': 'Legacy GPU signatures plus soft lockups, RCU stalls/starvation, and hung tasks; no recovery actions.'},
        'startup_tools': {name: common.sha(output / 'launch' / name)
                          for name in ('serve-encoder.py', 'encoder_runtime_common.py')},
        'extension_sha256s': {name: common.sha(output / 'source/scripts' / name) for name in local.EXTENSIONS},
        'patch_order': parent['patch_order'] + [*PATCHES, HOST_FAULT_PATCH],
        'patch_sha256s': {**parent['patch_sha256s'], **{name: common.sha(output / 'patches' / name) for name in (*PATCHES, HOST_FAULT_PATCH)}},
        'compiler': {'default': 'dormant; existing encoder graphs do not call the compiler node',
                     'encoder_variant': 'control', 'block_index': 24,
                     'effective_adapter_sha256': EFFECTIVE_ADAPTER_SHA256,
                     'input_sha256s': input_hashes,
                     'node': 'LTXCompileOneBlockGate',
                     'modes': ['eager', 'compiled', 'restored'],
                     'launcher_delta': 'Set compile worker count1 and cache paths under new server run before Torch import; bind environment in server identity. Strict import fix and arguments unchanged.',
                     'quality': 'Native BF16, unchanged sampler, 8+3 steps, 25 frames, 256x256 output at24fps; candidate needs native exact parity.',
                     'graph_delta': 'Add422 after420 and route both guider model inputs through422; all other nodes unchanged.'},
        'limitations': [
            'Prepared inactive; builder does not launch, stop, restart or contact any server.',
            'Original launcher archived byte-for-byte; copied launcher adds compiler environment and host-kernel fault signatures. Four original encoder graphs unchanged.',
            'Compiler enabled only by explicit compiled graph mode; one native block24 only.',
            'Offline preparation does not grant runtime admission; existing FAULT blocks launcher, client and node execution.',
            'Host-kernel fault detection is an earlier halt mechanism, not a fix for the kernel incident.',
            'Compiler exact parity, determinism, lifecycle restoration and native timing remain unqualified.',
            'Requires unique request names in capture, preview, encoder placement and compiler gate nodes.',
            'Compiler graphs use control encoder to isolate the compiler delta.',
            'Do not use existing encoder-only clients: compiler packet schema and node422 need a dedicated bound client.',
        ]}
    manifest['files'] = inventory(output, common)
    manifest['files'].pop('STATUS.txt')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'STATUS.txt').write_text('PREPARED, INACTIVE compiler successor. Exact native gates pending.\n')
    digest = common.sha(output / 'manifest.json')
    local.verify_packet(output, digest)
    local.verify_runtime(manifest['runtime'])
    return {'packet': str(output), 'manifest_sha256': digest, 'files': len(manifest['files']),
            'status': 'prepared-inactive-not-deployed', 'parent_manifest_sha256': PARENT_SHA256,
            'effective_adapter_sha256': EFFECTIVE_ADAPTER_SHA256}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
