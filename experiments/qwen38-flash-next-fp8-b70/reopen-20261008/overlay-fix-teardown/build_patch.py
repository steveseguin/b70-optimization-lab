#!/usr/bin/env python3
"""Verify/rebuild the frozen review artifact against its pre-application Git tree."""
import argparse
import difflib
import hashlib
import json
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
COPIES=HERE/'copies'
REPO=BASE.parents[2]
BASE_REVISION='08b6217e8a8a85aede148863e44cd0f4194d1d78'


def before_bytes(rel):
    """Frozen preimage; applying the patch must not change its review record."""
    path=str((BASE/rel).relative_to(REPO))
    result=subprocess.run(['git','show',BASE_REVISION+':'+path],cwd=REPO,
                          capture_output=True)
    if result.returncode == 0:
        return result.stdout
    if result.returncode == 128 and (b'does not exist in' in result.stderr or b'exists on disk, but not in' in result.stderr):
        return None
    raise RuntimeError(result.stderr.decode())


def sha(raw):return hashlib.sha256(raw).hexdigest()


def artifacts():
    payload={str(p.relative_to(COPIES)):p.read_bytes() for p in sorted(COPIES.rglob('*'))
             if p.is_file() and p.suffix in ('.py', '.sh')}
    manifest=json.loads(before_bytes('overlay-manifest.json'))
    for rel,raw in payload.items():
        if rel.startswith('overlay/'):
            runtime_rel=rel[len('overlay/'):]
            digest=sha(raw)
            manifest['files'][runtime_rel]=digest
            if runtime_rel in manifest['replacements']:
                manifest['replacements'][runtime_rel]['sha256']=digest
            else:
                native=HERE/'base-runtime'/runtime_rel
                manifest['replacements'][runtime_rel]=dict(
                    base_sha256=sha(native.read_bytes()) if native.exists() else None,
                    sha256=digest)
        else:
            manifest['support_files'][rel]=sha(raw)
    manifest['semantics']['shutdown']='UNQUALIFIED teardown candidate: cooperative signals; ordered alias/PLE/pin release; worker then communicator cleanup; per-rank release receipts; no kill escalation'
    payload['overlay-manifest.json']=(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode()
    lines=[]
    pins={}
    for rel,raw in sorted(payload.items()):
        original=before_bytes(rel)
        old=original if original is not None else b''
        if old==raw:continue
        lines.extend(difflib.unified_diff(old.decode().splitlines(keepends=True),
                     raw.decode().splitlines(keepends=True),
                     fromfile='a/'+rel if original is not None else '/dev/null',tofile='b/'+rel))
        pins[rel]={'before_sha256':sha(old) if original is not None else None,'after_sha256':sha(raw)}
    metadata=dict(schema='screen1b.unapplied-teardown-patch.v1',applied=False,
                  image=json.loads(before_bytes('image-plan.json'))['image'],
                  files=pins,native_base_sources={str(p.relative_to(HERE/'base-runtime')):sha(p.read_bytes())
                    for p in sorted((HERE/'base-runtime').rglob('*.py'))})
    return {'copies/overlay-manifest.json':payload['overlay-manifest.json'],
            # Git accepts bare empty context lines; avoid storing space-only lines.
            'teardown.patch':''.join('\n' if line == ' \n' else line for line in lines).encode(),
            'patch-manifest.json':(json.dumps(metadata,indent=2,ensure_ascii=False)+'\n').encode()}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    for rel,raw in artifacts().items():
        path=HERE/rel
        if args.check:
            if not path.exists() or path.read_bytes()!=raw:
                raise SystemExit('stale review artifact: '+rel)
        else:
            path.write_bytes(raw)
    print('Frozen patch artifacts '+('verified' if args.check else 'sealed'))
