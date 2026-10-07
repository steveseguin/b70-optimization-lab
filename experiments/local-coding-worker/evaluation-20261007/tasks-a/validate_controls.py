#!/usr/bin/env python3
"""Replay frozen CPU controls in bounded scoped git archives. Never call a model or container."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
LIMIT = 32 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    args = parser.parse_args()
    results = []
    for receipt_path in sorted((HERE / 'validation').glob('*.json')):
        receipt = json.loads(receipt_path.read_text())
        ident = receipt['id']
        task_path = HERE / (ident + '.json')
        task = json.loads(task_path.read_text())
        acceptance = HERE / 'acceptance' / receipt['acceptance_file']
        assert sha(task_path.read_bytes()) == receipt['task_sha256'], 'task changed: ' + ident
        assert sha(acceptance.read_bytes()) == receipt['acceptance_sha256'], 'acceptance changed: ' + ident
        assert sha((HERE / 'validation' / (ident + '.gold.patch')).read_bytes()) == receipt['gold_patch_sha256']
        assert task['source_commit'] == receipt['baseline_commit']
        python = 'node' if acceptance.suffix == '.cjs' else 'python3'
        paths = receipt['validation_paths']
        assert paths and all(not p.startswith('/') and '..' not in Path(p).parts for p in paths)
        for role, commit in [('baseline', receipt['baseline_commit']), ('fixed', receipt['fixed_commit'])]:
            # Write directly to a temporary file: no full-tree archive or source checkout.
            with tempfile.TemporaryDirectory(prefix='worker-eval-a-control-') as temp:
                temp = Path(temp)
                archive_path = temp / 'source.tar'
                with archive_path.open('wb') as stream:
                    subprocess.run(['git', '-C', str(args.repo.resolve()), 'archive', '--format=tar', commit,
                                    '--', *paths], stdout=stream, check=True, timeout=30)
                assert archive_path.stat().st_size <= LIMIT, 'scoped archive exceeds 32 MiB'
                data = archive_path.read_bytes()
                assert sha(data) == receipt['runs'][role]['archive_sha256'], 'source archive changed'
                tree = temp / 'source'; tree.mkdir()
                with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                    members = archive.getmembers()
                    assert sum(member.size for member in members) <= LIMIT, 'extracted source exceeds 32 MiB'
                    assert all(member.isdir() or member.isfile() for member in members), 'unexpected archive type'
                    archive.extractall(tree, filter='data')
                run = subprocess.run([python, str(acceptance)], cwd=tree, text=True,
                                     capture_output=True, timeout=35)
            passed = (run.returncode == 0) if role == 'fixed' else (
                run.returncode != 0 and task['expected_baseline_error'] in run.stdout + run.stderr)
            results.append({'id': ident, 'control': role, 'passed': passed, 'returncode': run.returncode,
                            'archive_bytes': len(data), 'stdout': run.stdout, 'stderr': run.stderr})
    print(json.dumps({'schema': 'lab.worker-task-controls-replay.v1', 'checks': results,
                      'passed': len(results) == 8 and all(row['passed'] for row in results)}, indent=2))
    return 0 if len(results) == 8 and all(row['passed'] for row in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
