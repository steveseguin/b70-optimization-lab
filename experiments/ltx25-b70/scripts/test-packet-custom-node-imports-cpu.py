#!/usr/bin/env python3
"""CPU test: the packet generator's verify_custom_node_imports refuses a custom node whose
top-level import does not resolve inside the staging tree, and accepts one that does.
Packet 76 shipped a node importing a module the generator never copied; the sealed
startup check does not import custom nodes, so the server came up without the node."""
import importlib.util
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('prepare_graph_capture_runtime', HERE / 'prepare-graph-capture-runtime.py')
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

results = []
with tempfile.TemporaryDirectory() as tmp:
    staging = Path(tmp)
    (staging / 'source/scripts').mkdir(parents=True)
    (staging / 'source/scripts/shipped_helper.py').write_text('X = 1\n')
    good = staging / 'source/custom_nodes/good_lab'
    good.mkdir(parents=True)
    good.joinpath('__init__.py').write_text('import json\nimport shipped_helper\nfrom shipped_helper import X\n')
    gen.verify_custom_node_imports(staging)
    results.append(('shipped helper accepted', True))

    bad = staging / 'source/custom_nodes/bad_lab'
    bad.mkdir()
    bad.joinpath('__init__.py').write_text('import json\nimport helper_never_copied\n')
    try:
        gen.verify_custom_node_imports(staging)
        results.append(('missing helper refused', False))
    except SystemExit as error:   # require() exits with the message
        results.append(('missing helper refused', 'helper_never_copied' in str(error)))
    except Exception as error:
        results.append(('missing helper refused', 'helper_never_copied' in str(error)))
for name, ok in results:
    print(f'{"ok " if ok else "BAD"} {name}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok in results))
