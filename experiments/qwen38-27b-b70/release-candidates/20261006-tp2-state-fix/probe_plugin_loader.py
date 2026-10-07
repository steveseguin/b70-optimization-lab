#!/usr/bin/env python3
"""Probe an explicit loader source's two functions with fake entry points only.

No vLLM import, runtime plugin, weights or device access. This is a source-level
behavior probe, not the actual runtime's plugin integration test.
"""
import argparse
import ast
import hashlib
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import patch


def probe(source):
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in ('load_plugins_by_group', 'load_general_plugins')]
    if len(functions) != 2:
        raise ValueError('source must define each expected loader function exactly once')
    namespace = {'envs': SimpleNamespace(VLLM_PLUGINS=None), 'logger': logging.getLogger('loader-probe'),
                 'Callable': Callable, 'Any': Any, 'DEFAULT_PLUGINS_GROUP': 'vllm.general_plugins',
                 'plugins_loaded': False}
    # Only the selected function definitions are executed; module-level imports
    # (including vllm.envs) are not run. Source must be an inspected trusted file.
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<inspected-loader>', 'exec'), namespace)
    outcomes = {}
    for case in ('success', 'import_failure', 'register_failure', 'excluded'):
        called = []
        def register():
            called.append('register')
            if case == 'register_failure':
                raise RuntimeError('deliberate register failure')
        def load():
            if case == 'import_failure':
                raise ImportError('deliberate entrypoint import failure')
            return register
        entry = SimpleNamespace(name='b70_gdn_state_width', value='b70_gdn_state_width:register', load=load)
        namespace['plugins_loaded'] = False
        namespace['envs'].VLLM_PLUGINS = [] if case == 'excluded' else None
        raised = None
        with patch('importlib.metadata.entry_points', return_value=[entry]):
            try:
                namespace['load_general_plugins']()
            except Exception as exc:
                raised = type(exc).__name__
        outcomes[case] = {'register_called': bool(called), 'raised': raised}
    return {'schema': 'lab.vllm-loader-source-probe.v1',
            'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'scope': 'extracted source functions with fake entrypoints; not runtime qualification',
            'outcomes': outcomes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(probe(args.source.read_text()), indent=2))


if __name__ == '__main__':
    main()
