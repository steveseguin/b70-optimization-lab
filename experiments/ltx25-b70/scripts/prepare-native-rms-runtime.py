#!/usr/bin/env python3
"""Build an inactive, separately pinned native-RMS compiler packet; no runtime actions."""
import argparse
import ast
import copy
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PARENT = ROOT / 'prepared-encoder-compiler-03'
PARENT_SHA = '9ecd5f9863289e00a934c1f4f400582092f37d0ee92035512fc095773ad02980'
PARENT_CHECKER_SHA = 'e2739c7a6223f278eabd587ec7ebb8f08d10158303b950b13b0011435e1b3f72'
PARENT_ADAPTER_SHA = '79ba260785e16d7e646bfe79b0816e99a8fab6db557a60408c35bd7675121577'
PARENT_NODE_SHA = 'ba98268c89f52477d4641a15b2f8ea9e73f68cdd5fc683700ee50d98f706280e'
BACKEND_SHA = '09defae7340dc3d7f33e16ab80c76f22b6a2ae733617704f2e7b69086108d9fb'
BACKEND = 'ltx_native_rms_backend.py'
SCHEMA = 'ltx.compiler-native-rms-runtime-packet.v1'
MODIFIED = ('launch/encoder_runtime_common.py', 'source/scripts/ltx_block_compile.py',
            'source/scripts/block_compile_node.py',
            'source/custom_nodes/ltx_block_compile_lab/__init__.py')
OLD_COMPILE = "self.compiled = compiler(block, backend='inductor', fullgraph=True, dynamic=False,\n                                 options=dict(OPTIONS))"
NEW_COMPILE = "self.compiled = compiler(block, backend=make_backend(\n            OPTIONS, Path(os.environ['LTX_ENCODER_RUN_DIR']) / 'native-rms-graphs',\n            expected_count=15), fullgraph=True, dynamic=False)"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def replace_once(text, old, new):
    require(text.count(old) == 1, 'Pinned source context changed: ' + old)
    return text.replace(old, new, 1)


def load_checker(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def adapter_source(original):
    text = replace_once(original, 'import hashlib\n', 'import hashlib\nimport os\n')
    text = replace_once(text, 'import torch\n', 'import torch\nfrom ltx_native_rms_backend import make_backend\n')
    return replace_once(text, OLD_COMPILE, NEW_COMPILE)


def verify_adapter_delta(original, candidate):
    """Reverse precisely the two imports and one assignment, then compare whole AST."""
    reverse = replace_once(candidate, 'import hashlib\nimport os\n', 'import hashlib\n')
    reverse = replace_once(reverse, 'import torch\nfrom ltx_native_rms_backend import make_backend\n', 'import torch\n')
    reverse = replace_once(reverse, NEW_COMPILE, OLD_COMPILE)
    require(ast.dump(ast.parse(reverse)) == ast.dump(ast.parse(original)),
            'Adapter changed beyond the declared compiler backend boundary')
    tree = ast.parse(candidate)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'CompiledBlockRoute')
    init = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '__init__')
    calls = [node for node in ast.walk(init) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == 'compiler']
    require(len(calls) == 1 and [keyword.arg for keyword in calls[0].keywords] == ['backend', 'fullgraph', 'dynamic'],
            'Unexpected outer compile options or invocation')
    return {'whole_adapter_ast_only_imports_and_backend_changed': True,
            'outer_compile_options_removed': True, 'fullgraph': True, 'dynamic': False,
            'expected_native_rms_count_per_graph': 15, 'original_options_retained': True}


def checker_source(original, adapter_sha):
    text = replace_once(original, "'ltx_block_compile.py', 'block_compile_node.py')",
                        "'ltx_block_compile.py', 'block_compile_node.py',\n              'ltx_native_rms_backend.py')")
    text = replace_once(text, "manifest['schema'] == 'ltx.compiler-runtime-packet.v1'",
                        f"manifest['schema'] == '{SCHEMA}'")
    # Keep the original encoder-parent gates, with their original archived file.
    require(text.count("manifest['parent_manifest_sha256']") == 2, 'Unexpected encoder lineage references')
    text = text.replace("manifest['parent_manifest_sha256']", "manifest['encoder_parent_manifest_sha256']")
    text = replace_once(text, repr(PARENT_ADAPTER_SHA), repr(adapter_sha))
    checks = f'''    # Native-RMS successor: pin the complete immediate compiler parent and
    # allow only backend selection plus the checker/node source identity pins.
    require(manifest['parent_manifest_sha256'] == {PARENT_SHA!r}, 'Unexpected compiler parent')
    compiler_parent_path = safe_path(packet, 'compiler-parent-manifest.json')
    require(sha(compiler_parent_path) == {PARENT_SHA!r}, 'Compiler parent manifest changed')
    compiler_parent = json.loads(compiler_parent_path.read_text())
    require(compiler_parent['schema'] == 'ltx.compiler-runtime-packet.v1', 'Unexpected compiler parent schema')
    require(manifest['runtime'] == compiler_parent['runtime'], 'Native RMS runtime changed')
    changed = {MODIFIED!r}
    for name, digest in compiler_parent['files'].items():
        if name in changed:
            require(manifest['files']['provenance/native-rms-parent/' + name] == digest,
                    'Original compiler parent source changed: ' + name)
        else:
            require(manifest['files'].get(name) == digest, 'Inherited compiler source changed: ' + name)
    require(manifest['native_rms']['backend_sha256'] == {BACKEND_SHA!r}
            and manifest['extension_sha256s']['ltx_native_rms_backend.py'] == {BACKEND_SHA!r},
            'Native RMS backend source changed')
    require(manifest['native_rms']['expected_count'] == 15
            and manifest['native_rms']['effective_adapter_sha256'] == {adapter_sha!r},
            'Native RMS intervention changed')
'''
    return replace_once(text, '    return manifest\n', checks + '    return manifest\n')


def inventory(root):
    files = {}
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), 'Packet symlink refused')
        if path.is_file():
            files[str(path.relative_to(root))] = sha(path)
    return files


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def prepare(output):
    require(output.is_absolute() and output.parent == ROOT
            and re.fullmatch(r'prepared-encoder-compiler-[a-z0-9-]+', output.name), 'Use a new compiler packet path')
    require(not output.exists() and not output.is_symlink(), 'Packet already exists; never overwrite')
    require(sha(PARENT / 'manifest.json') == PARENT_SHA, 'Parent manifest changed')
    require(sha(PARENT / 'launch/encoder_runtime_common.py') == PARENT_CHECKER_SHA, 'Parent checker changed')
    backend = LANE / 'scripts' / BACKEND
    require(not backend.is_symlink() and sha(backend) == BACKEND_SHA, 'Reviewed backend input changed')
    backend_text = backend.read_text()
    ast.parse(backend_text)
    builder_sha = sha(Path(__file__))
    common = load_checker(PARENT / 'launch/encoder_runtime_common.py', 'native_rms_parent_checker')
    common.safe_path(ROOT, output.name)
    parent = common.verify_packet(PARENT, PARENT_SHA)
    common.verify_runtime(parent['runtime'])
    model = common.safe_path(ROOT, 'model-verification.json')
    require(sha(model) == common.MODEL_VERIFICATION_SHA256
            and json.loads(model.read_text())['status'] == 'passed', 'Model provenance changed')
    require(shutil.disk_usage(ROOT).free >= 5 * 1024**3, 'Less than 5 GiB disk free')
    original_adapter = (PARENT / 'source/scripts/ltx_block_compile.py').read_text()
    original_node = (PARENT / 'source/scripts/block_compile_node.py').read_text()
    require(text_sha(original_adapter) == PARENT_ADAPTER_SHA and text_sha(original_node) == PARENT_NODE_SHA,
            'Original compiler source pins changed')
    candidate_adapter = adapter_source(original_adapter)
    adapter_sha = text_sha(candidate_adapter)
    checks = verify_adapter_delta(original_adapter, candidate_adapter)
    candidate_node = replace_once(original_node, f'ADAPTER_SHA256 = {PARENT_ADAPTER_SHA!r}',
                                  f'ADAPTER_SHA256 = {adapter_sha!r}')
    require(ast.dump(ast.parse(candidate_node.replace(adapter_sha, PARENT_ADAPTER_SHA)))
            == ast.dump(ast.parse(original_node)), 'Compiler node changes exceed its adapter hash pin')
    checker = checker_source((PARENT / 'launch/encoder_runtime_common.py').read_text(), adapter_sha)
    ast.parse(checker)
    output.mkdir()
    (output / 'STATUS.txt').write_text('INCOMPLETE native RMS packet; do not launch.\n')
    for name in parent['files']:
        source, target = common.safe_path(PARENT, name), common.safe_path(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(PARENT / 'manifest.json', output / 'compiler-parent-manifest.json')
    for name in MODIFIED:
        target = output / 'provenance/native-rms-parent' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PARENT / name, target)
    shutil.copyfile(Path(__file__), output / 'provenance' / Path(__file__).name)
    (output / 'source/scripts' / BACKEND).write_text(backend_text)
    replacements = {'launch/encoder_runtime_common.py': checker,
                    'source/scripts/ltx_block_compile.py': candidate_adapter,
                    'source/scripts/block_compile_node.py': candidate_node,
                    'source/custom_nodes/ltx_block_compile_lab/__init__.py': candidate_node}
    delta = []
    for name, content in replacements.items():
        original = (PARENT / name).read_text()
        (output / name).write_text(content)
        delta.extend(difflib.unified_diff(original.splitlines(keepends=True), content.splitlines(keepends=True),
                                         fromfile='a/' + name, tofile='b/' + name))
    patch_name = 'native-rms-backend-runtime.patch'
    (output / 'patches' / patch_name).write_text(''.join(delta))
    # Verify every inherited byte and every mutable input before sealing.
    common.verify_packet(PARENT, PARENT_SHA)
    require(sha(backend) == BACKEND_SHA and sha(Path(__file__)) == builder_sha, 'Preparation inputs changed')
    files = inventory(output)
    changed = {name for name, digest in parent['files'].items() if files[name] != digest}
    require(changed == set(MODIFIED), 'Unexpected inherited source changes')
    require(files['launch/serve-encoder.py'] == parent['files']['launch/serve-encoder.py'], 'Launcher changed')
    local = load_checker(output / 'launch/encoder_runtime_common.py', 'native_rms_packet_checker')
    checks.update({'changed_parent_files': sorted(changed),
                   'launcher_server_flags_unchanged': True, 'all_graphs_and_model_sources_unchanged': True,
                   'node_change_only_adapter_sha256': True, 'backend_input_sha256': BACKEND_SHA,
                   'native_imported_or_executed': False, 'runtime_admission_attempted': False})
    write_json(output / 'provenance/native-rms-source-checks.json', checks)
    manifest = copy.deepcopy(parent)
    manifest.update(schema=SCHEMA, parent_packet=str(PARENT), parent_manifest_sha256=PARENT_SHA,
                    encoder_parent_manifest_sha256=parent['parent_manifest_sha256'],
                    native_rms_preparer_sha256=builder_sha,
                    offline_preparation={'model_verification_sha256': common.MODEL_VERIFICATION_SHA256,
                        'fault_latch_present_at_preparation': (ROOT / 'FAULT.json').exists(),
                        'runtime_admission': 'not attempted; source preparation only'},
                    startup_tools={name: sha(output / 'launch' / name) for name in parent['startup_tools']},
                    extension_sha256s={name: sha(output / 'source/scripts' / name) for name in local.EXTENSIONS})
    manifest['compiler']['effective_adapter_sha256'] = adapter_sha
    manifest['native_rms'] = {'backend_sha256': BACKEND_SHA, 'expected_count': 15,
        'effective_adapter_sha256': adapter_sha, 'parent_adapter_sha256': PARENT_ADAPTER_SHA,
        'scope': 'One native block24; FX RMS targets become opaque native RMS operations before Inductor',
        'options': 'Original OPTIONS bound at make_backend; outer fullgraph=True, dynamic=False',
        'receipt_directory': "Path(os.environ['LTX_ENCODER_RUN_DIR']) / 'native-rms-graphs'",
        'changes': 'Backend selection, necessary imports, source identity pins only; no decoder or loader changes',
        'native_block_xpu_qualified': False, 'full_clip_qualified': False, 'speed_qualified': False}
    manifest['patch_order'].append(patch_name)
    manifest['patch_sha256s'][patch_name] = sha(output / 'patches' / patch_name)
    manifest['limitations'].extend([
        'Native RMS is a distinct compiler candidate; CPU source/operator tests do not qualify native XPU block or full-clip outputs.',
        'Requires a separately pinned campaign client accepting the new adapter identity and checking RMS graph receipts.',
        'Decoder NA extent and loader-memory candidates are not included; packet03 and the active server are untouched.'])
    manifest['files'] = inventory(output)
    manifest['files'].pop('STATUS.txt')
    write_json(output / 'manifest.json', manifest)
    digest = sha(output / 'manifest.json')
    local.verify_packet(output, digest)
    local.verify_runtime(manifest['runtime'])
    (output / 'STATUS.txt').write_text('PREPARED, INACTIVE native RMS successor. Native XPU/full-clip gates pending.\n')
    return {'status': 'prepared-inactive-not-deployed', 'packet': str(output), 'manifest_sha256': digest,
            'parent_manifest_sha256': PARENT_SHA, 'backend_sha256': BACKEND_SHA,
            'effective_adapter_sha256': adapter_sha, 'files': len(manifest['files']), 'source_checks': checks}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
