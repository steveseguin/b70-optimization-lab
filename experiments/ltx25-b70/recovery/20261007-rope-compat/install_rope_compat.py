"""Restore one pinned eager RoPE function's old arithmetic in this process only.

Call after normal comfy.quant_ops initialization, before model/graph construction.
No backend settings, package files, registry registrations or other arithmetic change.
"""
import ast
import hashlib
import marshal
from pathlib import Path
import sys
import types

HERE = Path(__file__).resolve().parent
NEW_PATH = Path('/home/steve/ltx25-upstream99-dependencies/site-packages/comfy_kitchen/backends/eager/rope.py')
OLD_SHA = 'aee33a18bb5fe75ce24ebad389b830c9d5775d52723fc7df4864598547b2257c'
NEW_SHA = '630a3d287bf602046935086f9d43eb6db2ec4971913a1cb3fb35bae6ea4ac9ee'
FUNCTION = 'apply_rope_split_half1'
HELPERS = (FUNCTION, 'apply_rope_split_half', 'apply_rope_split_half1_', 'apply_rope_split_half_')
_INSTALLED = False


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path):
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe source path')
    return path.read_bytes()


def code_identity(code):
    constants = tuple(code_identity(c) if isinstance(c, types.CodeType) else c for c in code.co_consts)
    normalized = code.replace(co_filename='', co_firstlineno=1, co_linetable=b'', co_consts=constants)
    return digest(marshal.dumps(normalized))


def definitions(raw, filename, torch):
    tree = ast.parse(raw, filename=filename)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in HELPERS]
    require({n.name for n in nodes} == set(HELPERS), 'Missing/duplicate pinned helpers')
    # Compile the full module, but execute no module-level code/imports. Python's
    # module import knowledge can alter call opcodes; isolated AST compilation
    # would falsely disagree with the same function loaded from the full module.
    module_code = compile(raw, filename, 'exec', dont_inherit=True, optimize=0)
    codes = [c for c in module_code.co_consts if isinstance(c, types.CodeType) and c.co_name in HELPERS]
    require(len(codes) == len(HELPERS), 'Missing/duplicate compiled helpers')
    return {c.co_name: types.FunctionType(c, {'torch': torch}, c.co_name) for c in codes}



def install():
    global _INSTALLED
    require(not _INSTALLED, 'RoPE compatibility already installed; repeat refused')
    require('comfy.quant_ops' in sys.modules, 'Normal Comfy quant_ops initialization must precede RoPE compatibility')
    torch = sys.modules.get('torch')
    ck = sys.modules.get('comfy_kitchen')
    rope = sys.modules.get('comfy_kitchen.backends.eager.rope')
    eager = sys.modules.get('comfy_kitchen.backends.eager')
    require(all(x is not None for x in (torch, ck, rope, eager)), 'Expected modules not loaded')
    require(sys.modules['comfy.quant_ops'].ck is ck, 'Foreign quant_ops kitchen binding')
    require(str(torch.__version__) == '2.14.0+xpu', 'Unexpected Torch version')
    require(Path(rope.__file__).resolve() == NEW_PATH and digest(regular(NEW_PATH)) == NEW_SHA, 'Unexpected loaded RoPE source')
    old_path = HERE/'source-evidence/rope-0.2.33.py'
    new_path = HERE/'source-evidence/rope-0.2.37.py'
    old_raw, new_raw = regular(old_path), regular(new_path)
    require(digest(old_raw) == OLD_SHA and digest(new_raw) == NEW_SHA, 'Pinned source evidence changed')
    old, new = definitions(old_raw, str(old_path), torch), definitions(new_raw, str(new_path), torch)
    registry = ck.registry
    require(rope.torch is torch and rope.registry is registry and eager.registry is registry
            and sys.modules['comfy_kitchen.registry'].registry is registry, 'Foreign global module binding')
    require(registry._backends.get('eager') is eager and registry.is_available('eager'), 'Foreign/unavailable eager owner')
    require(getattr(registry._thread_local, 'backend_override', None) is None, 'Thread backend override refused')
    require('eager' in registry._priority, 'Missing eager priority')
    before_eager = registry._priority[:registry._priority.index('eager')]
    require(not any(registry.is_available(n) for n in before_eager), 'Non-eager backend routing refused')
    for name in HELPERS:
        actual = getattr(rope, name)
        require(getattr(eager, name) is actual and actual.__globals__ is rope.__dict__, 'Foreign helper alias/owner: '+name)
        require(code_identity(actual.__code__) == code_identity(new[name].__code__), 'Loaded helper bytecode changed: '+name)
        require(registry.get_constraints('eager', name) is not None, 'Missing eager registry contract: '+name)
    actual = getattr(rope, FUNCTION)
    require(not actual.__closure__ and not old[FUNCTION].__code__.co_freevars, 'Unexpected closure')
    before_code = code_identity(actual.__code__)
    # Preserve function object and all existing aliases/registrations. Its unchanged
    # globals contain torch; higher split-half helpers resolve this same object.
    actual.__code__ = old[FUNCTION].__code__
    _INSTALLED = True
    require(code_identity(actual.__code__) == code_identity(old[FUNCTION].__code__), 'Restoration verification failed')
    return dict(schema='ltx.rope-arithmetic-compat.v1', status='installed-unqualified',
                installer_sha256=digest(regular(Path(__file__).resolve())), source_path=str(NEW_PATH),
                original_source_sha256=NEW_SHA, restored_source_sha256=OLD_SHA,
                function=FUNCTION, before_code_sha256=before_code, after_code_sha256=code_identity(actual.__code__),
                backend='eager', aliases_preserved=list(HELPERS), package_files_changed=False,
                scope='one process-local function code replacement; no exception interception',
                gpu_parity_qualified=False)
