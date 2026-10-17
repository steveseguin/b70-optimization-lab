#!/usr/bin/env python3
"""CPU-only copy of the clean export, then the single reviewed patch. No imports."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
CLEAN = Path('/home/steve/src/vllm-flashnext-a367-clean-20261016')
CANDIDATE = Path('/home/steve/src/vllm-flashnext-a367-glue01-20261017')
PATCH = REPO / 'patches/flash-next-m2-glue-fusion-01-row-copy.patch'
PATCH_SHA = '9a31076b55f5e6298226c9caa8c2ddf34a0ed479508512ad70be7de089c1c912'
CHANGED = 'vllm/distributed/device_communicators/xpu_communicator.py'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def manifest(root):
    # Symlinks are recorded by link bytes, not followed outside the export.
    return {str(p.relative_to(root)): {'symlink': str(p.readlink())} if p.is_symlink()
            else {'sha256': sha(p)} for p in sorted(root.rglob('*')) if p.is_file() or p.is_symlink()}

def main():
    assert sha(PATCH) == PATCH_SHA, 'patch changed'
    before = manifest(CLEAN)
    if CANDIDATE.exists():
        # Read-only recovery after an interrupted receipt write; never patch twice.
        subprocess.run(['git', 'apply', '--reverse', '--check', str(PATCH)], cwd=CANDIDATE, check=True)
    else:
        shutil.copytree(CLEAN, CANDIDATE, symlinks=True)
        subprocess.run(['git', 'apply', '--check', '--whitespace=error', str(PATCH)], cwd=CANDIDATE, check=True)
        subprocess.run(['git', 'apply', '--whitespace=error', str(PATCH)], cwd=CANDIDATE, check=True)
    after = manifest(CANDIDATE)
    assert manifest(CLEAN) == before, 'clean source changed'
    assert set(after) == set(before), 'candidate file set differs'
    assert [p for p in before if before[p] != after[p]] == [CHANGED], 'more than patch01 changed'
    pins = json.loads((HERE.parent / 'driver/preregistration.json').read_text())['source_pins']
    assert all(before[p] == {'sha256': digest} for p, digest in pins.items()), 'clean certified pins'
    receipt = {'schema': 'a367-glue01-source-export.v1', 'clean': str(CLEAN), 'candidate': str(CANDIDATE),
               'patch': str(PATCH.relative_to(REPO)), 'patch_sha256': PATCH_SHA,
               'clean_unchanged': True, 'files': len(before), 'python_pins': len(pins),
               'changed_files': {CHANGED: {'before': before[CHANGED]['sha256'], 'after': after[CHANGED]['sha256']}},
               'clean_manifest_sha256': hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
               'candidate_manifest_sha256': hashlib.sha256(json.dumps(after, sort_keys=True).encode()).hexdigest(),
               'candidate_files': after, 'native_executed': False}
    (HERE / 'source-export.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k:v for k,v in receipt.items() if k != 'candidate_files'}, indent=2))

if __name__ == '__main__':
    main()
