"""Inactive private VAE decode node; startup routing, unchanged original decode.

Without LTX_ENCODER_RUN_DIR, importing this module is stdlib-only and exposes the
CPU-test factory. A sealed custom-node startup sets that environment and pins
all dependencies before installing the router once. No per-request patching.
"""
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import time

ROUTER_SHA = '9aa3d6cc7be389555d60119ad3fd5960b762568e044eba49760fc03114c2b537'
CANDIDATE_SHA = 'bdd41e44716ff1e287e13fe9993578ce7bf6ccb18ca8b85f7767340ea6d4429c'
NODES_SHA = 'dddf275f6dbcbd1a9cbdc02ebee2bad86bf022cc968c58a3f14cb26a2d08926e'
SD_SHA = '41cbf195657cc81a60173f13f192966c4276bf7931a6c10f75870a66c59546b0'
DECODER_SHA = '7356bfcaedc545e8af1f4820e7466bbde0a56ccd2e8b2941902af83f16657f21'
NODE_CLASS_MAPPINGS = {}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    # Exclusive evidence is synchronous, including flush/fsync; all work remains
    # inside the node invocation. A receipt is not an output-quality verdict.
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def metadata(value):
    nested = bool(value.is_nested)
    return {'nested': nested, 'shape': None if nested else list(value.shape),
            'dtype': str(value.dtype), 'device': str(value.device)}


def create_node_class(original_class, router, context_provider, source_identity):
    """Bind one original class/router/context; factory owns shared sticky failure.

    context_provider returns (existing server directory, immutable identity dict)
    and checks fault/identity state. Native initialization supplies the real one;
    tests supply isolated CPU evidence paths, never the live server directory.
    """
    original_decode = original_class.decode
    sources = json.loads(json.dumps(source_identity))
    failed = False
    retained_owners = None
    retained_methods = None
    bound_identity = None
    bound_run = None
    retained_config = None

    def owners_and_methods(vae):
        owners = (vae, vae.patcher, vae.first_stage_model, vae.first_stage_model.decoder)
        methods = tuple(getattr(method, '__func__', method) for method in
                        (vae.decode, vae.first_stage_model.decode, vae.first_stage_model.decoder.forward))
        return owners, methods

    class LTXNAAxisDecode(original_class):
        @classmethod
        def INPUT_TYPES(cls):
            result = dict(original_class.INPUT_TYPES())
            result['required'] = dict(result['required'])
            result['required'].update(mode=(['original', 'axis-cache'],),
                run_name=('STRING', {'default': 'assign-unique-request-name'}))
            return result

        FUNCTION = 'decode'
        CATEGORY = 'lab/validation'

        @classmethod
        def IS_CHANGED(cls, **kwargs):
            return float('nan')

        def decode(self, vae, samples, mode, run_name):
            nonlocal failed, retained_owners, retained_methods, bound_identity, bound_run, retained_config
            directory, report, route = None, None, None
            try:
                require(not failed, 'Prior NA decode failure; halt without retry')
                require(mode in ('original', 'axis-cache') and isinstance(run_name, str) and
                        re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name), 'Invalid NA decode mode/run')
                run, identity = context_provider()
                identity = json.loads(json.dumps(identity, allow_nan=False))
                run = Path(run).absolute()
                require(run.is_dir() and not any(p.is_symlink() for p in (run, *run.parents)),
                        'Linked or missing NA evidence directory')
                require(bound_run is None or bound_run == run, 'NA server directory changed')
                require(bound_identity is None or bound_identity == identity, 'NA server identity changed')
                bound_run, bound_identity = run, dict(identity)
                directory = run / ('na-axis-' + run_name)
                directory.mkdir(exist_ok=False)
                report = {'schema': 'ltx.na-axis-decode.v1', 'status': 'started', 'mode': mode,
                          'run_name': run_name, 'source_identity': sources, 'identity': dict(identity),
                          'started_monotonic_ns': time.monotonic_ns(), 'route': None,
                          'quality_qualified': False, 'native_sequence_qualified': False}
                require(original_class.decode is original_decode, 'Original VAEDecode method changed')
                require(router._mode.get() is None, 'Unexpected existing NA scope at decode entry')
                owners, methods = owners_and_methods(vae)
                require(retained_owners is None or all(a is b for a, b in zip(retained_owners, owners)),
                        'VAE owner changed within NA decode lane')
                require(retained_methods is None or all(a is b for a, b in zip(retained_methods, methods)),
                        'VAE decode callable changed within NA decode lane')
                retained_owners, retained_methods = owners, methods
                report['owners'] = dict(zip(('vae', 'patcher', 'first_stage_model', 'decoder'), map(id, owners)))
                report['input'] = metadata(samples['samples'])
                require(isinstance(vae.first_stage_model.config, dict), 'Missing actual decoder config')
                config = json.loads(json.dumps(vae.first_stage_model.config, allow_nan=False))
                require(retained_config is None or retained_config == config, 'Decoder config changed between requests')
                retained_config = config
                report['decoder_config'] = config
                write_json(directory / 'started.json', report)
                with router.scope(mode, run_name) as route:
                    report['route'] = route
                    result = original_decode(self, vae, samples)
                require(router._mode.get() is None and route.get('scope_reset') is True,
                        'NA context failed to reset')
                require(original_class.decode is original_decode, 'Original VAEDecode method changed during decode')
                after_owners, after_methods = owners_and_methods(vae)
                require(json.loads(json.dumps(vae.first_stage_model.config, allow_nan=False)) == config,
                        'Decoder config changed during decode')
                require(all(a is b for a, b in zip(owners, after_owners)) and
                        all(a is b for a, b in zip(methods, after_methods)), 'VAE ownership changed during decode')
                after_run, after_identity = context_provider()
                require(Path(after_run).absolute() == run and after_identity == identity,
                        'NA request identity changed during decode')
                require(type(result) is tuple and len(result) == 1, 'Original VAEDecode output contract changed')
                report.update(status='passed-decode-route', output=metadata(result[0]))
                return result
            except BaseException as error:
                failed = True
                if report is not None:
                    report.update(status='failed', error=repr(error))
                raise
            finally:
                if report is not None:
                    report['finished_monotonic_ns'] = time.monotonic_ns()
                    report['context_clear_after'] = router._mode.get() is None
                    try:
                        write_json(directory / 'result.json', report)
                    except BaseException:
                        failed = True
                        raise

    return LTXNAAxisDecode


def initialize():
    """Called once during sealed custom-node import, before serving requests."""
    require(not NODE_CLASS_MAPPINGS, 'NA decode node already initialized')
    run_value = os.environ.get('LTX_ENCODER_RUN_DIR', '')
    identity_sha = os.environ.get('LTX_ENCODER_IDENTITY_SHA256', '')
    require(run_value and re.fullmatch(r'[0-9a-f]{64}', identity_sha), 'Missing sealed NA startup identity')
    run = Path(run_value)
    require(run.is_absolute() and run.is_dir() and not any(p.is_symlink() for p in (run, *run.parents)),
            'Invalid NA startup evidence directory')
    require(not (run / 'FAULT.json').exists() and not (run.parent / 'FAULT.json').exists(), 'Fault recorded')
    require(sha(run / 'server-identity.json') == identity_sha, 'NA startup server identity differs')
    adapter = importlib.import_module('ltx_na_axis_router')
    require(sha(adapter.__file__) == ROUTER_SHA, 'NA router source differs')
    candidate = Path(adapter.__file__).with_name('ltx_na_axis_candidate.py')
    require(sha(candidate) == CANDIDATE_SHA, 'NA candidate source differs')
    nodes = importlib.import_module('nodes')
    sd = importlib.import_module('comfy.sd')
    decoder = importlib.import_module('comfy.ldm.lightricks.vae.na_diffusion_decoder')
    for module, expected in ((nodes, NODES_SHA), (sd, SD_SHA), (decoder, DECODER_SHA)):
        require(sha(module.__file__) == expected, 'Original VAE decode source differs: ' + module.__name__)
    from encoder_diagnostics import _context
    sources = {'node_sha256': sha(__file__), 'router_sha256': ROUTER_SHA, 'candidate_sha256': CANDIDATE_SHA,
               'original_na_sha256': adapter.ORIGINAL_SHA, 'nodes_sha256': NODES_SHA,
               'sd_sha256': SD_SHA, 'decoder_sha256': DECODER_SHA,
               'decoder_seed_contract': {'source_fixed_seed': 0, 'observed_rng_state': False}}
    def context():
        observed_run, identity = _context()
        require(observed_run == run and identity['server_identity_sha256'] == identity_sha and
                os.environ.get('LTX_ENCODER_RUN_DIR') == run_value and
                os.environ.get('LTX_ENCODER_IDENTITY_SHA256') == identity_sha,
                'NA startup environment/server identity changed')
        require(not (run / 'FAULT.json').exists(), 'Server fault recorded')
        return observed_run, identity
    # Validate startup context before installing the one router mutation.
    context()
    router = adapter.install(candidate)
    NODE_CLASS_MAPPINGS['LTXNAAxisDecode'] = create_node_class(nodes.VAEDecode, router, context, sources)
    return NODE_CLASS_MAPPINGS


if os.environ.get('LTX_ENCODER_RUN_DIR'):
    initialize()
