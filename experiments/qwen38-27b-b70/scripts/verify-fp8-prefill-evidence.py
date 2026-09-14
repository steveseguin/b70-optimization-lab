#!/usr/bin/env python3
"""Verify archived receipt hashes and recompute all published prefill baselines."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
spec = importlib.util.spec_from_file_location('followup_summary', HERE / 'summarize-fp8-prefill-focus.py')
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(packet):
    evidence = packet / 'evidence'
    manifest = json.loads((evidence / 'manifest.json').read_text())
    checked = 0
    for source in manifest['source_files']:
        path = REPO / source['repository_path']
        if not path.resolve().is_relative_to(REPO):
            raise ValueError('source outside repository')
        data = path.read_bytes()
        if len(data) != source['bytes'] or sha(data) != source['sha256']:
            raise ValueError(f'source identity differs: {source["repository_path"]}')
    with tempfile.TemporaryDirectory(prefix='prefill-followup-replay-') as temporary:
        root = Path(temporary)
        seen = set()
        for archive in manifest['archives']:
            path = evidence / archive['archive']
            if path.parent != evidence:
                raise ValueError('archive outside evidence directory')
            data = path.read_bytes()
            if len(data) != archive['bytes'] or sha(data) != archive['sha256']:
                raise ValueError(f'archive identity differs: {path.name}')
            expected = {entry['raw_relative_path']: entry for entry in archive['files']}
            with tarfile.open(path, 'r:gz') as tar:
                members = tar.getmembers()
                if len(members) != len(expected) or {m.name for m in members} != set(expected):
                    raise ValueError('archive member coverage differs')
                for member in members:
                    relative = PurePosixPath(member.name)
                    if not member.isfile() or relative.is_absolute() or '..' in relative.parts or member.name in seen:
                        raise ValueError('unsafe or duplicated archive member')
                    seen.add(member.name)
                    raw = tar.extractfile(member).read()
                    entry = expected[member.name]
                    if len(raw) != entry['bytes'] or sha(raw) != entry['sha256']:
                        raise ValueError(f'receipt identity differs: {member.name}')
                    target = root / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
                    checked += 1
        analysis = json.loads((HERE.parent / 'data/2026-09-14-fp8-prefill-trace-analysis.json').read_text())
        for source in analysis['source_files']:
            relative = Path(source['path']).relative_to(Path(manifest['raw_root']))
            raw = (root / relative).read_bytes()
            if len(raw) != source['bytes'] or sha(raw) != source['sha256']:
                raise ValueError('profiler analysis source identity differs')
        analysis_spec = importlib.util.spec_from_file_location('fp8_trace_replay', HERE / 'analyze-fp8-prefill-trace.py')
        analyzer = importlib.util.module_from_spec(analysis_spec)
        analysis_spec.loader.exec_module(analyzer)
        recomputed_analysis = analyzer.analyze(root)
        for source in recomputed_analysis['source_files']:
            source['path'] = str(Path(manifest['raw_root']) / source['raw_relative_path'])
        summary.same(analysis, recomputed_analysis, 'archived trace analysis differs')
        trace_hashes = json.loads((root / '27b-fp8/profile-trace-hashes.json').read_text())
        if len(trace_hashes) != 3:
            raise ValueError('expected frontend and two worker traces')
        for relative, digest in trace_hashes.items():
            if sha((root / '27b-fp8' / relative).read_bytes()) != digest:
                raise ValueError('profile trace receipt differs')
        request = json.loads((root / '27b-fp8/profile-request/request.json').read_text())
        response = json.loads((root / '27b-fp8/profile-request/response.json').read_text())
        baseline = json.loads((root / '27b-fp8/baseline/summary.json').read_text())
        expected_token = next(r['token_ids'][0] for r in baseline['rows'] if r['key'] == 'prose-512')
        if (request['prompt'] != baseline['prompts']['prose-512'] or len(request['prompt']) != 512
                or request['max_tokens'] != 1 or response['usage']['prompt_tokens'] != 512
                or response['usage']['prompt_tokens_details']['cached_tokens'] != 0
                or response['choices'][0]['token_ids'] != [expected_token]):
            raise ValueError('profile request/input/cache/output parity differs')
        result = summary.summarize(root)
        if not result['complete']:
            raise ValueError(json.dumps(result['profiles']))
        saved = json.loads((packet / 'summary.json').read_text())
        result['raw_root'] = saved['raw_root']
        summary.same(saved, result, 'archived replay differs from published summary')
    return {'passed': True, 'archives': len(manifest['archives']), 'receipts': checked,
            'source_files': len(manifest['source_files']), 'profiles': len(result['profiles']),
            'summary_sha256': sha((packet / 'summary.json').read_bytes()),
            'manifest_sha256': sha((evidence / 'manifest.json').read_bytes()),
            'scope': 'Offline hash and raw receipt replay; no GPU requests.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, default=HERE.parent / 'data/2026-09-14-fp8-prefill-focus')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    result = verify(args.packet)
    if args.receipt:
        with args.receipt.open('x') as output:
            json.dump(result, output, indent=2)
            output.write('\n')
    print(json.dumps(result))
