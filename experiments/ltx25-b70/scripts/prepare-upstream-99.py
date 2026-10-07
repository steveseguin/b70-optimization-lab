#!/usr/bin/env python3
"""Plan, or explicitly prepare, an UNSEALED packet-99 source transplant.

Default --plan is read-only. --prepare copies source into a new owned directory;
it never starts a server, imports model/runtime modules or produces a launcher.
Run preparation only in the parent's admitted CPU/storage window, not alongside
the active control. Historical packets and checkout files remain unchanged.
"""
import argparse
import ast
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile

OLD = '19e1058f4c445ef74047e77a23f9ca7684c1e4b6'
NEW = 'b00c6e95279053474955540ba4f551646722b9aa'
REPO = Path('/home/steve/src/ComfyUI-ltx25-baseline')
PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-size-98')
MANIFEST_SHA = '918b47a5530b4dc97fe8fc8f4ec77fd64521ec6846217c54f5fba589e0e8377f'
NATIVE = {'comfy/model_patcher.py', 'comfy/sd.py', 'comfy/sd1_clip.py',
          'comfy/text_encoders/lt.py', 'comfy/ldm/lightricks/av_model.py'}
REMOVED = {'comfy_api_nodes/nodes_sora.py', 'tests-unit/comfy_test/seedvr_vae_forward_test.py'}
MAX_SOURCE_BYTES = 128 * 1024**2
ROOT_RESERVE = 50 * 1024**3
SD_OLD = '        self.patcher = ModelPatcher(self.cond_stage_model, load_device=load_device, offload_device=offload_device)\n'
SD_NEW = '        self.patcher = ModelPatcher(self.cond_stage_model, load_device=load_device, offload_device=offload_device, fast_disk=comfy.storage.state_dict_fast_disk(state_dict))\n'
SD_GUARD = '''        if model_options.get("ltx_small_state_residency", False):
            if self.patcher.is_dynamic() or not hasattr(self.patcher, "_ltx_small_state"):
                raise RuntimeError("LTX small-state option requires the patched static ModelPatcher")
            # Propagate before constructor-time load_models_gpu can run.
            self.patcher.model_options["ltx_small_state_residency"] = True
'''


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], timeout=120)


def tree(repo, commit):
    require(git(repo, 'rev-parse', '--verify', commit + '^{commit}').decode().strip() == commit,
            'Exact upstream commit unavailable')
    rows = {}
    for row in git(repo, 'ls-tree', '-r', '-l', '-z', commit).split(b'\0'):
        if not row:
            continue
        info, raw_path = row.split(b'\t', 1)
        mode, kind, oid, size = info.split()
        path = raw_path.decode('utf-8')
        require(str(PurePosixPath(path)) == path and not path.startswith('/') and
                '..' not in PurePosixPath(path).parts, 'Unsafe Git path')
        require(mode in (b'100644', b'100755') and kind == b'blob', 'Nonregular upstream path: ' + path)
        rows[path] = {'mode': mode.decode(), 'blob': oid.decode(), 'bytes': int(size)}
    require(sum(x['bytes'] for x in rows.values()) <= MAX_SOURCE_BYTES, 'Upstream source exceeds bound')
    return rows


def blobs(repo, rows):
    """Stream Git blobs; retain no complete source-tree copy in memory."""
    proc = subprocess.Popen(['git', '-C', str(repo), 'cat-file', '--batch'],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        for path, item in rows.items():
            proc.stdin.write((item['blob'] + '\n').encode()); proc.stdin.flush()
            expected = [item['blob'].encode(), b'blob', str(item['bytes']).encode()]
            require(proc.stdout.readline().split() == expected, 'Unexpected Git blob header')
            raw = proc.stdout.read(item['bytes'])
            require(len(raw) == item['bytes'] and proc.stdout.read(1) == b'\n', 'Incomplete Git blob')
            require(hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == item['blob'],
                    'Git blob identity mismatch')
            yield path, raw
        proc.stdin.close()
        require(proc.wait(timeout=30) == 0, 'Git blob reader failed')
    finally:
        if not proc.stdin.closed:
            proc.stdin.close()
        if proc.poll() is None:
            proc.terminate()  # Only this helper's CPU Git reader.
            proc.wait(timeout=10)
        proc.stdout.close()


def regular_bound(path, expected):
    require(path.is_absolute(), 'Absolute source path required')
    require(not any(p.is_symlink() for p in [path, *path.parents]), 'Source symlink refused')
    require(path.is_file(), 'Missing regular source')
    raw = path.read_bytes()
    require(sha(raw) == expected, 'Historical source changed: ' + str(path))
    return raw


def merge_native(path, base, latest, overlay):
    """Git three-way merge in anonymous memory files, no index/worktree writes."""
    fds = []
    try:
        for raw in (latest, base, overlay):
            fd = os.memfd_create('ltx99-merge-input'); fds.append(fd)
            with os.fdopen(os.dup(fd), 'wb') as stream:
                stream.write(raw)
            os.lseek(fd, 0, 0)
        result = subprocess.run(['git', 'merge-file', '-p', '-L', 'new-upstream',
                                 '-L', 'old-upstream', '-L', 'packet98-overlay',
                                 *[f'/proc/self/fd/{fd}' for fd in fds]],
                                pass_fds=tuple(fds), capture_output=True, timeout=30)
        merged = result.stdout.decode('utf-8')
        resolution = 'clean-three-way-merge'
        if result.returncode != 0:
            conflict = ('<<<<<<< new-upstream\n' + SD_NEW + '=======\n' +
                        SD_OLD + SD_GUARD + '>>>>>>> packet98-overlay\n')
            require(path == 'comfy/sd.py' and result.returncode == 1 and
                    merged.count(conflict) == 1 and merged.count('<<<<<<<') == 1,
                    'Unexpected source merge conflict: ' + path)
            merged = merged.replace(conflict, SD_NEW + SD_GUARD, 1)
            resolution = 'explicit-new-fast-disk-constructor-plus-unchanged-small-state-guard'
        require(not any(marker in merged for marker in ('<<<<<<<', '=======\n', '>>>>>>>')),
                'Unresolved merge markers')
        ast.parse(merged, filename=path)
        return merged.encode('utf-8'), resolution
    finally:
        for fd in fds:
            os.close(fd)


def plan(repo=REPO, packet=PACKET):
    manifest_raw = regular_bound(packet / 'manifest.json', MANIFEST_SHA)
    manifest = json.loads(manifest_raw)
    require(manifest['source_commit'] == OLD and len(manifest['files']) == 1501, 'Historical closure differs')
    historical = {p[7:]: h for p, h in manifest['files'].items() if p.startswith('source/')}
    old, new = tree(repo, OLD), tree(repo, NEW)
    require(len(old) == 1191 and len(new) == 1270 and len(historical) == 1254, 'Upstream/source census differs')
    require(set(old) <= set(historical), 'Historical source omits upstream files')
    additions = set(historical) - set(old)
    require(len(additions) == 63 and not additions & set(new), 'Lab addition collision/census differs')
    require(set(old) - set(new) == REMOVED and len(set(new) - set(old)) == 81, 'Upstream transition differs')
    base_native, old_hashes, modifications = {}, {}, set()
    for path, raw in blobs(repo, old):
        old_hashes[path] = sha(raw)
        if old_hashes[path] != historical[path]:
            modifications.add(path); base_native[path] = raw
    require(modifications == NATIVE, 'Historical native overlay differs')
    rows, merged, patches = {}, {}, {}
    for path, raw in blobs(repo, new):
        rows[path] = {**new[path], 'upstream_sha256': sha(raw), 'sha256': sha(raw), 'basis': 'new-upstream'}
        if path in NATIVE:
            overlay = regular_bound(packet / 'source' / path, historical[path])
            value, resolution = merge_native(path, base_native[path], raw, overlay)
            merged[path] = value
            rows[path].update(sha256=sha(value), bytes=len(value), basis='rebased-native-overlay',
                              historical_sha256=historical[path], resolution=resolution)
            patches[path] = ''.join(difflib.unified_diff(base_native[path].decode().splitlines(keepends=True),
                overlay.decode().splitlines(keepends=True), fromfile='old-upstream/' + path,
                tofile='packet98/' + path))
    for path in sorted(additions):
        raw = regular_bound(packet / 'source' / path, historical[path])
        rows[path] = {'sha256': sha(raw), 'bytes': len(raw), 'mode': '100644', 'basis': 'unchanged-lab-addition'}
    require(sum(v['bytes'] for v in rows.values()) <= MAX_SOURCE_BYTES, 'Candidate source exceeds bound')
    disposition = {}
    for path, digest in manifest['files'].items():
        if not path.startswith('source/'):
            status = 'historical-non-source-dependency-not-yet-ported'
        elif path[7:] in REMOVED:
            status = 'upstream-deleted-from-live-source-preserved-in-historical-packet'
        else:
            status = rows[path[7:]]['basis']
        disposition[path] = {'historical_sha256': digest, 'disposition': status}
    receipt = {'schema': 'ltx.upstream99.source-plan.v1', 'status': 'UNSEALED-NOT-LAUNCHABLE',
               'old_commit': OLD, 'new_commit': NEW, 'historical_manifest_sha256': MANIFEST_SHA,
               'source_repo': str(repo), 'historical_packet': str(packet),
               'source_tree_oid': git(repo, 'rev-parse', NEW + '^{tree}').decode().strip(),
               'builder_sha256': sha(Path(__file__).read_bytes()), 'source_files': rows,
               'historical_file_disposition': disposition, 'overlay_patches': patches,
               'counts': {'old_upstream': len(old), 'new_upstream': len(new), 'lab_additions': len(additions),
                          'native_overlays': len(modifications), 'new_source_files': len(rows),
                          'historical_files_accounted': len(disposition), 'historical_non_source_pending': 247},
               'source_bytes': sum(v['bytes'] for v in rows.values()),
               'unchanged_control': {'sampler_split': '23/25', 'batch': 1, 'references': 'w93c'},
               'pending': ['transition-aware runtime checker and launcher', 'accepted overlay API/behavior review',
                           'CPU source-contract tests', 'new-base capture and exact-output gates',
                           'runtime/dependency identity and host admission'],
               'qualification': False, 'model_requests': 0}
    return receipt, merged, new, manifest_raw


def write_new(path, raw):
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def prepare(output, repo, packet):
    """Explicit source-only materialization; never called by --plan."""
    require(output.is_absolute() and not output.exists() and not output.is_symlink(), 'Output must be new and absolute')
    require('..' not in output.parts and str(output) == os.path.abspath(output), 'Output path must be normalized')
    require(output.parent.is_dir() and not any(p.is_symlink() for p in output.parents), 'Unsafe output parent')
    require(not output.is_relative_to(packet) and not packet.is_relative_to(output), 'Output overlaps historical packet')
    require(not output.is_relative_to(repo) and not repo.is_relative_to(output), 'Output overlaps source checkout')
    receipt, merged, upstream, manifest_raw = plan(repo, packet)
    allowance = 3 * MAX_SOURCE_BYTES
    require(shutil.disk_usage(output.parent).free >= ROOT_RESERVE + allowance, '50 GiB reserve plus bounded build allowance required')
    output.mkdir(mode=0o700)
    write_new(output / 'STATUS.txt', b'UNSEALED-NOT-LAUNCHABLE\nSource only; no new runtime qualification.\n')
    provenance = output / 'provenance'; provenance.mkdir()
    write_new(provenance / 'packet98-manifest.json', manifest_raw)
    archive = provenance / 'upstream-source.tar'
    with archive.open('xb') as stream:
        subprocess.run(['git', '-C', str(repo), 'archive', '--format=tar', NEW], stdout=stream, check=True, timeout=120)
        stream.flush(); os.fsync(stream.fileno())
    require(archive.stat().st_size <= MAX_SOURCE_BYTES * 2, 'Archive exceeds bound')
    source = output / 'source'; source.mkdir()
    seen = set()
    with tarfile.open(archive, 'r:') as tar:
        for member in tar:
            if member.isdir():
                continue
            require(member.isfile() and member.name in upstream and member.name not in seen, 'Unexpected/duplicate archive member')
            raw = tar.extractfile(member).read()
            row = upstream[member.name]
            require(len(raw) == row['bytes'] and
                    hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == row['blob'],
                    'Archive changed Git blob bytes (including export substitution)')
            dest = source / member.name; dest.parent.mkdir(parents=True, exist_ok=True)
            write_new(dest, merged.get(member.name, raw)); dest.chmod(int(row['mode'], 8) & 0o777)
            seen.add(member.name)
    require(seen == set(upstream), 'Archive silently omitted upstream files')
    for path, row in receipt['source_files'].items():
        if row['basis'] == 'unchanged-lab-addition':
            dest = source / path; dest.parent.mkdir(parents=True, exist_ok=True)
            write_new(dest, regular_bound(packet / 'source' / path, row['sha256']))
            dest.chmod(int(row['mode'], 8) & 0o777)
        require(sha((source / path).read_bytes()) == row['sha256'], 'Prepared source mismatch')
    require({str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()} == set(receipt['source_files']),
            'Prepared source inventory mismatch')
    receipt['archive_sha256'] = sha(archive.read_bytes())
    receipt['archive_bytes'] = archive.stat().st_size
    receipt['output'] = str(output)
    write_new(output / 'source-plan.json', (json.dumps(receipt, indent=2, sort_keys=True) + '\n').encode())
    for directory in [p for p in output.rglob('*') if p.is_dir()] + [output, output.parent]:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return {'status': receipt['status'], 'output': str(output), 'counts': receipt['counts'],
            'source_plan_sha256': sha((output / 'source-plan.json').read_bytes())}


def self_test():
    """Small repeatable CPU controls; no preparation or test-directory writes."""
    checks = []
    base = b'a = 1\nb = 2\nc = 3\nd = 4\ne = 5\n'
    latest = base.replace(b'a = 1', b'a = 6')
    overlay = base.replace(b'e = 5', b'e = 7')
    value, _ = merge_native('sample.py', base, latest, overlay)
    require(value == latest.replace(b'e = 5', b'e = 7'), 'Independent merge changed bytes')
    checks.append('independent-edits-merge-exact')
    for path in ('sample.py', 'comfy/sd.py'):
        try:
            merge_native(path, base, base.replace(b'a = 1', b'a = 2'),
                         base.replace(b'a = 1', b'a = 3'))
        except ValueError:
            checks.append('unexpected-conflict-refused:' + path)
        else:
            raise ValueError('Unexpected conflict accepted')
    try:
        regular_bound(PACKET / 'manifest.json', '0' * 64)
    except ValueError:
        checks.append('incorrect-historical-manifest-hash-refused')
    else:
        raise ValueError('Incorrect manifest digest accepted')
    receipt, _, _, _ = plan()
    require(len(receipt['source_files']) == 1333 and
            len(receipt['historical_file_disposition']) == 1501 and
            receipt['source_files']['comfy/sd.py']['resolution'].startswith('explicit-new-fast-disk'),
            'Pinned source-plan coverage or known resolution failed')
    checks.append('actual-pinned-plan-and-explicit-sd-resolution')
    return {'status': 'passed', 'controls': checks, 'counts': receipt['counts'],
            'source_bytes': receipt['source_bytes'], 'prepared_sources': False,
            'model_requests': 0, 'builder_sha256': receipt['builder_sha256']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--plan', action='store_true', help='Read-only, default')
    action.add_argument('--prepare', action='store_true', help='Explicit new source-only output; no runtime sealing')
    action.add_argument('--self-test', action='store_true', help='Read-only merge/refusal controls and actual pinned plan')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    require(bool(args.out) == args.prepare, '--out is required only for --prepare')
    result = self_test() if args.self_test else prepare(args.out, REPO, PACKET) if args.prepare else plan()[0]
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
