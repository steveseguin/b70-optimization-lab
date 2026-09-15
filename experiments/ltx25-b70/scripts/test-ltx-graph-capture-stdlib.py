#!/usr/bin/env python3
"""CPU-only tests for the graph adapter's structure walk, mirror and signature.

No XPU, no ComfyUI model, no server. These check the invariant the capture path
depends on: `walk` and `mirror` agree on which tensors exist and in what order,
so filling static buffers by zip() cannot cross-assign or miss one.
"""
import sys, json, types
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import torch


class FakeMask:
    def __init__(self, a, b, flag):
        self.mask, self.bias, self.flag = a, b, flag


class Compressed:
    """Mirrors the real CompressedTimestep: __slots__, so no __dict__ at all."""
    __slots__ = ('data', 'batch_size', 'num_frames', 'patches_per_frame', 'feature_dim')

    def __init__(self, data, patches):
        self.data, self.patches_per_frame = data, patches
        self.batch_size, self.num_frames, self.feature_dim = data.shape


class SlottedMask:
    """Mirrors the real GuideAttentionMask: __slots__ holding several tensors."""
    __slots__ = ('guide_start', 'tracked_count', 'noisy_mask', 'tracked_mask')

    def __init__(self, start, count, noisy, tracked):
        self.guide_start, self.tracked_count = start, count
        self.noisy_mask, self.tracked_mask = noisy, tracked


def load_helpers():
    """Import only the pure helpers; the module's comfy imports are not needed."""
    src = Path(__file__).resolve().parent / 'ltx_graph_capture.py'
    text = src.read_text()
    start = text.index('SCALARS = (')
    end = text.index('class Entry:')
    body = 'import copy, hashlib, torch\n' + text[start:end]
    body = body.replace('def require(condition, message):', '', 1)
    ns = {}
    exec(compile('''import copy, hashlib, torch\nimport types as _types\nCACHE_KEY = '_ltx_layer_shard_forward_transfers'
def require(condition, message):
    if not condition:
        raise RuntimeError(message)
''' + text[start:end], str(src), 'exec'), ns)
    return ns


H = load_helpers()
walk, mirror, describe = H['walk'], H['mirror'], H['describe']
split_options, describe_identity = H['split_options'], H['describe_identity']
option_census = H['option_census']
CACHE_KEY = '_ltx_layer_shard_forward_transfers'
static_like, fill_static, attribute_names = H['static_like'], H['fill_static'], H['attribute_names']
results = []


def case(name, fn):
    try:
        fn()
        results.append({'case': name, 'status': 'passed'})
    except Exception as error:
        results.append({'case': name, 'status': 'FAILED', 'error': repr(error)})


def sample():
    return {
        'img': (torch.randn(1, 64, 8), torch.randn(1, 26, 4)),
        'v_context': torch.randn(1, 12, 8),
        'attention_mask': FakeMask(torch.ones(1, 5), torch.zeros(2), True),
        'v_timestep': Compressed(torch.randn(1, 3, 8), 4),
        'a_pe': (torch.randn(2, 4), torch.randn(2, 4)),
        'self_attention_mask': SlottedMask(3, 2, torch.randn(1, 1, 1, 9), torch.randn(1, 1, 2, 9)),
        'a_prompt_timestep': None,
        'opts': {'run_vx': True, 'run_ax': False, 'aux': torch.randn(3)},
    }


def test_walk_finds_every_tensor():
    s = sample()
    found = []
    walk(s, found, 'root')
    assert len(found) == 11, len(found)


def test_mirror_preserves_walk_order():
    s = sample()
    a, b = [], []
    walk(s, a, 'root')
    m = mirror(s, lambda t: t.clone() + 1)
    walk(m, b, 'root')
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert x.shape == y.shape and x.dtype == y.dtype
        assert torch.equal(y, x + 1), 'mirror paired the wrong tensors'


def test_mirror_is_structural_not_shared():
    s = sample()
    m = mirror(s, static_like)
    flat_s, flat_m = [], []
    walk(s, flat_s, 'r'); walk(m, flat_m, 'r')
    for x, y in zip(flat_s, flat_m):
        assert x is not y and torch.equal(x, y)
    assert m['attention_mask'].flag is True
    assert m['v_timestep'].patches_per_frame == 4
    assert m['opts']['run_ax'] is False
    assert m['a_prompt_timestep'] is None
    assert m['self_attention_mask'].guide_start == 3


def test_fill_by_zip_round_trips():
    s = sample()
    m = mirror(s, static_like)
    flat_m = []; walk(m, flat_m, 'r')
    new = sample()
    flat_n = []; walk(new, flat_n, 'r')
    assert len(flat_m) == len(flat_n)
    for buf, val in zip(flat_m, flat_n):
        if buf is not val:
            buf.copy_(val)
    check = []; walk(m, check, 'r')
    for got, want in zip(check, flat_n):
        assert torch.equal(got, want)


def test_describe_separates_shape_dtype_device():
    a = describe(torch.zeros(2, 3))
    assert a != describe(torch.zeros(3, 2))
    assert a != describe(torch.zeros(2, 3, dtype=torch.bfloat16))
    assert describe(None) != describe(0)
    assert describe({'a': 1}) != describe({'a': 2})
    assert describe(FakeMask(torch.ones(1), torch.ones(1), True)) != \
           describe(FakeMask(torch.ones(1), torch.ones(1), False))


def test_describe_is_order_independent_for_dicts():
    assert describe({'a': 1, 'b': 2}) == describe({'b': 2, 'a': 1})


def test_walk_refuses_unexplained_object():
    try:
        walk({'f': (lambda x: x)}, [], 'root')
    except RuntimeError as error:
        assert 'cannot mirror' in str(error)
        return
    raise AssertionError('a function was accepted')


def test_static_like_preserves_stride():
    t = torch.randn(4, 6).t()
    s = static_like(t)
    assert s.stride() == t.stride() and s.shape == t.shape and torch.equal(s, t)
    assert not s.is_contiguous()


def test_scalar_tensor_and_zero_dim():
    t = torch.tensor(3.5)
    s = static_like(t)
    assert s.shape == t.shape and torch.equal(s, t)
    found = []; walk({'t': t}, found, 'r')
    assert len(found) == 1





def test_slotted_objects_are_walked_and_mirrored():
    """The real CompressedTimestep and GuideAttentionMask declare __slots__ and
    have no __dict__; a __dict__-only walk silently misses their tensors."""
    obj = SlottedMask(3, 2, torch.randn(1, 1, 1, 9), torch.randn(1, 1, 2, 9))
    assert not hasattr(obj, '__dict__')
    found = []
    walk(obj, found, 'mask')
    assert len(found) == 2, found
    m = mirror(obj, lambda t: t.clone() + 1)
    assert m.guide_start == 3 and m.tracked_count == 2
    assert torch.equal(m.noisy_mask, obj.noisy_mask + 1)
    assert torch.equal(m.tracked_mask, obj.tracked_mask + 1)
    assert describe(obj) != describe(SlottedMask(4, 2, obj.noisy_mask, obj.tracked_mask))


def test_attribute_names_covers_slots_and_dict():
    obj = Compressed(torch.randn(1, 3, 8), 4)
    assert set(attribute_names(obj)) == {'data', 'batch_size', 'num_frames',
                                         'patches_per_frame', 'feature_dim'}
    assert attribute_names(FakeMask(torch.ones(1), torch.ones(1), True)) == ['bias', 'flag', 'mask']


def test_expanded_view_is_mirrored_with_identical_layout():
    base = torch.randn(1, 5)
    t = base.expand(4, 5)
    s = static_like(t)
    assert s.shape == t.shape and s.stride() == t.stride(), (s.stride(), t.stride())
    assert torch.equal(s, t)
    fresh = torch.randn(1, 5).expand(4, 5)
    fill_static(s, fresh)
    assert torch.equal(s, fresh), 'expanded static buffer did not track its source'


def test_fill_static_handles_plain_and_expanded_together():
    src = {'plain': torch.randn(2, 3), 'wide': torch.randn(1, 4).expand(3, 4)}
    mir = mirror(src, static_like)
    flat_m = []; walk(mir, flat_m, 'r')
    new = {'plain': torch.randn(2, 3), 'wide': torch.randn(1, 4).expand(3, 4)}
    flat_n = []; walk(new, flat_n, 'r')
    for buf, val in zip(flat_m, flat_n):
        fill_static(buf, val)
    for buf, val in zip(flat_m, flat_n):
        assert torch.equal(buf, val)


def test_error_messages_name_the_path_and_type():
    try:
        walk({'bad': (lambda x: x)}, [], 'root')
    except RuntimeError as error:
        assert 'root' in str(error) and 'function' in str(error).lower(), str(error)
    else:
        raise AssertionError('callable accepted by walk')
    try:
        describe({'bad': (lambda x: x)}, 'root')
    except RuntimeError as error:
        assert 'root' in str(error), str(error)
    else:
        raise AssertionError('callable accepted by describe')


def runtime_options():
    """The shape of the real runtime options bag that broke two packets."""
    def _verify_placement(p):
        return None
    class Route:
        def __init__(self, block): self.block = block
    block = torch.nn.Linear(4, 4)
    return {
        'run_vx': True, 'run_ax': True, 'a2v_cross_attn': True, 'v2a_cross_attn': True,
        'sample_sigmas': torch.linspace(1.0, 0.0, 5),
        'denoise_mask_function': (lambda x: x),
        'callbacks': {'on_pre_run': {'ltx_layer_shard': [_verify_placement]}},
        'wrappers': {'diffusion_model': {'ltx_layer_shard': [_verify_placement]}},
        'patches_replace': {'dit': {('double_block', 0): Route(block)}},
        CACHE_KEY: {},
    }


def test_split_options_separates_infrastructure():
    infra, data = split_options(runtime_options())
    assert set(infra) == {'callbacks', 'wrappers', 'patches_replace', CACHE_KEY}, sorted(infra)
    assert set(data) == {'run_vx', 'run_ax', 'a2v_cross_attn', 'v2a_cross_attn',
                         'sample_sigmas', 'denoise_mask_function'}, sorted(data)


def test_infrastructure_is_never_walked_for_tensors():
    """patches_replace reaches the model's own weights and a captured graph's
    own static buffers; mirroring them would be catastrophic."""
    infra, data = split_options(runtime_options())
    found = []
    walk(data, found, 'options', 'skip')
    assert len(found) == 1 and found[0].numel() == 5, found


def test_stray_callable_in_options_is_tolerated_not_refused():
    infra, data = split_options(runtime_options())
    m = mirror(data, static_like, 'skip')
    assert m['denoise_mask_function'] is data['denoise_mask_function']
    assert m['sample_sigmas'] is not data['sample_sigmas']
    assert torch.equal(m['sample_sigmas'], data['sample_sigmas'])
    a, b = [], []
    walk(data, a, 'o', 'skip'); walk(m, b, 'o', 'skip')
    assert len(a) == len(b) == 1


def test_options_walk_still_refuses_by_default():
    _, data = split_options(runtime_options())
    try:
        walk(data, [], 'options')
    except RuntimeError as error:
        assert 'denoise_mask_function' in str(error), str(error)
        return
    raise AssertionError('a callable was accepted under the strict policy')


def test_describe_identity_pins_infrastructure_by_identity():
    a = runtime_options(); b = runtime_options()
    ia, _ = split_options(a); ib, _ = split_options(b)
    assert describe_identity(ia) == describe_identity(ia)
    assert describe_identity(ia) != describe_identity(ib), 'rebuilt callbacks must not compare equal'


def test_describe_identity_without_id_is_stable_across_rebuilds():
    _, da = split_options(runtime_options())
    _, db = split_options(runtime_options())
    assert describe_identity(da, with_id=False) == describe_identity(db, with_id=False)
    db['run_vx'] = False
    assert describe_identity(da, with_id=False) != describe_identity(db, with_id=False)


def test_option_census_records_types_and_shapes():
    census = option_census(runtime_options())
    assert census["'sample_sigmas'"]['shape'] == [5]
    assert census["'callbacks'"]['keys'] == ["'on_pre_run'"]
    assert census["'run_vx'"]['value'] == 'True'



for name, fn in sorted((k, v) for k, v in list(globals().items())
                       if k.startswith('test_') and isinstance(v, types.FunctionType)):
    case(name, fn)

passed = sum(1 for r in results if r['status'] == 'passed')
print(json.dumps({'passed': passed, 'total': len(results), 'results': results}, indent=2))
sys.exit(0 if passed == len(results) else 1)
