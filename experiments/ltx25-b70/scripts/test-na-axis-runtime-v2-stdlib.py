#!/usr/bin/env python3
"""Offline source closure regressions; no native imports, packet seal or endpoint."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('na_axis_builder_v2', LANE / 'scripts/prepare-na-axis-runtime-v2.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def main():
    checks = []
    def check(name, condition):
        builder.require(condition, name)
        checks.append(name)
    def rejects(name, action, expected):
        try:
            action()
        except RuntimeError as error:
            check(name, expected in str(error))
            return
        raise AssertionError('Expected rejection: ' + name)

    original = builder.FAILED_PACKET / 'source'
    rejects('packet09-reproduces-sd-startup-mismatch-offline',
        lambda: builder.verify_na_source_closure(original), 'SD_SHA: declared=3eba634a')
    corrected = LANE / 'scripts/na_axis_decode_node_v2.py'
    result = builder.verify_na_source_closure(original, node_path=corrected)
    check('corrected-node-closes-all-seven-startup-hash-edges', len(result['dependencies']) == 7)
    check('source-closure-does-not-claim-native-registration', result['startup_registration_qualified'] is False)
    generated = builder.checker_source((builder.PARENT / builder.CHECKER).read_text())
    tree = ast.parse(generated)
    names = {'literal_source_pins', 'verify_na_source_closure'}
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    ns = {'ast': ast, 'Path': Path, 're': builder.re, 'sha': builder.sha, 'require': builder.require}
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<generated-checker-source-closure>', 'exec'), ns)
    check('generated-checker-closure-matches-builder',
        ns['verify_na_source_closure'](original, node_path=corrected) == result)
    rejects('generated-checker-rejects-original09-node',
        lambda: ns['verify_na_source_closure'](original), 'SD_SHA: declared=3eba634a')
    verifier = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'verify_packet')
    calls = [n for n in ast.walk(verifier) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'verify_na_source_closure']
    check('packet-verifier-executes-closure-on-actual-packet-source', len(calls) == 1 and
        ast.unparse(calls[0]) == "verify_na_source_closure(safe_path(packet, 'source'))")

    with tempfile.TemporaryDirectory(prefix='ltx-na-axis-source-closure-') as temp:
        source = Path(temp) / 'source'
        paths = ['nodes.py', 'comfy/sd.py', 'comfy/ldm/lightricks/vae/na_diffusion_decoder.py',
                 'scripts/ltx_na_axis_router.py', 'scripts/ltx_na_axis_candidate.py']
        for name in paths:
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original / name, target)
        node = source / 'scripts/na_axis_decode_node.py'
        shutil.copyfile(corrected, node)
        native = Path(temp) / 'original-na.py'
        shutil.copyfile(builder.KITCHEN / 'backends/eager/na.py', native)
        closure = lambda: builder.verify_na_source_closure(source, original_na_path=native)
        check('isolated-complete-source-closure-passes', closure() == result)
        for pin, name in zip(('NODES_SHA', 'SD_SHA', 'DECODER_SHA', 'ROUTER_SHA', 'CANDIDATE_SHA'), paths):
            path = source / name
            content = path.read_bytes()
            path.write_bytes(content + b'\n# simulated dependency drift\n')
            rejects('changed-dependency-rejected-' + pin, closure, pin + ': declared=')
            path.write_bytes(content)
        content = native.read_bytes()
        native.write_bytes(content + b'\n# simulated installed dependency drift\n')
        rejects('changed-router-original-dependency-rejected', closure, 'router.ORIGINAL_SHA: declared=')
        native.write_bytes(content)
        node_content = node.read_text()
        for label, changed in (
            ('duplicate', node_content + "\nSD_SHA = '" + '0' * 64 + "'\n"),
            ('missing', '\n'.join(line for line in node_content.splitlines() if not line.startswith('SD_SHA = '))),
            ('nonliteral', node_content.replace("SD_SHA = '41cbf195657cc81a60173f13f192966c4276bf7931a6c10f75870a66c59546b0'", "SD_SHA = str('" + '0' * 64 + "')")),
            ('conditional-write', node_content + "\nif False:\n    SD_SHA = '" + '0' * 64 + "'\n"),
        ):
            node.write_text(changed)
            rejects('malformed-pin-rejected-' + label, closure, 'startup pin: SD_SHA')
        node.write_text(node_content)
        check('restored-source-closure-passes', closure() == result)

    check('no-native-modules-imported', not any(name == 'torch' or name.startswith(('torch.', 'comfy.', 'comfy_kitchen'))
                                               for name in sys.modules))
    print(json.dumps({'status': 'passed-stdlib-source-closure', 'checks': checks, 'native_imports': False,
        'native_requests': 0, 'packet_sealed': False, 'builder_sha256': builder.sha(builder.__file__),
        'test_sha256': builder.sha(__file__), 'node_sha256': builder.sha(corrected),
        'closure': result}, indent=2))


if __name__ == '__main__':
    main()
