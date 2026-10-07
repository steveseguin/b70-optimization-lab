#!/usr/bin/env python3
"""Independently verify packet-99 source only; never qualify or launch a runtime."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tarfile

OLD = '19e1058f4c445ef74047e77a23f9ca7684c1e4b6'
NEW = 'b00c6e95279053474955540ba4f551646722b9aa'
MANIFEST_SHA = '918b47a5530b4dc97fe8fc8f4ec77fd64521ec6846217c54f5fba589e0e8377f'
REPO = Path('/home/steve/src/ComfyUI-ltx25-baseline')
HISTORICAL = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-size-98')
NATIVE = {
    'comfy/ldm/lightricks/av_model.py': 'e880b29b1d6e2cefe807c53c26cf4733d90aaae13126d8652f5989de15d1f213',
    'comfy/model_patcher.py': '5882b0e1192037654cf78ea11852c7c8393018fdddbfd9e9bed73ff3542be1c6',
    'comfy/sd.py': '2917a7982d08640ebe297ebc5cb5ad873567099c2e66688dcaff3650464dc694',
    'comfy/sd1_clip.py': '4b7f08bea2028e73c8f68dc9a26f5cc2981ddf27f12c303a467bd8aa9939dcfa',
    'comfy/text_encoders/lt.py': '0e58019c5ae8755d03654238c78ce5d39aa606eac7ffce568332feac0342952a',
}
COUNTS = {'old_upstream': 1191, 'new_upstream': 1270, 'lab_additions': 63,
          'native_overlays': 5, 'new_source_files': 1333,
          'historical_files_accounted': 1501, 'historical_non_source_pending': 247}
STATUS = b'UNSEALED-NOT-LAUNCHABLE\nSource only; no new runtime qualification.\n'
MAX_BYTES = 128 * 1024**2


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def safe_name(path):
    require(isinstance(path, str) and path and '\x00' not in path and
            not PurePosixPath(path).is_absolute() and '..' not in PurePosixPath(path).parts and
            str(PurePosixPath(path)) == path, 'Unsafe inventory path')


def digest_string(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'Invalid SHA-256')


def regular(path, limit=MAX_BYTES):
    require(path.is_absolute() and '..' not in path.parts, 'Absolute normalized path required')
    require(not any(p.is_symlink() for p in [path, *path.parents]), 'Symlink refused: ' + str(path))
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= limit, 'Not a bounded regular file')
    raw = path.read_bytes(); after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'File changed during verification')
    return raw


def load_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'Duplicate JSON key: ' + key)
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON value')))


def git(repo, *args):
    return subprocess.check_output(['git', '--no-replace-objects', '-C', str(repo), *args], timeout=120)


def git_tree(repo, commit):
    require(git(repo, 'rev-parse', '--verify', commit + '^{commit}').decode().strip() == commit,
            'Pinned source commit unavailable')
    rows = {}
    for entry in git(repo, 'ls-tree', '-rlz', commit).split(b'\0'):
        if not entry:
            continue
        info, name = entry.split(b'\t', 1); mode, kind, oid, size = info.split()
        name = name.decode('utf-8'); safe_name(name)
        require(mode in (b'100644', b'100755') and kind == b'blob', 'Nonregular Git object')
        rows[name] = {'mode': mode.decode(), 'blob': oid.decode(), 'bytes': int(size)}
    require(sum(x['bytes'] for x in rows.values()) <= MAX_BYTES, 'Git source exceeds bound')
    return rows


def validate_plan(plan, repo=REPO, historical=HISTORICAL):
    require(plan.get('schema') == 'ltx.upstream99.source-plan.v1', 'Wrong plan schema')
    require(plan.get('status') == 'UNSEALED-NOT-LAUNCHABLE' and plan.get('qualification') is False,
            'Source plan cannot claim runtime qualification')
    require(type(plan.get('model_requests')) is int and plan['model_requests'] == 0, 'Source-only plan required')
    require(plan.get('old_commit') == OLD and plan.get('new_commit') == NEW and
            plan.get('historical_manifest_sha256') == MANIFEST_SHA, 'Wrong pinned transition')
    require(plan.get('counts') == COUNTS and all(type(v) is int for v in plan['counts'].values()), 'Wrong source census')
    require(plan.get('unchanged_control') == {'sampler_split': '23/25', 'batch': 1, 'references': 'w93c'},
            'Baseline control changed')
    require(plan.get('pending') == ['transition-aware runtime checker and launcher', 'accepted overlay API/behavior review',
            'CPU source-contract tests', 'new-base capture and exact-output gates',
            'runtime/dependency identity and host admission'], 'Missing runtime limitations')
    require(Path(plan.get('source_repo', '')) == repo and Path(plan.get('historical_packet', '')) == historical,
            'Source provenance paths differ')
    digest_string(plan.get('builder_sha256'))
    require(plan['builder_sha256'] == sha(regular(Path(__file__).with_name('prepare-upstream-99.py').absolute())),
            'Builder identity changed')
    manifest_raw = regular(historical / 'manifest.json', 4 * 1024**2)
    require(sha(manifest_raw) == MANIFEST_SHA, 'Historical manifest changed')
    manifest = load_json(manifest_raw)
    require(manifest['source_commit'] == OLD and len(manifest['files']) == 1501, 'Historical closure differs')
    old, new = git_tree(repo, OLD), git_tree(repo, NEW)
    require(plan.get('source_tree_oid') == git(repo, 'rev-parse', NEW + '^{tree}').decode().strip(), 'Wrong Git tree')
    old_sources = {p[7:]: h for p, h in manifest['files'].items() if p.startswith('source/')}
    additions = set(old_sources) - set(old)
    require(len(old) == 1191 and len(new) == 1270 and len(additions) == 63 and
            set(old) <= set(old_sources) and not additions & set(new), 'Git/overlay census differs')
    require(set(old) - set(new) == {'comfy_api_nodes/nodes_sora.py', 'tests-unit/comfy_test/seedvr_vae_forward_test.py'}
            and len(set(new) - set(old)) == 81, 'Upstream additions/deletions differ')
    rows = plan.get('source_files', {})
    require(set(rows) == set(new) | additions, 'Plan omitted/added source paths')
    for path, row in rows.items():
        safe_name(path); digest_string(row.get('sha256'))
        require(type(row.get('bytes')) is int and 0 <= row['bytes'] <= MAX_BYTES, 'Invalid source size')
        if path in additions:
            require(row.get('basis') == 'unchanged-lab-addition' and row.get('mode') == '100644' and
                    row['sha256'] == old_sources[path], 'Lab addition differs from historical manifest')
        else:
            require(row.get('blob') == new[path]['blob'] and row.get('mode') == new[path]['mode'], 'Wrong upstream tree binding')
            digest_string(row.get('upstream_sha256'))
            if path in NATIVE:
                resolution = ('explicit-new-fast-disk-constructor-plus-unchanged-small-state-guard' if path == 'comfy/sd.py'
                              else 'clean-three-way-merge')
                require(row.get('basis') == 'rebased-native-overlay' and row['sha256'] == NATIVE[path] and
                        row.get('historical_sha256') == old_sources[path] and row.get('resolution') == resolution,
                        'Reviewed native overlay differs')
                require(row['upstream_sha256'] == sha(git(repo, 'show', NEW + ':' + path)), 'Wrong native upstream SHA')
            else:
                require(row.get('basis') == 'new-upstream' and row['bytes'] == new[path]['bytes'] and
                        row['upstream_sha256'] == row['sha256'], 'Unmodified upstream row differs')
    require(type(plan.get('source_bytes')) is int and plan['source_bytes'] == sum(r['bytes'] for r in rows.values())
            and plan['source_bytes'] <= MAX_BYTES, 'Source byte census differs')
    expected_disposition = {}
    for path, digest in manifest['files'].items():
        if not path.startswith('source/'):
            status = 'historical-non-source-dependency-not-yet-ported'
        elif path[7:] not in rows:
            status = 'upstream-deleted-from-live-source-preserved-in-historical-packet'
        else:
            status = rows[path[7:]]['basis']
        expected_disposition[path] = {'historical_sha256': digest, 'disposition': status}
    require(plan.get('historical_file_disposition') == expected_disposition, 'Historical closure accounting differs')
    require(set(plan.get('overlay_patches', {})) == set(NATIVE), 'Native patch inventory differs')
    for path in NATIVE:
        original = git(repo, 'show', OLD + ':' + path)
        overlay = regular(historical / 'source' / path)
        require(sha(overlay) == old_sources[path], 'Historical overlay bytes changed')
        expected = ''.join(difflib.unified_diff(original.decode().splitlines(keepends=True),
                    overlay.decode().splitlines(keepends=True), fromfile='old-upstream/' + path, tofile='packet98/' + path))
        require(plan['overlay_patches'][path] == expected, 'Historical patch provenance differs')
    return new, manifest_raw


def inventory(root):
    require(root.is_absolute() and root.is_dir() and not any(p.is_symlink() for p in [root, *root.parents]),
            'Unsafe inventory root')
    files, directories = set(), set()
    for directory, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            path = Path(directory) / name
            mode = path.lstat().st_mode
            require(not stat.S_ISLNK(mode), 'Source symlink refused')
            require(stat.S_ISDIR(mode) or stat.S_ISREG(mode), 'Nonregular inventory member')
            if stat.S_ISDIR(mode):
                directories.add(str(path.relative_to(root)))
        files.update(str((Path(directory) / name).relative_to(root)) for name in names)
    expected_dirs = {str(parent) for name in files for parent in PurePosixPath(name).parents if str(parent) != '.'}
    require(directories == expected_dirs, 'Unexpected empty directory in inventory')
    return files


def check_source_files(root, rows):
    """Reusable tiny-fixture boundary; validates actual bytes, modes and Git IDs."""
    for path in rows:
        safe_name(path)
    require(inventory(root) == set(rows), 'On-disk source inventory differs')
    actual_blobs = {}
    for path, row in rows.items():
        dest = root / path; raw = regular(dest)
        require(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'On-disk source bytes differ: ' + path)
        require(stat.S_IMODE(dest.stat().st_mode) == (int(row['mode'], 8) & 0o777), 'Source mode differs: ' + path)
        oid = blob(raw)
        if row['basis'] == 'new-upstream':
            require(oid == row['blob'], 'On-disk Git blob differs: ' + path)
        if row['basis'] == 'rebased-native-overlay':
            actual_blobs[path] = oid
    return actual_blobs


def check_archive(path, upstream, rows):
    seen = set()
    with tarfile.open(path, 'r:') as tar:
        for item in tar:
            safe_name(item.name.rstrip('/'))
            if item.isdir():
                require(any(p.startswith(item.name.rstrip('/') + '/') for p in upstream), 'Unexpected archive directory')
                continue
            require(item.isfile() and item.name in upstream and item.name not in seen, 'Unexpected/duplicate archive member')
            require(item.mode == (int(upstream[item.name]['mode'], 8) & 0o777), 'Archive mode differs from Git tree')
            require(item.size == upstream[item.name]['bytes'], 'Wrong archive member size')
            raw = tar.extractfile(item).read()
            require(blob(raw) == upstream[item.name]['blob'] and sha(raw) == rows[item.name]['upstream_sha256'],
                    'Archive differs from upstream Git blob')
            seen.add(item.name)
    require(seen == set(upstream), 'Archive omitted upstream files')


def check(candidate, repo=REPO, historical=HISTORICAL):
    raw = regular(candidate / 'source-plan.json', 4 * 1024**2); plan = load_json(raw)
    upstream, manifest_raw = validate_plan(plan, repo, historical)
    require(plan.get('output') == str(candidate), 'Candidate output provenance differs')
    require(regular(candidate / 'STATUS.txt') == STATUS, 'Candidate must stay unsealed')
    require(regular(candidate / 'provenance/packet98-manifest.json', 4 * 1024**2) == manifest_raw,
            'Preserved historical manifest differs')
    expected = {'STATUS.txt', 'source-plan.json', 'provenance/packet98-manifest.json', 'provenance/upstream-source.tar'}
    expected.update('source/' + p for p in plan['source_files'])
    require(inventory(candidate) == expected, 'Unexpected candidate file (no launcher is admitted)')
    archive = regular(candidate / 'provenance/upstream-source.tar', 2 * MAX_BYTES)
    require(type(plan.get('archive_bytes')) is int and len(archive) == plan['archive_bytes'] and
            sha(archive) == plan.get('archive_sha256'), 'Archive receipt differs')
    check_archive(candidate / 'provenance/upstream-source.tar', upstream, plan['source_files'])
    merged_blobs = check_source_files(candidate / 'source', plan['source_files'])
    return {'schema': 'ltx.upstream99.source-check.v1', 'status': 'SOURCE-INTEGRITY-PASSED-UNSEALED',
            'source_plan_sha256': sha(raw), 'checker_sha256': sha(Path(__file__).read_bytes()),
            'new_commit': NEW, 'historical_manifest_sha256': MANIFEST_SHA, 'counts': plan['counts'],
            'actual_merged_git_blobs': merged_blobs, 'runtime_qualified': False, 'launchable': False,
            'pending': plan['pending'], 'model_requests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--candidate', type=Path)
    action.add_argument('--plan-only', type=Path, help='Validate a saved --plan receipt; no materialized-source claim')
    args = parser.parse_args()
    if args.plan_only:
        raw = regular(args.plan_only, 4 * 1024**2); plan = load_json(raw)
        validate_plan(plan)
        result = {'status': 'PLAN-IDENTITY-PASSED-SOURCE-NOT-CHECKED', 'source_plan_sha256': sha(raw),
                  'runtime_qualified': False, 'launchable': False, 'model_requests': 0}
    else:
        result = check(args.candidate)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
