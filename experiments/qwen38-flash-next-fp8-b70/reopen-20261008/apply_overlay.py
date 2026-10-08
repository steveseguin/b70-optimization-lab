#!/usr/bin/env python3
"""Hash-bound whole-file Screen 1b overlay; no vLLM/torch import or installs.

Verify ALL input/output bytes before changing a container's Python tree. A
modified base file is a refusal, not an invitation to patch approximately.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise RuntimeError(f'unsafe overlay path: {value}')
    return path


def load_manifest(package=HERE):
    manifest = json.loads((package / 'overlay-manifest.json').read_text())
    if manifest.get('schema') != 'neural.download.screen1b-overlay.v1':
        raise RuntimeError('unsupported overlay manifest')
    return manifest


def verify_package(package=HERE):
    package = Path(package)
    manifest = load_manifest(package)
    if set(manifest['files']) != set(manifest['replacements']):
        raise RuntimeError('overlay file/replacement inventory differs')
    for rel, expected in manifest['files'].items():
        path = package / manifest['source'] / safe_relative(rel)
        if path.is_symlink() or not path.is_file() or digest(path) != expected:
            raise RuntimeError(f'overlay payload drift: {rel}')
        if manifest['replacements'][rel]['sha256'] != expected:
            raise RuntimeError(f'overlay output pin disagrees: {rel}')
    for rel, expected in manifest.get('support_files', {}).items():
        path = package / safe_relative(rel)
        if path.is_symlink() or not path.is_file() or digest(path) != expected:
            raise RuntimeError(f'overlay support-file drift: {rel}')
    return manifest


def apply_overlay(root, package=HERE, *, check_only=False):
    root, package = Path(root).resolve(), Path(package).resolve()
    manifest = verify_package(package)
    changes = []
    for rel, pin in manifest['replacements'].items():
        dest = root / safe_relative(rel)
        # Do not follow links out of the supplied Python package tree.
        if dest.is_symlink() or root not in dest.resolve().parents:
            raise RuntimeError(f'unsafe overlay destination: {rel}')
        if dest.exists() and not dest.is_file():
            raise RuntimeError(f'base drift: non-file destination: {rel}')
        actual = digest(dest) if dest.is_file() else None
        if actual == pin['sha256']:
            continue  # Idempotent recheck, including output hashes.
        if actual != pin['base_sha256']:
            raise RuntimeError(f'base drift: {rel}: expected {pin["base_sha256"]}, got {actual}')
        changes.append((rel, dest))
    # No partial application on any validation failure above. Replacements are
    # same-directory atomic renames; receipt is emitted only after all rehashes.
    if not check_only:
        for rel, dest in changes:
            dest.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix='.screen1b-', dir=dest.parent)
            try:
                with os.fdopen(fd, 'wb') as f:
                    f.write((package / manifest['source'] / rel).read_bytes())
                    f.flush()
                    os.fsync(f.fileno())
                os.chmod(tmp, 0o644)
                os.replace(tmp, dest)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        for rel, pin in manifest['replacements'].items():
            if digest(root / rel) != pin['sha256']:
                raise RuntimeError(f'installed overlay drift: {rel}')
    return {'schema': manifest['schema'], 'files': len(manifest['files']),
            'changed': len(changes), 'check_only': check_only,
            'manifest_sha256': digest(package / 'overlay-manifest.json'),
            'base_commit': manifest['upstream'], 'root': str(root)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--package', default=HERE, type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(apply_overlay(args.root, args.package, check_only=args.check_only), indent=2))


if __name__ == '__main__':
    main()
