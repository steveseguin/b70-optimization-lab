#!/usr/bin/env python3
"""Emit the draft-only overlay for a new49c/49d engine copy, never modify a parent."""
import argparse
import hashlib
import json
from pathlib import Path
P=Path(__file__).resolve().parent

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def verify(base):
    base=Path(base).resolve()
    if base not in ((P.parent/'packet49c-round2').resolve(),(P.parent/'packet49d-round3').resolve()):
        raise ValueError('only the pinned49c/49d parents are registered')
    manifest=json.loads((P/'base-source-manifest.json').read_text())
    if sha(base/'mtp.hpp') != manifest['files_sha256']['mtp.hpp']:
        raise ValueError('parent draft runtime differs from overlay preimage')
    for name in ('p33_submit.cpp','round2_submit.cpp','arithmetic.hpp','native_controller.hpp','dispatch-speed6.json'):
        if sha(base/name) != manifest['files_sha256'][name]:raise ValueError('parent kernel/controller differs: '+name)
    return dict(base_packet=base.name,base_mtp_sha256=sha(base/'mtp.hpp'),
                files_sha256={name:sha(P/name) for name in ('mtp.hpp','p56_config.hpp','p56_prefix.hpp')},
                target_arithmetic_unchanged=True,requires_fresh_build_and_gates=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',type=Path,required=True);ap.add_argument('--output',type=Path)
    args=ap.parse_args();row=verify(args.base)
    if args.output:
        out=args.output.resolve()
        if out.exists():raise ValueError('overlay output must be a new directory')
        for protected in ('packet49c-round2','packet49d-round3'):
            if out.is_relative_to((P.parent/protected).resolve()):raise ValueError('protected parent tree')
        out.mkdir(parents=True)
        for name in row['files_sha256']:(out/name).write_bytes((P/name).read_bytes())
        (out/'overlay.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(row,indent=2))
if __name__=='__main__': main()
