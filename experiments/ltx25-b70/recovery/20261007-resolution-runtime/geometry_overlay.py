#!/usr/bin/env python3
"""Pure, hash-pinned source transformation for a new resolution runtime. No device/import/build actions."""
import ast
import hashlib

PARENT_MANIFEST_SHA256 = 'f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a'
PLAN_SHA256 = 'b4590ffc14a7a4a2c0c3e59d6785cfbfc85df1d3080687f05bfd12ffd390002d'
QUALIFICATION_ID = '1979c71925283fd715e9983baba81f7d0c2cd7dc4534a1514c016ededa4e4923'
GEOMETRY_PATH = 'source/scripts/ltx_output_size_98.py'
SPECS = {
    'pipeline_node.py': ('text', '3c170dc810c95ad00aebd721c7031c1a9220b152b52a779925ef672e0e89b690', 'ltx_pipeline_lab'),
    'pipeline_sampler_node.py': ('sampler', '1d20b4ad3341710f71a36d8d1bef57e0f11004a4a9cb5bbd46bced1407e377b0', 'ltx_pipeline_sampler_lab'),
    'pipeline_decode_node.py': ('decode', 'bb03e12809feaedf93235130827d40d352b21ee8488c31f08dec1397c068d8c8', 'ltx_pipeline_decode_lab'),
}
SOURCE_HASHES = {GEOMETRY_PATH: '895b1c02ac764838b5d69446b0e5cf054884b191dd8b9446c5ce641ec40f2e52'}
for name, (_, sha, package) in SPECS.items():
    SOURCE_HASHES['source/scripts/' + name] = sha
    SOURCE_HASHES['source/custom_nodes/' + package + '/__init__.py'] = sha

# Appended to the original geometry module; historical functions remain intact.
RUNTIME_EXTENSION = r'''

# Explicit same-size reference mode. The old guards above remain historical defaults.
_RESOLUTION_PLAN_SHA256 = '@PLAN@'
_RESOLUTION_QUALIFICATION_ID = '@ID@'
_RESOLUTION_MODE = 'same-size-native-v1'
_RESOLUTION_CONTEXT = contextvars.ContextVar('resolution_reference_authorization', default=None)
_legacy_receipt_scope = receipt_scope
_legacy_receipt_metadata = receipt_metadata
_legacy_admit_arm = admit_arm


def _resolution_require(ok, message):
    if not ok:
        raise RuntimeError(message)


def _resolution_authorize(role, fields):
    import re
    mode, qid = fields.get('comparison_mode', 'historical'), fields.get('qualification_id', '')
    _resolution_require(mode == _RESOLUTION_MODE and qid == _RESOLUTION_QUALIFICATION_ID,
                        'Unknown same-size comparison mode or qualification ID')
    _resolution_require(role in ('text', 'sampler', 'decode'), 'Unknown same-size role')
    _resolution_require(OUTPUT_SIZE == fields.get('output_size') == '640x384' and
                        fields.get('speed_only') is False, 'Same-size mode requires640x384 and explicit non-speed comparison')
    env = {'LTX_SAMPLER_PLACEMENT': 'two-way', 'LTX_SAMPLER_WORKERS': '2',
           'LTX_SAMPLER_BATCH': '1', 'LTX_SAMPLER_SHARED_POOL': '1',
           'LTX_DECODE_REPLICA_DEVICE': 'xpu:2', 'LTX_DECODE_REPLICAS': '1'}
    _resolution_require(all(os.environ.get(k) == v for k, v in env.items()),
                        'Same-size mode requires exact23/25 W2 B1 shared-pool configuration')
    _resolution_require(_RESOLUTION_CONTEXT.get() is None, 'Nested same-size authorization refused')
    run_name = fields.get('run_name')
    _resolution_require(isinstance(run_name, str) and re.fullmatch('[a-z0-9][a-z0-9-]{0,119}', run_name),
                        'Unsafe same-size request name')
    # The sealed launcher configures this module once AFTER final server identity.
    # It owns registered request graphs and evidence-driven phases, not client JSON.
    import ltx_resolution_session
    auth = ltx_resolution_session.require_phase(role, qid, run_name)
    _resolution_require(isinstance(auth, dict), 'Missing phase authority receipt')
    required = {'role': role, 'run_name': run_name, 'plan_sha256': _RESOLUTION_PLAN_SHA256,
                'qualification_id': qid, 'comparison_mode': mode}
    _resolution_require(all(auth.get(k) == v for k, v in required.items()), 'Phase authority identity differs')
    phase = auth.get('phase')
    _resolution_require(phase in (('native_reference', 'optimized_preparation', 'timing') if role == 'text'
                                 else ('optimized_preparation', 'timing')), 'Role not permitted in phase')
    for key in ('runtime_manifest_sha256', 'server_identity_sha256'):
        _resolution_require(isinstance(auth.get(key), str) and re.fullmatch('[0-9a-f]{64}', auth[key]),
                            'Phase authority lacks runtime/server identity')
    if phase != 'native_reference':
        _resolution_require(isinstance(auth.get('reference_receipt_sha256'), str) and
                            re.fullmatch('[0-9a-f]{64}', auth['reference_receipt_sha256']),
                            'Verified independent reference receipt required')
    if phase == 'timing':
        _resolution_require(isinstance(auth.get('candidate_receipt_sha256'), str) and
                            re.fullmatch('[0-9a-f]{64}', auth['candidate_receipt_sha256']),
                            'Verified candidate parity receipt required before timing')
    # Do not retain a mutable authority-owned dict through the numerical call.
    keys = ('phase', 'role', 'run_name', 'plan_sha256', 'qualification_id', 'comparison_mode',
            'runtime_manifest_sha256', 'server_identity_sha256', 'reference_receipt_sha256',
            'candidate_receipt_sha256')
    return {k: auth[k] for k in keys if k in auth}


def receipt_scope(fn=None, *, role=None):
    def decorate(function):
        legacy = _legacy_receipt_scope(function)
        signature = inspect.signature(function)
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            bound = signature.bind(*args, **kwargs); bound.apply_defaults()
            fields = bound.arguments
            mode = fields.get('comparison_mode', 'historical')
            if mode == 'historical':
                _resolution_require(fields.get('qualification_id', '') == '' and _RESOLUTION_CONTEXT.get() is None,
                                    'Historical mode cannot inherit same-size authority')
                return legacy(*args, **kwargs)
            auth = _resolution_authorize(role, fields)
            token = _RESOLUTION_CONTEXT.set(auth)
            try:
                return legacy(*args, **kwargs)
            finally:
                _RESOLUTION_CONTEXT.reset(token)
        return wrapped
    return decorate(fn) if fn is not None else decorate


def admit_arm(output_size=DEFAULT, speed_only=False):
    auth = _RESOLUTION_CONTEXT.get()
    if auth is None:
        return _legacy_admit_arm(output_size, speed_only)
    _resolution_require(output_size == OUTPUT_SIZE == '640x384' and speed_only is False,
                        'Authorized reference geometry/speed mode changed')


def receipt_metadata(size=OUTPUT_SIZE, batch=None, speed_only=None):
    auth = _RESOLUTION_CONTEXT.get()
    if auth is None:
        # Worker completion/save/coverage receipts carry observation, never a numerical grant.
        import sys
        session = sys.modules.get('ltx_resolution_session')
        auxiliary = session.auxiliary_metadata() if session is not None else None
        if auxiliary is None:
            return _legacy_receipt_metadata(size, batch, speed_only)
        import re
        _resolution_require(isinstance(auxiliary, dict) and
                            auxiliary.get('comparison_mode') == _RESOLUTION_MODE and
                            auxiliary.get('qualification_id') == _RESOLUTION_QUALIFICATION_ID and
                            auxiliary.get('plan_sha256') == _RESOLUTION_PLAN_SHA256 and
                            auxiliary.get('role') == 'auxiliary' and auxiliary.get('run_name') is None and
                            auxiliary.get('output_parity_claimed') is False and
                            auxiliary.get('phase') in ('native_reference', 'reference_verified',
                                'optimized_preparation', 'candidate_verified', 'timing') and
                            size == OUTPUT_SIZE == '640x384', 'Invalid same-size auxiliary observation')
        for key in ('runtime_manifest_sha256', 'server_identity_sha256'):
            _resolution_require(isinstance(auxiliary.get(key), str) and
                                re.fullmatch('[0-9a-f]{64}', auxiliary[key]), 'Missing auxiliary runtime identity')
        return {'output_size': size, 'speed_only': False,
                'comparison': 'same-size-native-reference:auxiliary-no-output-parity',
                'comparison_mode': _RESOLUTION_MODE, 'qualification_id': _RESOLUTION_QUALIFICATION_ID,
                'session_observation': dict(auxiliary), 'output_parity_claimed': False}
    _resolution_require(size == OUTPUT_SIZE == '640x384' and (batch is None or type(batch) is int and batch == 1)
                        and (speed_only is None or speed_only is False), 'Same-size receipt geometry/batch differs')
    return {'output_size': size, 'speed_only': False,
            'comparison': 'same-size-native-reference:external-four-tensor-gate-required',
            'comparison_mode': _RESOLUTION_MODE, 'qualification_id': auth['qualification_id'],
            'phase_authorization': dict(auth), 'output_parity_claimed': False}
'''.replace('@PLAN@', PLAN_SHA256).replace('@ID@', QUALIFICATION_ID)


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected source anchor count: ' + repr(old))
    return text.replace(old, new)


def transform(path, raw):
    """Return successor bytes only. Caller owns newpacket write/provenance/manifest checks."""
    if path not in SOURCE_HASHES or hashlib.sha256(raw).hexdigest() != SOURCE_HASHES[path]:
        raise ValueError('Unknown or changed immutable99b source: ' + path)
    text = raw.decode('utf-8')
    if path == GEOMETRY_PATH:
        text += RUNTIME_EXTENSION
    else:
        name = next(name for name, (_, _, package) in SPECS.items()
                    if path in ('source/scripts/' + name, 'source/custom_nodes/' + package + '/__init__.py'))
        role = SPECS[name][0]
        text = replace_once(text, '@size98.receipt_scope', '@size98.receipt_scope(role=' + repr(role) + ')')
        text = replace_once(text, "'speed_only': ('BOOLEAN', {'default': False})",
                            "'comparison_mode': ('STRING', {'default': 'historical'}),\n"
                            "                             'qualification_id': ('STRING', {'default': ''}),\n"
                            "                             'speed_only': ('BOOLEAN', {'default': False})")
        if role == 'sampler':
            text = replace_once(text, 'speed_only=False, **chain):',
                                "speed_only=False, comparison_mode='historical', qualification_id='', **chain):")
        else:
            text = replace_once(text, 'speed_only=False):',
                                "speed_only=False, comparison_mode='historical', qualification_id=''):")
    ast.parse(text)
    return text.encode('utf-8')


def transform_sources(sources):
    if set(sources) != set(SOURCE_HASHES):
        raise ValueError('All seven exact geometry/node source paths required')
    result = {path: transform(path, raw) for path, raw in sources.items()}
    for name, (_, _, package) in SPECS.items():
        if result['source/scripts/' + name] != result['source/custom_nodes/' + package + '/__init__.py']:
            raise ValueError('Canonical/custom-node output mismatch')
    return result
