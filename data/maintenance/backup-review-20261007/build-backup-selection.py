#!/usr/bin/env python3
"""Build one frozen backup selection; does not archive, copy or access a device.

Run once from any directory with Python 3.12. The NUL list is outside Git.
For review only, its GNU tar input contract is:
  tar --create --file DEST --acls --xattrs --numeric-owner \
      --directory / --no-recursion --null --verbatim-files-from \
      --files-from /home/steve/git-archives/backup-selection-20261007.nul
Keep --no-recursion before --files-from and do not add --dereference. No such
command is executed here. The repository is backed up separately with a Git
bundle and a HEAD archive. This selection deliberately does not include it.
"""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LIST_PATH = Path('/home/steve/git-archives/backup-selection-20261007.nul')
SUMMARY_PATH = HERE / 'selection-summary.json'
ARCHIVES = Path('/home/steve/git-archives')
LTX = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
# Exact allowlist: newly created backup archives/control files are never selected.
ARCHIVE_CHILDREN = (
    'cache-consolidation-20261006',
    'staging-consolidation-20261007',
    'flash-next-rescue-20261007',
    'llm-optimizations-pre-main-consolidation-20260814.bundle',
    'llm-optimizations-qwen-agent-tp2-20260814.bundle',
)
SECRET_NAME = re.compile(
    r'(^sudopassword|password|(^|[._-])(secret|secrets|credentials)([._-]|$)|'
    r'^\.env($|\.)|^id_(rsa|dsa|ecdsa|ed25519)($|\.)|'
    r'^(token|api_key|hf_token)(\.(txt|json))?$|\.(pem|p12|pfx|key)$)',
    re.IGNORECASE,
)


def main():
    if LIST_PATH.exists() or SUMMARY_PATH.exists():
        raise SystemExit('One-shot outputs already exist; preserve them and review before another selection.')
    reference_names = {'baseline-01', 'baseline-02', 'baseline-03',
                       'resident-split-03', 'speed-oracle-bird', 'speed-oracle-marble'}
    reference_inputs = []
    for name in ('window', 'batch2', 'batch4'):
        path = REPO / f'experiments/ltx25-b70/data/stability-01-{name}-prereg.json'
        data = path.read_bytes()
        reference_inputs.append({'path': str(path), 'sha256': hashlib.sha256(data).hexdigest()})
        for fixture in json.loads(data)['fixtures']:
            reference = fixture['reference']
            if Path(reference).name != reference or reference in ('.', '..'):
                raise SystemExit('Invalid reference directory name in preregistration.')
            reference_names.add(reference)
    if len(reference_names) != 36:
        raise SystemExit(f'Expected 36 exact reference directories, found {len(reference_names)}.')

    selections = []
    seen_paths = set()
    seen_inodes = set()
    totals = Counter()
    groups = {}
    secret_flags = []
    rejected = []

    def visit(path, group, root_device, descend=True, excluded_children=()):
        if path in seen_paths:
            return
        info = path.lstat()
        if info.st_dev != root_device:
            rejected.append({'path': str(path), 'reason': 'unexpected filesystem crossing'})
            return
        kind = ('directory' if stat.S_ISDIR(info.st_mode) else
                'file' if stat.S_ISREG(info.st_mode) else
                'symlink' if stat.S_ISLNK(info.st_mode) else 'special')
        if kind == 'special':
            rejected.append({'path': str(path), 'reason': 'special file'})
            return
        if SECRET_NAME.search(path.name):
            secret_flags.append(str(path))
        if kind == 'file' and not os.access(path, os.R_OK):
            rejected.append({'path': str(path), 'reason': 'unreadable regular file'})
        seen_paths.add(path)
        selections.append(os.fsencode(str(path.relative_to('/'))))
        counts = groups.setdefault(group, Counter())
        for counter in (counts, totals):
            counter[kind + '_count'] += 1
            counter['logical_regular_bytes'] += info.st_size if kind == 'file' else 0
            counter['symlink_payload_bytes'] += info.st_size if kind == 'symlink' else 0
            counter['hardlinked_regular_file_count'] += int(kind == 'file' and info.st_nlink > 1)
        inode = (info.st_dev, info.st_ino)
        if inode not in seen_inodes:
            seen_inodes.add(inode)
            for counter in (counts, totals):
                counter['allocated_unique_bytes'] += info.st_blocks * 512
        if kind == 'directory' and descend:
            # Never follow symlinks. Every admitted file/directory is individually
            # listed, so future files cannot be picked up by tar recursion.
            with os.scandir(path) as entries:
                children = sorted((Path(e.path) for e in entries), key=lambda p: os.fsencode(p.name))
            for child in children:
                if child.name not in excluded_children:
                    visit(child, group, root_device)

    def root(path, group, descend=True, excluded_children=()):
        if path.is_symlink() or not path.is_dir():
            raise RuntimeError(f'Declared source root must be a real directory: {path}')
        visit(path, group, path.stat().st_dev, descend, excluded_children)

    root(ARCHIVES, 'git_archives', descend=False)
    archive_device = ARCHIVES.stat().st_dev
    for name in ARCHIVE_CHILDREN:
        visit(ARCHIVES / name, 'git_archives', archive_device)
    excluded_archive_children = sorted(p.name for p in ARCHIVES.iterdir() if p.name not in ARCHIVE_CHILDREN)
    root(Path('/home/steve/identified-mistakes'), 'identified_mistakes')
    root(Path('/home/steve/src/ComfyUI-ltx25-baseline'), 'ltx_source')
    root(LTX, 'ltx_raw_without_output_quarantine', excluded_children=('output', 'quarantine'))
    root(LTX / 'output', 'ltx_previews', excluded_children=('validation',))
    root(LTX / 'output/validation', 'ltx_references', descend=False)
    validation_device = (LTX / 'output/validation').stat().st_dev
    for name in sorted(reference_names):
        path = LTX / 'output/validation' / name
        if path.is_symlink() or not path.is_dir():
            raise RuntimeError(f'Exact reference must be a real directory: {path}')
        visit(path, 'ltx_references', validation_device)
    packet97 = sorted((p for p in (LTX / 'output/validation').iterdir() if p.name.startswith('f97-')),
                      key=lambda p: p.name)
    if not packet97:
        raise RuntimeError('No packet-97 validation directories found.')
    for path in packet97:
        if path.is_symlink() or not path.is_dir():
            raise RuntimeError(f'Packet-97 output must be a real directory: {path}')
        visit(path, 'ltx_packet97_outputs', validation_device)

    selections.sort()
    payload = b''.join(name + b'\0' for name in selections)
    # The limit is on source payload, not a guessed compressed archive size.
    if totals['logical_regular_bytes'] > 100 * 1024**3:
        rejected.append({'reason': 'selected regular-file payload exceeds 100 GiB'})
    admitted = not secret_flags and not rejected
    summary = {
        'schema': 'lab.research-backup-selection.v1',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'host': os.uname().nodename,
        'admitted': admitted,
        'selection_builder_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'nul_list_path': str(LIST_PATH),
        'nul_list_written': admitted,
        'nul_list_sha256': hashlib.sha256(payload).hexdigest(),
        'nul_list_bytes': len(payload),
        'listed_paths': len(selections),
        'totals': dict(totals),
        'groups': {key: dict(value) for key, value in groups.items()},
        'archive_child_allowlist': list(ARCHIVE_CHILDREN),
        'excluded_existing_archive_children': excluded_archive_children,
        'exact_reference_names': sorted(reference_names),
        'reference_manifest_inputs': reference_inputs,
        'packet97_validation_directory_count': len(packet97),
        'secret_like_filename_flags': secret_flags,
        'rejected_entries': rejected,
        'archive_input_contract': {
            'names_relative_to': '/',
            'null_delimited': True,
            'no_recursion': True,
            'verbatim_files_from': True,
            'dereference_symlinks': False,
            'preserve': ['directories', 'regular files', 'symlinks', 'modes', 'ownership', 'ACLs', 'xattrs'],
        },
        'exclusions': [
            'Repository paths: preserve separately with git bundle --all and git archive HEAD.',
            'LTX quarantine and validation outputs other than the 36 exact references and f97-*.',
            'All git-archives top-level entries except the explicit existing-child allowlist.',
            'External filesystems, model stores, home configuration and session directories.',
        ],
        'limitations': [
            'Filename screening does not inspect content or establish absence of embedded secrets.',
            'Point-in-time selection; file content can change before archival. Recheck identity and verify afterward.',
            'Allocated bytes count each inode once; logical bytes count every listed regular-file name.',
            'This command creates only the local path list and summary; no backup or copy has been performed.',
        ],
    }
    if admitted:
        with LIST_PATH.open('xb') as handle:
            handle.write(payload)
    with SUMMARY_PATH.open('x') as handle:
        json.dump(summary, handle, indent=2)
        handle.write('\n')
    print(json.dumps({'admitted': admitted, 'summary': str(SUMMARY_PATH),
                      'logical_regular_bytes': totals['logical_regular_bytes'],
                      'listed_paths': len(selections), 'secret_name_flags': len(secret_flags),
                      'rejected_entries': len(rejected)}))
    return 0 if admitted else 1


if __name__ == '__main__':
    raise SystemExit(main())
