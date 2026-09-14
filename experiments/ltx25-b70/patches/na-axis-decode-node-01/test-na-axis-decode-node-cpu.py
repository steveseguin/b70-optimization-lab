#!/usr/bin/env python3
"""Original extracted VAEDecode + fake VAE + actual Kitchen CPU dispatcher.

No Comfy imports/model weights; native XPU availability/initialization blocked.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
FAULT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json')
NODES = Path('/home/steve/src/ComfyUI-ltx25-baseline/nodes.py')


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu', action='store_true', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(args.cpu and not FAULT.exists(), 'CPU/fault guard failed before Torch import')
    require(os.environ.get('OMP_NUM_THREADS') == os.environ.get('MKL_NUM_THREADS') == '1', 'Set OMP/MKL_NUM_THREADS=1')
    args.output.mkdir(exist_ok=False)
    state = {'status': 'running', 'phase': 'before-torch-import', 'pid': os.getpid(),
             'test_sha256': sha(__file__), 'checks': [], 'forbidden_device_calls': [],
             'suppressed_availability_probes': []}
    def save():
        (args.output / 'receipt.json').write_text(json.dumps(state, indent=2) + '\n')
    save()
    try:
        # Prevent any environment-driven startup integration in this test process.
        state['startup_environment_removed'] = [key for key in
            ('LTX_ENCODER_RUN_DIR', 'LTX_ENCODER_IDENTITY_SHA256') if os.environ.pop(key, None) is not None]
        node = load('na_decode_node_cpu_test', LANE / 'scripts/na_axis_decode_node.py')
        adapter = load('na_axis_router_cpu_test', LANE / 'scripts/ltx_na_axis_router.py')
        require(sha(NODES) == node.NODES_SHA and sha(adapter.__file__) == node.ROUTER_SHA, 'Pinned sources changed')
        tree = ast.parse(NODES.read_text())
        original_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'VAEDecode')
        ns = {}
        exec(compile(ast.Module(body=[original_class], type_ignores=[]), str(NODES), 'exec'), ns)
        original = ns['VAEDecode']
        state['source_pins'] = {'node': sha(node.__file__), 'router': sha(adapter.__file__), 'nodes': sha(NODES)}
        import torch
        state['xpu_initialized_before'] = torch.xpu.is_initialized()
        require(state['xpu_initialized_before'] is False, 'XPU already initialized')
        torch.set_num_threads(1)
        def forbidden(name):
            def fail(*args, **kwargs):
                state['forbidden_device_calls'].append(name)
                raise AssertionError('Forbidden device call: ' + name)
            return fail
        def unavailable(name):
            def probe(*args, **kwargs):
                state['suppressed_availability_probes'].append(name)
                return False
            return probe
        for name in ('init', '_lazy_init', 'device_count', 'current_device', 'get_device_properties',
                     'get_device_name', 'get_device_capability', 'set_device'):
            if hasattr(torch.xpu, name):
                setattr(torch.xpu, name, forbidden('torch.xpu.' + name))
        for name in ('_xpu_init', '_xpu_getDeviceCount'):
            if hasattr(torch._C, name):
                setattr(torch._C, name, forbidden('torch._C.' + name))
        torch.xpu.is_available = unavailable('torch.xpu.is_available')
        torch.cuda.is_available = unavailable('torch.cuda.is_available')
        state['phase'] = 'before-kitchen-import'
        save()
        import comfy_kitchen
        require(not FAULT.exists(), 'Fault appeared during CPU import')
        router = adapter.install(LANE / 'data/na-axis-cache-01/candidate-na.py')
        state['phase'] = 'node-lifecycle'
        save()
        shape = (1, 2, 3, 3, 1, 4)
        latent = (torch.arange(72, dtype=torch.float32, device='cpu').reshape(shape) / 64).to(torch.bfloat16)
        class Decoder:
            def forward(self, x):
                return comfy_kitchen.na3d(x, x, x, [3, 3, 3], None, 1.0)
        class Stage:
            def __init__(self):
                self.decoder = Decoder()
                self.config = {'cpu_fake_config': True, 'decoder': {'head_dim': 4}}
            def decode(self, x):
                return self.decoder.forward(x)
        class VAE:
            def __init__(self):
                self.first_stage_model = Stage()
                self.patcher = object()
                self.inputs = []
                self.fail = False
                self.skip_na = False
                self.change_config = False
            def decode(self, x):
                self.inputs.append(x)
                if self.fail:
                    raise ValueError('synthetic original VAE failure')
                out = x if self.skip_na else self.first_stage_model.decode(x)
                if self.change_config:
                    self.first_stage_model.config['late_mutation'] = True
                return out.squeeze(-2)  # Original VAEDecode flattens this5D output.
        def same(a, b):
            return a.shape == b.shape and a.dtype == b.dtype and torch.equal(a.contiguous().view(torch.uint8), b.contiguous().view(torch.uint8))
        def check(name):
            require(not FAULT.exists(), 'Fault appeared')
            state['checks'].append({'name': name, 'passed': True})
        def factory(name):
            root = args.output / name
            root.mkdir()
            identity = {'server_identity_sha256': 'a'*64, 'model_verification_sha256': 'b'*64}
            cls = node.create_node_class(original, router, lambda: (root, identity),
                {'cpu_fixture': True, **state['source_pins']})
            return cls(), root, identity
        def receipt(root, run):
            return json.loads((root / ('na-axis-' + run) / 'result.json').read_text())
        def rejects(action):
            try:
                action()
            except Exception:
                return
            raise AssertionError('Expected refusal')
        with torch.inference_mode():
            instance, root, identity = factory('normal')
            vae = VAE()
            expected = original().decode(vae, {'samples': latent})[0]
            require(list(expected.shape) == [2, 3, 3, 4], 'Original5D reshape fixture differs')
            owners = None
            for mode, run in [('original', 'cpu-r01-original'), ('axis-cache', 'cpu-r02-cache'), ('original', 'cpu-r03-original')]:
                result = instance.decode(vae, {'samples': latent}, mode, run)
                report = receipt(root, run)
                require(same(result[0], expected) and vae.inputs[-1] is latent, 'Original method or input ownership differs')
                require(report['status'] == 'passed-decode-route' and report['context_clear_after'] and
                        report['route']['scope_reset'] and len(report['route']['calls']) == 1, 'Route receipt invalid')
                require(report['decoder_config'] == vae.first_stage_model.config and
                        report['output']['shape'] == [2, 3, 3, 4], 'Config/output metadata differs')
                require(owners is None or owners == report['owners'], 'Owner receipt changed')
                owners = report['owners']
                started = json.loads((root / ('na-axis-' + run) / 'started.json').read_text())
                require(started['decoder_config'] == report['decoder_config'] and started['owners'] == report['owners'], 'Started identity incomplete')
            check('original-cache-original-full-dispatch-exact-output-owners-and-reshape')
            require(set(instance.INPUT_TYPES()['required']) == {'samples', 'vae', 'mode', 'run_name'} and
                    instance.RETURN_TYPES == ('IMAGE',), 'Node interface differs')
            check('original-input-output-interface-preserved')
            # Real nested tensor exercises original unbind()[0], without a copied decode.
            nested = torch.nested.nested_tensor([latent, latent + 1], dtype=torch.bfloat16, device='cpu')
            nested_expected = original().decode(vae, {'samples': nested})[0]
            got = instance.decode(vae, {'samples': nested}, 'axis-cache', 'cpu-r04-nested')[0]
            require(same(got, nested_expected) and receipt(root, 'cpu-r04-nested')['input']['nested'] is True,
                    'Original nested-latent behavior differs')
            check('real-nested-latent-first-element-and-output-reshape')
            instance2, root2, identity2 = factory('decode-failure')
            failing = VAE(); failing.fail = True
            rejects(lambda: instance2.decode(failing, {'samples': latent}, 'axis-cache', 'cpu-r01-failed'))
            report = receipt(root2, 'cpu-r01-failed')
            require(report['status'] == 'failed' and report['context_clear_after'] and
                    report['route']['status'] == 'failed' and report['route']['scope_reset'], 'Exception receipt/reset differs')
            failing.fail = False
            previous = len(failing.inputs)
            rejects(lambda: instance2.decode(failing, {'samples': latent}, 'original', 'cpu-r02-no-retry'))
            require(len(failing.inputs) == previous and not (root2 / 'na-axis-cpu-r02-no-retry').exists(), 'Sticky failure retried')
            check('decode-exception-durable-failure-reset-and-sticky-no-retry')
            skip_node, skip_root, _ = factory('missing-coverage')
            skipped = VAE(); skipped.skip_na = True
            rejects(lambda: skip_node.decode(skipped, {'samples': latent}, 'axis-cache', 'cpu-r01-skipped'))
            require(receipt(skip_root, 'cpu-r01-skipped')['status'] == 'failed' and router._mode.get() is None,
                    'Skipped custom op falsely qualified')
            check('missing-custom-op-coverage-fails-closed')
            mutate_node, mutate_root, _ = factory('config-mutation')
            mutate = VAE(); mutate.change_config = True
            rejects(lambda: mutate_node.decode(mutate, {'samples': latent}, 'axis-cache', 'cpu-r01-mutated'))
            require(receipt(mutate_root, 'cpu-r01-mutated')['status'] == 'failed', 'Late config mutation accepted')
            check('decoder-config-change-during-decode-rejected')
            owner_node, owner_root, _ = factory('owner-change')
            owner_node.decode(VAE(), {'samples': latent}, 'original', 'cpu-r01-owner')
            rejects(lambda: owner_node.decode(VAE(), {'samples': latent}, 'axis-cache', 'cpu-r02-owner'))
            require(receipt(owner_root, 'cpu-r02-owner')['status'] == 'failed', 'Owner replacement accepted')
            check('owner-change-between-requests-rejected')
            # Existing evidence remains byte-identical when a request name repeats.
            protected = root / 'na-axis-cpu-r01-original/result.json'
            before = protected.read_bytes()
            rejects(lambda: instance.decode(vae, {'samples': latent}, 'original', 'cpu-r01-original'))
            require(protected.read_bytes() == before, 'Duplicate request overwrote evidence')
            check('duplicate-run-preserves-exclusive-evidence')
            id_node, id_root, id_context = factory('identity-change')
            id_vae = VAE()
            id_node.decode(id_vae, {'samples': latent}, 'original', 'cpu-r01-identity')
            id_context['server_identity_sha256'] = 'c'*64
            count = len(id_vae.inputs)
            rejects(lambda: id_node.decode(id_vae, {'samples': latent}, 'axis-cache', 'cpu-r02-identity'))
            require(len(id_vae.inputs) == count, 'Changed identity executed decoder')
            check('server-identity-change-before-decode-rejected')
            router.validate()
        require(not state['forbidden_device_calls'] and not torch.xpu.is_initialized(), 'Forbidden XPU work')
        state.update(status='passed-cpu-node-lifecycle', phase='complete', xpu_initialized_after=False,
            limitation='Actual original VAEDecode class and Kitchen dispatcher, but fake VAE/CPU-only registration; no native decoder/config/quality/speed qualification.')
        save()
        print(json.dumps({'status': state['status'], 'checks': len(state['checks']), 'output': str(args.output)}, indent=2))
    except BaseException as error:
        state.update(status='failed-unqualified', error=repr(error))
        save()
        raise


if __name__ == '__main__':
    main()
