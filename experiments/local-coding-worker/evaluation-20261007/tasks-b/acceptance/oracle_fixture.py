"""Independent CPU fixtures: exercise real CLI logic with HTTP transport replaced."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch


def load():
    spec = importlib.util.spec_from_file_location('oracle_subject',
        Path.cwd() / 'scripts/bench-openai-concurrency-oracle.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(module, extra=(), pinned=None):
    seen = []
    def transport(**kwargs):
        seen.append(kwargs['request_id'])
        return {'sha256': hashlib.sha256(b'ok').hexdigest(), 'token_ids': [31, 41],
                'completion_tokens': 2, 'tok_s_wall_full': 10.0, 'cached_tokens': 0}
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        args = ['oracle', '--base-url', 'http://invalid.local', '--model', 'fixture',
                '--suite', str(root/'suite.json'), '--concurrency', '1,2',
                '--repeats', '2', '--max-tokens', '2', '--out', str(root/'result.json')]
        if pinned is not None:
            (root/'pinned.json').write_text(json.dumps(pinned))
            args += ['--oracle-digests', str(root/'pinned.json')]
        args += list(extra)
        with patch.object(module._BASE, 'load_suite', return_value=(
                {'id': 'fixture'}, [{'id':'a', 'prompt':'alpha'}])), \
             patch.object(module._BASE, 'post_stream', side_effect=transport), \
             patch.object(module._BASE, 'cached_tokens', side_effect=lambda row: row.get('cached_tokens')), \
             patch.object(sys, 'argv', args), contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            try:
                code = module.main()
            except SystemExit as error:
                code = error.code
        result = json.loads((root/'result.json').read_text()) if (root/'result.json').exists() else None
        return code, result, seen


def pinned_rows(count):
    rows = []
    for index in range(count):
        prompt = 'alpha' + f'\n\n[Independent validation case {index:03d}; variant {index:02d}]'
        rows.append({'prompt_id':f'a-c{index:03d}',
                     'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
                     'sha256':hashlib.sha256(b'ok').hexdigest(),
                     'token_ids':[31,41], 'completion_tokens':2, 'cached_tokens':0})
    return {'rows':rows, 'cached_tokens_zero':True}
