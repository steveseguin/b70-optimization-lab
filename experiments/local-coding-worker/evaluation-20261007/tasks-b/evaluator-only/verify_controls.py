#!/usr/bin/env python3
"""Evaluator-only: verify historical baseline failures and fixed-commit controls."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_CAP = 32 * 1024 * 1024


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, default=Path('/home/steve/llm-optimizations'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    cases = json.loads((ROOT/'evaluator-only/provenance.json').read_text())['cases']
    results = []
    for case in cases:
        for role, commit in [('baseline',case['baseline_commit']), ('fixed',case['fixed_commit'])]:
            listing = subprocess.check_output(
                ['git','-C',str(args.repo),'ls-tree','-rlz',commit,'--',*case['snapshot_paths']],
                timeout=30)
            entries = [entry.split(b'\t',1)[0].split() for entry in listing.split(b'\0') if entry]
            if not entries or any(fields[1] != b'blob' for fields in entries):
                raise RuntimeError('Expected a nonempty selection of ordinary Git blobs')
            source_bytes = sum(int(fields[3]) for fields in entries)
            if source_bytes + 4096 * len(entries) + 10240 > ARCHIVE_CAP:
                raise RuntimeError('Scoped archive exceeds the 32 MiB admission limit')
            archive = subprocess.check_output(['git','-C',str(args.repo),'archive','--format=tar',commit,
                                               '--',*case['snapshot_paths']],timeout=30)
            if len(archive) > ARCHIVE_CAP:
                raise RuntimeError('Scoped archive exceeds the 32 MiB limit')
            with tempfile.TemporaryDirectory(prefix='coding-eval-b-') as tmp:
                tree = Path(tmp)
                with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
                    # Trusted local Git archive; fail if a source member tries to escape.
                    for member in stream:
                        target = tree/member.name
                        assert target.resolve().is_relative_to(tree)
                        assert member.isfile() or member.isdir(), member.name
                        stream.extract(member,tree)
                assert not (tree/'.git').exists()
                files = {str(p.relative_to(tree)):hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in tree.rglob('*') if p.is_file()}
                completed = subprocess.run([sys.executable,'-B',str(ROOT/'acceptance'/case['acceptance'])],
                                           cwd=tree,capture_output=True,text=True,timeout=30)
            stem = case['task_id']+'.'+role
            (args.out/(stem+'.stdout')).write_text(completed.stdout)
            (args.out/(stem+'.stderr')).write_text(completed.stderr)
            text = completed.stdout+completed.stderr
            passed = completed.returncode == 0 if role == 'fixed' else (
                completed.returncode != 0 and case['expected_marker'] in text)
            row = {'task':case['task_id'],'role':role,'commit':commit,
                   'snapshot_scope':case['snapshot_paths'],'archive_bytes':len(archive),
                   'source_bytes':source_bytes,'archive_cap_bytes':ARCHIVE_CAP,
                   'archive_sha256':hashlib.sha256(archive).hexdigest(),'files':files,
                   'returncode':completed.returncode,'control_passed':passed,
                   'expected_baseline_marker':case['expected_marker'],
                   'stdout':stem+'.stdout','stderr':stem+'.stderr','git_metadata_present':False}
            results.append(row)
            print(stem,completed.returncode,'PASS' if passed else 'FAIL',flush=True)
            if not passed: print(text[-2500:],flush=True)
    receipt = {'schema':'coding-evaluation.historical-controls.v1',
               'all_controls_passed':all(r['control_passed'] for r in results),
               'scope':'selected exact Git archive paths; no .git; CPU-only, transport mocked',
               'model_trials_run':False,'results':results,
               'acceptance_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in (ROOT/'acceptance').glob('*.py')}}
    (args.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return 0 if receipt['all_controls_passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
