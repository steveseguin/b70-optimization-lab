#!/usr/bin/env python3
"""AST-only manifest check; never imports torch, vLLM, or a comparator module."""
import argparse
import ast
import hashlib
import json
from pathlib import Path


def check(manifest, roots):
    counts = {f'U{i}': 0 for i in range(1, 8)}
    for row in manifest['symbols']:
        root = Path(roots[row['source_id']]).resolve()
        path = (root / row['file']).resolve()
        if not path.is_relative_to(root):
            raise ValueError('source path escapes root')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('source hash mismatch: ' + row['id'])
        tree = ast.parse(data)
        scope = tree if not row['class'] else next(
            n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == row['class'])
        fn = next(n for n in ast.walk(scope) if isinstance(n, ast.FunctionDef)
                  and n.name == row['method'] and n.lineno == row['line'])
        args = [a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs]
        if args != row['arguments']:
            raise ValueError('argument signature mismatch: ' + row['id'])
        for selector in row['inputs'] + row['outputs'] + row.get('state', []):
            parts = selector.split('.')
            if parts[0] == 'arg' and parts[1] not in args:
                raise ValueError('nonargument selector: ' + selector)
            if parts[0] not in ('arg', 'result'):
                raise ValueError('invalid selector')
        for u in row['u_rows']:
            counts[u] += 1
    return counts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--a367-root', type=Path, required=True)
    p.add_argument('--image-root', type=Path, required=True)
    p.add_argument('--manifest', type=Path, default=Path(__file__).with_name('names.json'))
    a = p.parse_args()
    print(json.dumps(check(json.loads(a.manifest.read_text()),
                           {'a367': a.a367_root, 'reopen-image': a.image_root}), sort_keys=True))


if __name__ == '__main__':
    main()
