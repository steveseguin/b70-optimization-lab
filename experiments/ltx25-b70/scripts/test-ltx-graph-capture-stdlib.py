#!/usr/bin/env python3
"""CPU-only tests for the graph adapter's structure walk, mirror and signature.

No XPU, no ComfyUI model, no server. These check the invariant the capture path
depends on: `walk` and `mirror` agree on which tensors exist and in what order,
so filling static buffers by zip() cannot cross-assign or miss one.
"""
import sys, json, types, uuid
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
    exec(compile('''import copy, hashlib, torch\nimport types as _types\nCACHE_KEY = '_ltx_layer_shard_forward_transfers'\nKEYWORDS = ('v_context', 'v_timestep')\nMAX_SIGNATURES_PER_BLOCK = 4
def require(condition, message):
    if not condition:
        raise RuntimeError(message)
''' + text[start:end], str(src), 'exec'), ns)
    return ns


H = load_helpers()
walk, mirror, describe = H['walk'], H['mirror'], H['describe']
split_options, signed_infrastructure = H['split_options'], H['signed_infrastructure']
describe_infrastructure, describe_option_data = H['describe_infrastructure'], H['describe_option_data']
attribute_names = H['attribute_names']
option_census, DeviceGroup = H['option_census'], H['DeviceGroup']
MAX_SIGNATURES_PER_BLOCK = H['MAX_SIGNATURES_PER_BLOCK']
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
        'uuid': uuid.uuid4(),
        'inner': {'nested': [uuid.uuid4(), torch.randn(2)]},
        'callbacks': {'on_pre_run': {'ltx_layer_shard': [_verify_placement]}},
        'wrappers': {'diffusion_model': {'ltx_layer_shard': [_verify_placement]}},
        'patches_replace': {'dit': {('double_block', 0): Route(block)}},
        CACHE_KEY: {},
    }


def test_split_options_separates_infrastructure():
    infra, data = split_options(runtime_options())
    assert set(infra) == {'callbacks', 'wrappers', 'patches_replace', CACHE_KEY}, sorted(infra)
    assert set(data) == {'run_vx', 'run_ax', 'a2v_cross_attn', 'v2a_cross_attn',
                         'sample_sigmas', 'denoise_mask_function', 'uuid', 'inner'}, sorted(data)


def test_infrastructure_is_never_walked_for_tensors():
    """patches_replace reaches the model's own weights and a captured graph's
    own static buffers; mirroring them would be catastrophic."""
    infra, data = split_options(runtime_options())
    found = []
    walk(data, found, 'options', 'skip')
    assert len(found) == 2 and sorted(t.numel() for t in found) == [2, 5], found


def test_stray_callable_in_options_is_tolerated_not_refused():
    infra, data = split_options(runtime_options())
    m = mirror(data, static_like, 'skip')
    assert m['denoise_mask_function'] is data['denoise_mask_function']
    assert m['sample_sigmas'] is not data['sample_sigmas']
    assert torch.equal(m['sample_sigmas'], data['sample_sigmas'])
    a, b = [], []
    walk(data, a, 'o', 'skip'); walk(m, b, 'o', 'skip')
    assert len(a) == len(b) == 2


def test_options_walk_still_refuses_by_default():
    _, data = split_options(runtime_options())
    try:
        walk(data, [], 'options')
    except RuntimeError as error:
        assert 'denoise_mask_function' in str(error), str(error)
        return
    raise AssertionError('a callable was accepted under the strict policy')


def test_describe_infrastructure_pins_by_identity():
    a = runtime_options(); b = runtime_options()
    ia, _ = split_options(a); ib, _ = split_options(b)
    assert describe_infrastructure(ia) == describe_infrastructure(ia)
    assert describe_infrastructure(ia) != describe_infrastructure(ib), 'rebuilt callbacks must not compare equal'


def test_describe_infrastructure_does_not_recurse_into_objects():
    """patches_replace reaches the model parameters and each route's own static
    buffers; recursing there would be enormous and self-referential."""
    class Deep:
        def __init__(self): self.buffers = [torch.randn(1000) for _ in range(3)]
    infra = {'patches_replace': {'dit': {('double_block', 0): Deep()}}}
    d = describe_infrastructure(infra)
    assert 'identity' in repr(d) and 'torch' not in repr(d), repr(d)[:200]


def test_option_data_signature_is_stable_across_requests():
    """A fresh uuid.UUID per request must not invalidate every captured graph,
    while a changed behavioural flag must."""
    _, da = split_options(runtime_options())
    _, db = split_options(runtime_options())
    assert da['uuid'] != db['uuid']
    assert describe_option_data(da) == describe_option_data(db)
    db['run_vx'] = False
    assert describe_option_data(da) != describe_option_data(db)


def test_option_data_signature_still_tracks_tensor_shape():
    _, da = split_options(runtime_options())
    db = dict(da); db['sample_sigmas'] = torch.linspace(1.0, 0.0, 9)
    assert describe_option_data(da) != describe_option_data(db)


def test_option_census_records_types_and_shapes():
    census = option_census(runtime_options())
    assert census["'sample_sigmas'"]['shape'] == [5]
    assert census["'callbacks'"]['keys'] == ["'on_pre_run'"]
    assert census["'run_vx'"]['value'] == 'True'


def test_uuid_and_other_tensorless_objects_pass_through():
    """uuid.UUID declares __weakref__ in __slots__ and is immutable; rebuilding
    it raised AttributeError and broke a whole packet."""
    u = uuid.uuid4()
    assert not attribute_names(u) or '__weakref__' not in attribute_names(u)
    m = mirror({'u': u}, static_like, 'skip')
    assert m['u'] is u
    found = []
    walk({'u': u}, found, 'r', 'skip')
    assert found == []


def test_tensorless_object_passes_through_under_strict_policy_too():
    u = uuid.uuid4()
    m = mirror({'u': u}, static_like)
    assert m['u'] is u


def test_object_holding_a_tensor_is_still_rebuilt():
    obj = SlottedMask(1, 1, torch.randn(2), torch.randn(3))
    m = mirror(obj, lambda t: t.clone() + 5)
    assert m is not obj and torch.equal(m.noisy_mask, obj.noisy_mask + 5)


def test_runtime_options_mirror_end_to_end():
    _, data = split_options(runtime_options())
    m = mirror(data, static_like, 'skip')
    a, b = [], []
    walk(data, a, 'o', 'skip'); walk(m, b, 'o', 'skip')
    assert len(a) == len(b) == 2, (len(a), len(b))
    for x, y in zip(a, b):
        assert x is not y and torch.equal(x, y)
    assert m['uuid'] is data['uuid']
    assert m['denoise_mask_function'] is data['denoise_mask_function']


def test_shard_transfer_cache_is_excluded_from_the_signature():
    """The shard's per-forward _move cache is keyed by (id(tensor), device), so
    signing it makes every block past the split re-capture on every step."""
    a = runtime_options()
    b = dict(a)                      # same infrastructure objects, new forward
    t1, t2 = torch.randn(3), torch.randn(3)
    a[CACHE_KEY] = {(id(t1), 'xpu:1'): (t1, t1.clone())}
    b[CACHE_KEY] = {(id(t2), 'xpu:1'): (t2, t2.clone())}
    ia, _ = split_options(a); ib, _ = split_options(b)
    assert describe_infrastructure(ia) != describe_infrastructure(ib), \
        'the unfiltered cache must differ, otherwise this test proves nothing'
    assert CACHE_KEY in ia and CACHE_KEY not in signed_infrastructure(ia)
    assert describe_infrastructure(signed_infrastructure(ia)) == \
           describe_infrastructure(signed_infrastructure(ib)), 'cache contents leaked into the signature'


def test_signed_infrastructure_still_pins_callbacks():
    a = runtime_options(); b = runtime_options()
    ia, _ = split_options(a); ib, _ = split_options(b)
    assert describe_infrastructure(signed_infrastructure(ia)) != \
           describe_infrastructure(signed_infrastructure(ib))


def group_call(vx, ax, vctx, vts, options):
    return {'img': (vx, ax), 'v_context': vctx, 'v_timestep': vts, 'transformer_options': options}


def test_device_group_reuses_the_signature_within_a_forward():
    """Describing eighteen arguments per block per step was itself measurable;
    every block on a device sees the same objects, so it is computed once."""
    g = DeviceGroup('xpu:0')
    opts = runtime_options()
    vx, ax = torch.randn(1, 4, 8), torch.randn(1, 2, 4)
    vctx, vts = torch.randn(1, 3, 8), torch.randn(1, 1, 8)
    r = group_call(vx, ax, vctx, vts, opts)
    k1 = g.key_for(r, opts)
    assert g.fresh_forward is True
    k2 = g.key_for(group_call(vx, ax, vctx, vts, opts), opts)
    assert g.fresh_forward is False and k2 is k1
    # a genuinely new forward supplies new activation objects
    k3 = g.key_for(group_call(vx.clone(), ax, vctx, vts, opts), opts)
    assert g.fresh_forward is True and k3 == k1


def test_shared_slot_copies_only_what_changed():
    g = DeviceGroup('xpu:0')
    opts = runtime_options()
    vx, ax = torch.randn(1, 4, 8), torch.randn(1, 2, 4)
    vctx, vts = torch.randn(1, 3, 8), torch.randn(1, 1, 8)
    r = group_call(vx, ax, vctx, vts, opts)
    key = g.key_for(r, opts)
    slot = g.slot_for(key, r, opts)
    first = g.fill(slot, r, opts)
    assert first > 0
    # a second block in the same forward sees the identical objects
    assert g.fill(slot, group_call(vx, ax, vctx, vts, opts), opts) == 0
    # and a later block receives the shared buffer itself as its input
    chained = group_call(slot.img[0], slot.img[1], vctx, vts, opts)
    assert g.fill(slot, chained, opts) == 0
    # only the activations change on the next step
    assert g.fill(slot, group_call(vx.clone(), ax.clone(), vctx, vts, opts), opts) == 2


def test_shared_slot_actually_tracks_new_values():
    g = DeviceGroup('xpu:0')
    opts = runtime_options()
    vx, ax = torch.randn(1, 4, 8), torch.randn(1, 2, 4)
    vctx, vts = torch.randn(1, 3, 8), torch.randn(1, 1, 8)
    r = group_call(vx, ax, vctx, vts, opts)
    slot = g.slot_for(g.key_for(r, opts), r, opts)
    g.fill(slot, r, opts)
    assert torch.equal(slot.img[0], vx)
    nvx = torch.randn(1, 4, 8)
    g.fill(slot, group_call(nvx, ax, vctx, vts, opts), opts)
    assert torch.equal(slot.img[0], nvx)


def test_device_group_refuses_runaway_shapes():
    g = DeviceGroup('xpu:0')
    opts = runtime_options()
    try:
        for n in range(3, 3 + MAX_SIGNATURES_PER_BLOCK + 2):
            vx, ax = torch.randn(1, n, 8), torch.randn(1, 2, 4)
            r = group_call(vx, ax, torch.randn(1, 3, 8), torch.randn(1, 1, 8), opts)
            g.slot_for(g.key_for(r, opts), r, opts)
    except RuntimeError as error:
        assert 'distinct argument shapes' in str(error)
        return
    raise AssertionError('unbounded slot creation was allowed')



for name, fn in sorted((k, v) for k, v in list(globals().items())
                       if k.startswith('test_') and isinstance(v, types.FunctionType)):
    case(name, fn)

passed = sum(1 for r in results if r['status'] == 'passed')
print(json.dumps({'passed': passed, 'total': len(results), 'results': results}, indent=2))
sys.exit(0 if passed == len(results) else 1)
