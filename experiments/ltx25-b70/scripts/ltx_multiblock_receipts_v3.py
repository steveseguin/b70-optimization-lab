"""Stdlib offline receipt gates for the pinned packet08 one-pass screen.

The caller owns live server/packet identity checks, full-output comparison and
cross-request ownership continuity. Receipt acceptance is not clip acceptance.
"""
import hashlib
import json
import math
import re
from pathlib import Path

SELECTIONS = {'single24': (24,), 'boundary4': (0, 20, 21, 47), 'all48': tuple(range(48))}
PACKET_MANIFEST_SHA = 'a32f645772d2ef59d46b66c9181f1d9433950172bcc763924de8aa7acb679b6b'
MODEL_SHA = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
ADAPTER_SHA = 'ba89394822e9ec607cc8ec7aad092a3afa7d87e0f723b781cf27f1f6158c031b'
NODE_SHA = 'e7d6e69ff44d5b727dba27f52142647a06afe6d494abb043af49fa132a005d2f'
NATIVE_ACTIVATIONS_BACKEND_SHA = '62b78186fdfc6d9a22cb8cb10423869ecc37cc09c9c0994a7ccebe2eafd41c2a'
NATIVE_RMS_BACKEND_SHA = '09defae7340dc3d7f33e16ab80c76f22b6a2ae733617704f2e7b69086108d9fb'
NATIVE_RMS_OPTIONS = {'compile_threads': 1, 'emulate_precision_casts': True,
    'eager_numerics.division_rounding': True, 'triton.cudagraphs': False,
    'max_autotune': False, 'max_autotune_gemm': False}
EXTENSIONS = {'ltx_multiblock_compile.py': ADAPTER_SHA, 'multiblock_compile_node.py': NODE_SHA,
    'ltx_native_activations_backend.py': NATIVE_ACTIVATIONS_BACKEND_SHA,
    'ltx_native_rms_backend.py': NATIVE_RMS_BACKEND_SHA}


def require(value, message):
    if not value:
        raise ValueError(message)


def safe_path(path):
    path = Path(path).absolute()
    require('..' not in path.parts, 'Parent path traversal')
    require(all(not part.is_symlink() for part in (path, *path.parents)), 'Symlink evidence path')
    require(path.exists(), 'Missing evidence path')
    return path


def sha(path):
    return hashlib.sha256(safe_path(path).read_bytes()).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def read_json(path):
    return json.loads(safe_path(path).read_text(), object_pairs_hook=_pairs)


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _positive(value):
    return type(value) is int and value > 0


def _exact_config(value, expected):
    return (isinstance(value, dict) and value == expected and
            all(type(value[key]) is type(wanted) for key, wanted in expected.items()))


def validate_native_operation_receipts(directory, device):
    directory = safe_path(directory)
    require({p.name for p in directory.iterdir()} == {
        f'graph-{i:03d}{suffix}' for i in (1, 2)
        for suffix in ('.json', '-before.py', '-after.py')}, 'Unexpected native graph files')
    paths = sorted(directory.glob('graph-*.json'))
    require([p.name for p in paths] == ['graph-001.json', 'graph-002.json'],
            'Native RMS requires exactly two graph receipts')
    records = []
    for number, path in enumerate(paths, 1):
        safe_path(directory / path.name)
        row = read_json(path)
        require(row.get('schema') == 'ltx25.native-activations-fx-rewrite.v1' and
                row.get('status') == 'compiled-native-activations-boundary' and
                type(row.get('graph')) is int and row['graph'] == number,
                'Native RMS graph schema/status/index failed')
        require(row.get('source_sha256') == NATIVE_ACTIVATIONS_BACKEND_SHA and
                row.get('dependency_sha256') == NATIVE_RMS_BACKEND_SHA and
                row.get('expected_count') == 15 and
                _exact_config(row.get('expected_activation_counts'), {'sigmoid': 6, 'gelu': 2}) and
                _exact_config(row.get('options'), NATIVE_RMS_OPTIONS) and 'error' not in row,
                'Native RMS backend/options identity failed')
        replacements = row.get('replacements')
        require(isinstance(replacements, list) and len(replacements) == 15,
                'Native RMS graph requires fifteen replacements')
        require(all(isinstance(r, dict) and isinstance(r.get('node'), str) for r in replacements) and
                len({r['node'] for r in replacements}) == 15,
                'Native RMS replacement identities are invalid or duplicated')
        for r in replacements:
            shape, metadata = r.get('normalized_shape'), r.get('input')
            require(isinstance(shape, list) and len(shape) == 1 and shape[0] in (2048, 4096) and
                    isinstance(metadata, dict) and metadata.get('dtype') == 'torch.bfloat16' and
                    metadata.get('device') == device and metadata.get('contiguous') is True and
                    isinstance(metadata.get('shape'), list) and metadata['shape'][-1:] == shape,
                    'Native RMS input metadata differs from native block')
            require(type(r.get('weighted')) is bool and r.get('eps') == (1e-5 if r['weighted'] else 1e-6),
                    'Native RMS weighting/epsilon changed')
            weight = r.get('weight')
            require((not r['weighted'] and weight is None) or
                    (r['weighted'] and isinstance(weight, dict) and weight.get('shape') == shape and
                     weight.get('dtype') == metadata['dtype'] and weight.get('device') == metadata['device'] and
                     weight.get('contiguous') is True), 'Native RMS weight metadata changed')
        require(sum(r['weighted'] for r in replacements) == 12,
                'Native RMS expected twelve weighted and three unweighted sites')
        activations = row.get('activation_replacements')
        require(isinstance(activations, list) and len(activations) == 8 and
                all(isinstance(r, dict) and isinstance(r.get('node'), str) for r in activations) and
                len({r['node'] for r in activations}) == 8,
                'Native activation replacement count/identities failed')
        require({kind: sum(r.get('kind') == kind for r in activations) for kind in ('sigmoid', 'gelu')} ==
                {'sigmoid': 6, 'gelu': 2}, 'Native activation kind mix changed')
        video_tokens = 64 if number == 1 else 256
        expected_shapes = {'sigmoid': [[1, video_tokens, 32]] * 3 + [[1, 26, 32]] * 3,
                           'gelu': [[1, video_tokens, 16384], [1, 26, 8192]]}
        for kind in ('sigmoid', 'gelu'):
            selected = [r for r in activations if r.get('kind') == kind]
            require(all(isinstance(r.get('input'), dict) for r in selected) and
                    sorted(r['input'].get('shape', []) for r in selected) == sorted(expected_shapes[kind]),
                    'Native activation shape census changed')
            for r in selected:
                metadata = r['input']
                shape = metadata['shape']
                require(metadata.get('dtype') == 'torch.bfloat16' and metadata.get('device') == device and
                        metadata.get('contiguous') is True and metadata.get('stride') ==
                        [shape[1] * shape[2], shape[2], 1], 'Native activation precision/device/layout changed')
                require((kind == 'gelu' and r.get('approximate') == 'tanh') or
                        (kind == 'sigmoid' and 'approximate' not in r), 'Native activation approximation changed')
        files = {'receipt': sha(path)}
        for phase in ('before', 'after'):
            graph_path = safe_path(directory / f'graph-{number:03d}-{phase}.py')
            require(graph_path.is_file(), 'Native RMS graph source missing')
            files[phase] = sha(graph_path)
        records.append({'graph': number, 'replacements': replacements, 'activation_replacements': activations, 'files': files})
    return records


def _metadata(row, shape, device):
    require(isinstance(row, dict) and row.get('shape') == shape and
            all(type(x) is int for x in row['shape']) and
            row.get('dtype') == 'torch.bfloat16' and row.get('device') == device,
            'Native tensor shape/device/precision changed')
    stride = row.get('stride')
    require(isinstance(stride, list) and len(stride) == len(shape) and
            all(type(x) is int and x >= 0 for x in stride), 'Invalid tensor stride')


def _census(row, index, device):
    records = row.get('records') if isinstance(row, dict) else None
    require(isinstance(records, list) and len(records) == 84 and
            all(isinstance(r, dict) and isinstance(r.get('name'), str) for r in records) and
            len({r['name'] for r in records}) == 84, 'Native state census identities changed')
    for r in records:
        shape = r.get('shape')
        require(isinstance(shape, list) and all(_positive(x) for x in shape), 'Invalid state shape')
        _metadata(r, shape, device)
        require(r.get('kind') in ('parameter', 'buffer') and _positive(r.get('tensor_id')) and
                type(r.get('bytes')) is int and r['bytes'] == 2 * math.prod(shape),
                'Native state size/type changed')
    require(type(row.get('bytes')) is int and
            sum(r['bytes'] for r in records) == row['bytes'] == 773349760 and
            type(row.get('block_index')) is int and row['block_index'] == index and
            row.get('route_device') == device, 'Native state census size/placement changed')
    require(all(_positive(row.get(k)) for k in ('block_id', 'diffusion_id', 'owner_id', 'container_id')) and
            row.get('registration') == ('_ltx_primary_blocks' if index < 21 else 'blocks') and
            type(row.get('slot')) is int and row['slot'] == (index if index < 21 else index - 21),
            'Native state registered ownership changed')


def _exact_outputs(rows, shapes, device):
    require(isinstance(rows, list) and len(rows) == 2, 'Missing native output comparisons')
    for row, name, shape in zip(rows, ('video', 'audio'), shapes):
        require(isinstance(row, dict) and row.get('output') == name and
                all(row.get(k) is True for k in ('finite', 'metadata_equal', 'bitwise_equal')) and
                type(row.get('unequal_bytes')) is int and row['unequal_bytes'] == 0 and
                _digest(row.get('expected_sha256')) and
                row['expected_sha256'] == row.get('actual_sha256'), 'Native output parity failed')
        _metadata(row, shape, device)
        _metadata(row.get('expected'), shape, device)


def validate_compiler_receipts(server_run, run, mode, selection, identity_sha, qualified_before):
    """Validate one completed request; caller binds identity across requests."""
    require(isinstance(run, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run),
            'Unsafe request name')
    require(selection in SELECTIONS and mode in ('original', 'compiled', 'restored') and
            type(qualified_before) is int and qualified_before in (0, 2) and _digest(identity_sha),
            'Invalid mode/selection/qualification/identity')
    require(mode != 'restored' or qualified_before == 2, 'Restored selection is not qualified')
    indices = SELECTIONS[selection]
    directory = safe_path(Path(server_run) / ('compiler-' + run))
    request = read_json(directory / 'request.json')

    def bound(row, schema, index=None):
        require(isinstance(row, dict) and row.get('schema') == schema and
                row.get('run_name') == run and row.get('selection') == selection and
                row.get('server_identity_sha256') == identity_sha and
                row.get('model_verification_sha256') == MODEL_SHA and
                row.get('passed') is True and row.get('failures') == [], 'Receipt identity/status failed')
        if index is not None:
            require(type(row.get('block_index')) is int and row['block_index'] == index,
                    'Receipt block index changed')

    bound(request, 'ltx.multiblock-request.v1')
    require(request.get('mode') == mode and request.get('block_indices') == list(indices) and
            all(type(i) is int for i in request['block_indices']) and
            request.get('extension_sha256s') == EXTENSIONS and
            _exact_config(request.get('compiler_options'), NATIVE_RMS_OPTIONS),
            'Request selection/extensions/options changed')
    limits = request.get('dynamo_limits')
    require(isinstance(limits, dict) and all(type(v) is int for v in limits.values()) and
            limits == {'recompile_limit': 8, 'accumulated_recompile_limit': 256},
            'Actual Dynamo limits changed')
    expected_qualified = {str(i): qualified_before for i in indices}
    for field in ('qualified_before', 'qualified_stage_counts'):
        values = request.get(field)
        require(isinstance(values, dict) and all(type(v) is int for v in values.values()) and
                values == expected_qualified, 'Request qualification map changed')
    require(_positive(request.get('original_id')), 'Invalid original owner')
    candidate = request.get('candidate_id')
    absent = mode == 'original' and qualified_before == 0
    require((candidate is None if absent else _positive(candidate) and candidate != request['original_id']),
            'Invalid retained candidate owner')
    retained = request.get('retained_candidate_count')
    require(type(retained) is int and 0 <= retained <= 3 and
            (absent or retained >= 1), 'Invalid retained candidate bound')
    names = {p.name for p in directory.iterdir()}
    if mode != 'compiled':
        require(names == {'request.json'}, 'Original/restored request contains compiled receipts')
        return {'request': request, 'blocks': {}}
    require(names == {'request.json', *(f'block-{i:02d}' for i in indices)},
            'Request block directory coverage changed')
    graph_root = safe_path(Path(server_run) / ('native-multiblock-' + selection))
    require({p.name for p in graph_root.iterdir()} == {f'block-{i:02d}' for i in indices},
            'Native graph block coverage changed')
    blocks = {}
    for index in indices:
        device = f'xpu:{0 if index < 21 else 1}'
        block_dir = safe_path(directory / f'block-{index:02d}')
        require({p.name for p in block_dir.iterdir()} == {f'call-{n:02d}.json' for n in range(1, 12)},
                'Expected exactly eleven completed calls per selected block')
        graph_dir = safe_path(graph_root / f'block-{index:02d}')
        graphs = validate_native_operation_receipts(graph_dir, device)
        hashes = [{'graph': g['graph'], 'files': g['files']} for g in graphs]
        reports = []
        for number in range(1, 12):
            row = read_json(block_dir / f'call-{number:02d}.json')
            bound(row, 'ltx.multiblock-call.v1', index)
            require(type(row.get('call')) is int and row['call'] == number, 'Call ordering changed')
            shapes = [[1, 64 if number <= 8 else 256, 4096], [1, 26, 2048]]
            signature = row.get('stage_signature')
            require(isinstance(signature, list) and len(signature) == 2, 'Missing stage signature')
            for meta, shape in zip(signature, shapes):
                _metadata(meta, shape, device)
            new_stage = qualified_before == 0 and number in (1, 9)
            require(type(row.get('stage_check')) is bool and row['stage_check'] == new_stage,
                    'Cold/warm stage check changed')
            qualified = 1 if qualified_before == 0 and number <= 8 else 2
            require(type(row.get('qualified_stage_count')) is int and
                    row['qualified_stage_count'] == qualified, 'Incomplete stage qualification')
            delta = row.get('counter_delta')
            require(isinstance(delta, dict) and all(isinstance(v, dict) and
                    all(type(n) is int and n >= 0 for n in v.values()) for v in delta.values()),
                    'Invalid per-call counter delta')
            require(sum(delta.get('graph_break', {}).values()) == 0 and
                    sum(delta.get('unimplemented', {}).values()) == 0 and
                    delta.get('stats', {}).get('unique_graphs', 0) == int(new_stage),
                    'Graph break, fallback or unexpected recompile')
            if new_stage:
                for field in ('eager_vs_compiled', 'compiled_vs_repeat'):
                    _exact_outputs(row.get(field), shapes, device)
            else:
                require('eager_vs_compiled' not in row and 'compiled_vs_repeat' not in row,
                        'Unexpected warm comparison evidence')
            if number == 1:
                _census(row.get('state_census'), index, device)
            else:
                require(row.get('state_census') is None, 'Unexpected repeated state census')
            if new_stage or number == 11:
                require(row.get('native_graphs') == hashes[:qualified], 'Native graph evidence drift')
            else:
                require('native_graphs' not in row, 'Unexpected native graph evidence')
            reports.append(row)
        blocks[str(index)] = {'calls': reports, 'native_operation_graphs': graphs}
    return {'request': request, 'blocks': blocks}
