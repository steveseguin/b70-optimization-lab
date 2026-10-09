#!/usr/bin/env python3
"""Seal an unapplied review artifact. Never modifies the live Screen 1b package."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
COPIES=HERE/'copies'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def artifacts():
    payload={str(p.relative_to(COPIES)):p.read_bytes() for p in sorted(COPIES.rglob('*'))
             if p.is_file() and p.suffix in ('.py', '.sh')}
    manifest=json.loads((BASE/'overlay-manifest.json').read_text())
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
    payload['overlay-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    lines=[]
    pins={}
    for rel,raw in sorted(payload.items()):
        original=BASE/rel
        old=original.read_bytes() if original.exists() else b''
        if old==raw:continue
        lines.extend(difflib.unified_diff(old.decode().splitlines(keepends=True),
                     raw.decode().splitlines(keepends=True),
                     fromfile='a/'+rel if original.exists() else '/dev/null',tofile='b/'+rel))
        pins[rel]={'before_sha256':sha(old) if original.exists() else None,'after_sha256':sha(raw)}
    metadata=dict(schema='screen1b.unapplied-teardown-patch.v1',applied=False,
                  image=json.loads((BASE/'image-plan.json').read_text())['image'],
                  files=pins,native_base_sources={str(p.relative_to(HERE/'base-runtime')):sha(p.read_bytes())
                    for p in sorted((HERE/'base-runtime').rglob('*.py'))})
    return {'copies/overlay-manifest.json':payload['overlay-manifest.json'],
            # Git accepts bare empty context lines; avoid storing space-only lines.
            'teardown.patch':''.join('\n' if line == ' \n' else line for line in lines).encode(),
            'patch-manifest.json':(json.dumps(metadata,indent=2)+'\n').encode()}


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
    print('Unapplied patch artifacts '+('verified' if args.check else 'sealed'))
