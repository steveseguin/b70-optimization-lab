"""CPU test helper (not in the packet): the sealed native guide nodes, executed on CPU.

Compiles, from the sealed packet's own source files and under their own file names, exactly
these definitions of comfy_extras/nodes_lt.py:

    _append_guide_attention_entry, conditioning_get_any_value, get_noise_mask, get_keyframe_idxs,
    LTXVAddGuide, LTXVAddLatentGuide, LTXVCropGuides

plus node_helpers.conditioning_set_values and the whole of
comfy/ldm/lightricks/symmetric_patchifier.py (torch + einops only). The V3 base class and
NodeOutput are stand-ins (`io.ComfyNode` is an empty class, `io.NodeOutput(*args).result == args`);
nothing else of ComfyUI is imported, so no device, model management or registry is touched.

`load(packet_source)` returns a namespace dict with those names. The tests use it to check the
token counts, masks and keyframe positions of the guide anchor against the sealed code, and
harness_runtime.py registers the two node classes as the native nodes the runtime pins.
"""
import ast
from pathlib import Path
import types

NODES_LT_NAMES = ('_append_guide_attention_entry', 'conditioning_get_any_value', 'get_noise_mask',
                  'get_keyframe_idxs', 'LTXVAddGuide', 'LTXVAddLatentGuide', 'LTXVCropGuides')


class _ComfyNode:
    pass


class NodeOutput:
    def __init__(self, *args, ui=None, expand=None, block_execution=None):
        self.result = args
        self.ui, self.expand, self.block_execution = ui, expand, block_execution


def _pick(path, names):
    tree = ast.parse(Path(path).read_bytes())
    body = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    found = {n.name for n in body}
    if found != set(names):
        raise RuntimeError('Sealed source lacks %s' % sorted(set(names) - found))
    return compile(ast.Module(body=body, type_ignores=[]), str(path), 'exec')


def load(source, filename_root=None):
    """source: the sealed packet's source/ directory. filename_root: compile under this source/
    directory's file names instead (the harness copies nodes_lt.py into its fake packet)."""
    import logging
    import torch
    source = Path(source)
    names_root = Path(filename_root) if filename_root else source
    patch_ns = {'__name__': 'symmetric_patchifier_cpu'}
    patch_path = source / 'comfy/ldm/lightricks/symmetric_patchifier.py'
    exec(compile(patch_path.read_bytes(), str(patch_path), 'exec'), patch_ns)
    helpers_ns = {'torch': torch}
    exec(_pick(source / 'node_helpers.py', ('conditioning_set_values',)), helpers_ns)
    node_helpers = types.SimpleNamespace(conditioning_set_values=helpers_ns['conditioning_set_values'])
    io = types.SimpleNamespace(ComfyNode=_ComfyNode, NodeOutput=NodeOutput)
    ns = {'__name__': 'nodes_lt_cpu', 'torch': torch, 'logging': logging, 'io': io, 'node_helpers': node_helpers,
          'SymmetricPatchifier': patch_ns['SymmetricPatchifier'],
          'latent_to_pixel_coords': patch_ns['latent_to_pixel_coords']}
    raw = (source / 'comfy_extras/nodes_lt.py').read_bytes()
    target = names_root / 'comfy_extras/nodes_lt.py'
    if target != source / 'comfy_extras/nodes_lt.py' and target.read_bytes() != raw:
        raise RuntimeError('Harness copy of nodes_lt.py differs from the sealed source')
    exec(_pick(target, NODES_LT_NAMES), ns)
    return ns
