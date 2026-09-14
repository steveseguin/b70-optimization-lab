#!/usr/bin/env python3
"""Exercise real node initialize against sealed file paths, with stdlib module stubs.

No Torch/Comfy imports, endpoint access, router installation or GPU work. The
stub install only records ordering; actual routing remains separately tested.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
from unittest.mock import patch

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-na-axis-09')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    spec = importlib.util.spec_from_file_location('startup_node_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise(path, expect_error=None, bad_module=None, bad_context=False, bad_identity=False):
    events = []
    with tempfile.TemporaryDirectory(prefix='ltx-node-startup-') as temporary:
        run = Path(temporary) / 'encoder-server-startup-test'
        run.mkdir()
        identity_path = run / 'server-identity.json'
        identity_path.write_text('{"test": "stdlib-only"}\n')
        identity = {'server_identity_sha256': sha(identity_path),
                    'model_verification_sha256': 'b' * 64}
        fake = {}
        for name, relative in (
            ('ltx_na_axis_router', 'scripts/ltx_na_axis_router.py'),
            ('nodes', 'nodes.py'), ('comfy.sd', 'comfy/sd.py'),
            ('comfy.ldm.lightricks.vae.na_diffusion_decoder', 'comfy/ldm/lightricks/vae/na_diffusion_decoder.py'),
        ):
            module = types.ModuleType(name)
            module.__file__ = str(PACKET / 'source' / relative)
            if name == bad_module:
                wrong = Path(temporary) / 'wrong-source.py'
                wrong.write_text('# changed source\n')
                module.__file__ = str(wrong)
            fake[name] = module
        tree = ast.parse((PACKET / 'source/nodes.py').read_text())
        original_ast = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'VAEDecode')
        namespace = {}
        exec(compile(ast.Module(body=[original_ast], type_ignores=[]), '<original-VAEDecode>', 'exec'), namespace)
        fake['nodes'].VAEDecode = namespace['VAEDecode']
        fake['ltx_na_axis_router'].ORIGINAL_SHA = '4f1d82fe02af995d395969667f6cfd8d10635c3144eec8ca78fe37c103803995'

        def install(candidate):
            events.append('install')
            assert candidate == PACKET / 'source/scripts/ltx_na_axis_candidate.py'
            return object()

        fake['ltx_na_axis_router'].install = install
        diagnostics = types.ModuleType('encoder_diagnostics')

        def context():
            events.append('context')
            result = dict(identity)
            if bad_context:
                result['server_identity_sha256'] = 'c' * 64
            return run, result

        diagnostics._context = context
        fake['encoder_diagnostics'] = diagnostics
        environment = {'LTX_ENCODER_RUN_DIR': str(run),
                       'LTX_ENCODER_IDENTITY_SHA256': 'd' * 64 if bad_identity else identity['server_identity_sha256']}
        with patch.dict(sys.modules, fake), patch.dict(os.environ, environment):
            try:
                node = load(path)  # Real environment-driven initialize executes here.
            except RuntimeError as error:
                if expect_error is None or expect_error not in str(error):
                    raise
                assert 'install' not in events, 'Rejected startup installed router'
                return {'error': str(error), 'events': events}
            assert expect_error is None, 'Expected startup refusal'
            assert events == ['context', 'install']
            assert set(node.NODE_CLASS_MAPPINGS) == {'LTXNAAxisDecode'}
            cls = node.NODE_CLASS_MAPPINGS['LTXNAAxisDecode']
            assert issubclass(cls, namespace['VAEDecode'])
            assert cls.FUNCTION == 'decode' and cls.RETURN_TYPES == ('IMAGE',)
            assert list(cls.INPUT_TYPES()['required']) == ['samples', 'vae', 'mode', 'run_name']
            try:
                node.initialize()
            except RuntimeError as error:
                assert str(error) == 'NA decode node already initialized'
            else:
                raise AssertionError('Second startup installed another router')
            assert events == ['context', 'install']
            return {'registered': list(node.NODE_CLASS_MAPPINGS), 'events': events,
                    'duplicate_startup_rejected': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert 'torch' not in sys.modules
    old = LANE / 'scripts/na_axis_decode_node.py'
    new = LANE / 'scripts/na_axis_decode_node_v2.py'
    results = {
        'old_packet09_failure_reproduced': exercise(old, 'Original VAE decode source differs'),
        'corrected_startup_registers_once': exercise(new),
        'wrong_nodes_refused': exercise(new, 'Original VAE decode source differs: nodes', bad_module='nodes'),
        'wrong_sd_refused': exercise(new, 'Original VAE decode source differs: comfy.sd', bad_module='comfy.sd'),
        'wrong_decoder_refused': exercise(new, 'Original VAE decode source differs: comfy.ldm.lightricks.vae.na_diffusion_decoder', bad_module='comfy.ldm.lightricks.vae.na_diffusion_decoder'),
        'wrong_router_refused': exercise(new, 'NA router source differs', bad_module='ltx_na_axis_router'),
        'wrong_context_refused': exercise(new, 'NA startup environment/server identity changed', bad_context=True),
        'wrong_identity_refused': exercise(new, 'NA startup server identity differs', bad_identity=True),
    }
    assert 'torch' not in sys.modules and 'comfy.sd' not in sys.modules
    report = {'status': 'passed-stdlib-startup-integration', 'checks': results,
              'node_sha256': sha(new), 'old_node_sha256': sha(old), 'test_sha256': sha(__file__),
              'source_packet_manifest_sha256': sha(PACKET / 'manifest.json'),
              'torch_imported': False, 'native_requests': 0,
              'limitations': 'Real initialize and inherited source hashes; stub modules/install/context, no real native startup or decode.'}
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2); handle.write('\n')
    print(json.dumps({'status': report['status'], 'checks': len(results), 'node_sha256': sha(new)}))


if __name__ == '__main__':
    main()
