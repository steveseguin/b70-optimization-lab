#!/usr/bin/env python3
"""Export bounded follow-up receipts using the frozen safe archive writer."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
spec = importlib.util.spec_from_file_location('frozen_prefill_export', HERE / 'export-short-prefill-evidence.py')
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)
PROFILES = ('4b-tp2', '9b-tp2', '27b-int4-tp1')
TREES = ('baseline', 'final-control', 'baseline-strict', 'original-reference', 'profile-request')
SOURCES = ('bench-short-prefill.py', 'bench-prefill-followup.py', 'run-prefill-followup-stage.py',
           'profile-prefill-followup.py', 'summarize-prefill-followup.py',
           'export-short-prefill-evidence.py', 'export-prefill-followup-evidence.py',
           'test_bench_prefill_followup.py', 'test_summarize_prefill_followup.py',
           'verify-prefill-followup-evidence.py')


def run(root, out):
    root = root.absolute()
    if root.is_symlink() or not root.is_dir() or out.absolute() == root or root in out.absolute().parents:
        raise ValueError('require real raw root and separate archive output')
    out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 'neural.download.prefill-followup-evidence.v1',
                'raw_root': str(root), 'archives': [], 'source_files': [],
                'notes': ['Raw text receipts preserved; caches excluded.',
                          'Original profiler gzip bytes are preserved in separate trace archives after text/credential checks.',
                          'No GPU or server operations.']}
    archive.TREES = TREES
    for profile in (None, *PROFILES):
        if profile is not None and not (root / profile).is_dir():
            continue
        files = archive.select(root, profile)
        if files:
            manifest['archives'].append(archive.archive(root, files, out / ((profile or 'campaign') + '.tar.gz')))
        if profile is not None:
            traces = sorted((root / profile / 'profile').glob('*.pt.trace.json.gz'))
            traces += sorted((root / profile / 'profile').glob('*.txt'))
            if traces:
                original_safe_file = archive.safe_file
                def checked_trace(path, source_root):
                    if not path.name.endswith('.pt.trace.json.gz'):
                        return original_safe_file(path, source_root)
                    relative = path.relative_to(source_root)
                    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
                        raise ValueError('symlink trace rejected')
                    raw = path.read_bytes()
                    data = gzip.decompress(raw)
                    if len(raw) > archive.MAX_BYTES or len(data) > archive.MAX_BYTES:
                        raise ValueError('oversized trace')
                    if b'\x00' in data or archive.SECRET.search(data):
                        raise ValueError('invalid or credential-like trace')
                    parsed = json.loads(data.decode('utf-8'))
                    if not parsed.get('traceEvents'):
                        raise ValueError('empty profiler trace')
                    return relative.as_posix(), raw
                archive.safe_file = checked_trace
                try:
                    manifest['archives'].append(archive.archive(root, traces, out / (profile + '-traces.tar.gz')))
                finally:
                    archive.safe_file = original_safe_file
    sources = [HERE / name for name in SOURCES]
    sources += [HERE.parent / 'data/2026-09-13-prefill-followup-corpus.json',
                HERE.parent / 'data/2026-09-14-prefill-trace-analysis.json']
    for path in sources:
        data = path.read_bytes()
        manifest['source_files'].append({'repository_path': path.relative_to(REPO).as_posix(),
            'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'archives': len(manifest['archives']),
        'files': sum(len(a['files']) for a in manifest['archives']),
        'compressed_bytes': sum(a['bytes'] for a in manifest['archives'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run(args.raw_root, args.out)
