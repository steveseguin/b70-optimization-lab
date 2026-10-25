#!/usr/bin/env python3
"""Authenticate immutable model bytes and create a separate local build binding.

No downloads, device calls, source changes, or engine execution. Large preparation
must run at nice 19; all reads are bounded and existing outputs are refused.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

HERE = Path(__file__).resolve().parent
HEADER = 'gsq-rco-iq3s/integration/build/private/additive/bound.hpp'
CHUNK = 4 * 1024 * 1024
TEXT_CAP = 2 * 1024 * 1024


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pairs(rows):
    result = {}
    for key, value in rows:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def hexhash(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def basename(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.-]+', value)
            and value not in ('.', '..'), 'unsafe basename')
    return value


def identity(s):
    require(stat.S_ISREG(s.st_mode), 'regular file required')
    return dict(bytes=s.st_size, dev=s.st_dev, ino=s.st_ino,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns)


class Directory:
    """Open every path component without following symlinks."""
    def __init__(self, path):
        self.path = Path(path).absolute()
        require('..' not in self.path.parts, 'parent traversal refused')
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
        self.fd = os.open('/', flags)
        try:
            for part in self.path.parts[1:]:
                child = os.open(part, flags, dir_fd=self.fd)
                os.close(self.fd)
                self.fd = child
        except BaseException:
            os.close(self.fd)
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        os.close(self.fd)


class HeldFile:
    def __init__(self, directory, name):
        self.directory, self.name = directory, basename(name)
        self.fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
                          dir_fd=directory.fd)
        try:
            self.before = identity(os.fstat(self.fd))
        except BaseException:
            os.close(self.fd)
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        os.close(self.fd)

    def stable(self):
        require(identity(os.fstat(self.fd)) == self.before, 'held file changed: ' + self.name)
        require(identity(os.stat(self.name, dir_fd=self.directory.fd, follow_symlinks=False))
                == self.before, 'pathname replaced: ' + self.name)
        # The held directory cannot silently be rebound to another pathname.
        require(os.path.samestat(os.fstat(self.directory.fd), self.directory.path.stat()),
                'model directory replaced')

    def read(self, offset, size, deadline):
        require(time.monotonic() < deadline, 'preparation deadline exceeded')
        require(0 <= size <= CHUNK and 0 <= offset <= self.before['bytes']
                and size <= self.before['bytes'] - offset, 'bounded read extent')
        raw = os.pread(self.fd, size, offset)
        require(len(raw) == size, 'short read: ' + self.name)
        return raw

    def hash_range(self, offset, size, deadline):
        h = hashlib.sha256()
        for at in range(offset, offset + size, CHUNK):
            h.update(self.read(at, min(CHUNK, offset + size - at), deadline))
        self.stable()
        return h.hexdigest()


def read_small(path, limit=TEXT_CAP):
    path = Path(path).absolute()
    with Directory(path.parent) as directory, HeldFile(directory, path.name) as held:
        require(0 < held.before['bytes'] <= limit, 'bounded metadata size')
        raw = held.read(0, held.before['bytes'], time.monotonic() + 30)
        held.stable()
        return raw


def asset(profile_path, record):
    raw = read_small(Path(profile_path).parent / basename(record['file']))
    require(hexhash(record['sha256']) and digest(raw) == record['sha256'], 'profile asset hash mismatch')
    return raw


def parse_placement(raw, shards, count):
    rows, names = [], set()
    for line in raw.decode('utf-8').splitlines():
        fields = line.split()
        require(len(fields) >= 10, 'placement fields')
        shard, name, component = fields[:3]
        require(shard in shards and re.fullmatch(r'[A-Za-z0-9_.-]+', name)
                and re.fullmatch(r'[A-Za-z0-9_]+', component), 'placement names')
        kind, offset, size, layer, mask, rank, *dims = map(int, fields[3:])
        require(name not in names and 0 <= kind <= 255 and 0 < rank <= 8 and len(dims) == rank
                and all(0 < d < 2**32 for d in dims) and -1 <= layer < 48 and 0 <= mask <= 3,
                'placement descriptor')
        payload_bytes = shards[shard]['bytes'] - shards[shard]['data_start']
        require(0 <= offset < payload_bytes and 0 < size <= payload_bytes - offset, 'placement range')
        names.add(name)
        rows.append(dict(shard=shard, name=name, component=component, kind=kind,
                         offset=offset, bytes=size, layer=layer, mask=mask, dims=dims))
    require(len(rows) == count and count > 0, 'placement count')
    return rows


def parse_draft(raw, shards, count):
    rows, names = [], set()
    for line in raw.decode('utf-8').splitlines():
        fields = line.split()
        require(len(fields) == 8, 'draft fields')
        name, shard, off, size, dtype, height, width, sha = fields
        off, size, height, width = map(int, (off, size, height, width))
        require(name.startswith('mtp.') and name not in names and shard in shards
                and hexhash(sha) and dtype in ('BF16', 'F8_E4M3'), 'draft descriptor')
        require(0 <= off < shards[shard]['bytes'] and 0 < size <= 64 * 1024**2
                and size <= shards[shard]['bytes'] - off and height > 0 and width > 0
                and size == height * width * (2 if dtype == 'BF16' else 1), 'draft range/shape')
        names.add(name)
        rows.append(dict(name=name, shard=shard, offset=off, bytes=size, dtype=dtype,
                         rows=height, cols=width, sha256=sha))
    require(len(rows) == count and count > 0, 'draft tensor count')
    return rows


def shard_map(component, target=False):
    result = {}
    for row in component['shards']:
        name = basename(row['name'])
        require(name not in result and type(row['bytes']) is int and 0 < row['bytes'] <= 128 * 1024**3
                and hexhash(row['sha256']), 'shard identity')
        if target:
            require(type(row['header_bytes']) is int and 0 < row['header_bytes'] <= 16 * 1024**2
                    and row['header_bytes'] <= row['bytes'] and hexhash(row['header_sha256']), 'header identity')
            require(type(row['data_start']) is int and row['header_bytes'] <= row['data_start'] < row['bytes'], 'GGUF payload base')
        result[name] = row
    require(0 < len(result) <= 128 and sum(r['bytes'] for r in result.values()) <= 256 * 1024**3,
            'bounded shard inventory')
    return result


def load_profile(path, trusted_sha256):
    raw = read_small(path)
    require(hexhash(trusted_sha256) and digest(raw) == trusted_sha256, 'trusted profile SHA256 mismatch')
    profile = json.loads(raw, object_pairs_hook=pairs)
    require(profile['schema'] == 'ownrt.portable-model-profile.v1'
            and profile['architecture'] == 'qwen4exp'
            and profile['native_context'] == 4096 and profile['activation_dtype'] == 'F32',
            'unsupported profile capability')
    target, draft = shard_map(profile['target'], True), shard_map(profile['draft'])
    require(profile['target']['placement']['file'] == 'placement.tsv'
            and profile['draft']['tensors']['file'] == 'draft-tensors.tsv'
            and profile['tokenizer']['chat_template']['file'] == 'chat-template.jinja', 'v1 asset names')
    placement, tensors = asset(path, profile['target']['placement']), asset(path, profile['draft']['tensors'])
    rows = parse_placement(placement, target, profile['target']['placement']['tensor_count'])
    draft_rows = parse_draft(tensors, draft, profile['draft']['tensors']['tensor_count'])
    template = asset(path, profile['tokenizer']['chat_template'])
    require(hexhash(profile['tokenizer']['sha256']), 'tokenizer identity')
    return profile, raw, placement, rows, draft_rows, template


def render_header(placement, auth, model_root, rows, shards, bindings, *, placement_sha, auth_sha):
    require(hexhash(placement_sha) and hexhash(auth_sha), 'verified authority text digests required')
    lines = []
    for r in rows:
        lines.append('{' + ','.join(json.dumps(r[k]) for k in ('shard', 'name', 'component'))
                     + ',iq3::Type(' + str(r['kind']) + '),{' + ','.join(str(d)+'ULL' for d in r['dims'])
                     + '},' + ','.join((str(r['offset'])+'ULL', str(r['bytes'])+'ULL', str(r['layer']), str(r['mask']))) + '}')
    identities = ['{' + json.dumps(name) + ',' + ','.join(str(bindings[name][k])+'ULL'
                  for k in ('bytes', 'dev', 'ino', 'mtime_ns', 'ctime_ns')) + '}' for name in shards]
    headers = ['{' + str(s['header_bytes'])+'ULL,'+json.dumps(s['header_sha256'])+'}' for s in shards.values()]
    text = read_small(HERE / 'bound.hpp.in').decode()
    replacements = {'PLACEMENT': json.dumps(str(placement)), 'AUTH': json.dumps(str(auth)),
                    'ROOT': json.dumps(str(model_root)), 'PLAN_SHA': json.dumps(placement_sha),
                    'AUTH_SHA': json.dumps(auth_sha), 'SHARDS': ',\n'.join(identities),
                    'HEADERS': ',\n'.join(headers), 'PLAN': ',\n'.join(lines),
                    'COUNT': str(len(shards)), 'HEADER_COUNT': str(len(shards))}
    for key, value in replacements.items():
        marker = '@' + key + '@'
        require(text.count(marker) == 1, 'template marker: ' + key)
        text = text.replace(marker, value)
    return text.encode()


def plan(profile_path, trusted_sha256, model_root, output, draft_root=None, tokenizer_root=None):
    """Read small trusted metadata and file stats only; never read model payloads."""
    profile, _, _, _, draft_rows, _ = load_profile(profile_path, trusted_sha256)
    output = Path(output).absolute()
    require(not output.exists() and not output.is_symlink(), 'fresh deployment output required')
    roots = [('target', model_root, shard_map(profile['target'], True))]
    if draft_root is not None:
        roots.append(('draft', draft_root, shard_map(profile['draft'])))
    locations, full_bytes, extra_bytes = [], 0, 0
    with Directory(output.parent) as directory:
        volume = os.fstatvfs(directory.fd)
        destination = dict(parent=str(directory.path), dev=os.fstat(directory.fd).st_dev,
                           available_bytes=volume.f_bavail * volume.f_frsize)
    for kind, path, shards in roots:
        with Directory(path) as directory:
            volume = os.fstatvfs(directory.fd)
            for name, record in shards.items():
                with HeldFile(directory, name) as held:
                    require(held.before['bytes'] == record['bytes'], 'shard size mismatch: '+name)
                    held.stable()
            count_bytes = sum(r['bytes'] for r in shards.values())
            full_bytes += count_bytes
            extra_bytes += (sum(r['header_bytes'] for r in shards.values()) if kind == 'target'
                            else sum(t['bytes'] for t in draft_rows))
            locations.append(dict(kind=kind, root=str(directory.path), dev=os.fstat(directory.fd).st_dev,
                                  available_bytes=volume.f_bavail * volume.f_frsize,
                                  shard_count=len(shards), full_file_bytes=count_bytes))
    if tokenizer_root is not None:
        with Directory(tokenizer_root) as directory, HeldFile(directory, profile['tokenizer']['file']) as held:
            require(held.before['bytes'] <= 64 * 1024**2, 'tokenizer size cap')
            full_bytes += held.before['bytes']; held.stable()
            locations.append(dict(kind='tokenizer', root=str(directory.path),
                                  dev=os.fstat(directory.fd).st_dev, full_file_bytes=held.before['bytes']))
    artifacts = ['profile.json', 'placement.tsv', 'draft-tensors.tsv', 'shard-auth.tsv',
                 'chat-template.jinja', 'include/'+HEADER, 'binding.json']
    if draft_root is not None:
        artifacts.append('draft-manifest.tsv')
    return dict(schema='ownrt.deployment-preparation-plan.v1', profile_sha256=trusted_sha256,
                locations=locations, destination=destination, output=str(output), artifacts=artifacts,
                full_file_hash_bytes=full_bytes, additional_prefix_and_payload_hash_bytes=extra_bytes,
                planned_read_bytes=full_bytes+extra_bytes, read_chunk_bytes=CHUNK,
                model_payload_bytes_read=0, full_content_authenticated=False,
                device_executed=False, output_created=False,
                large_preparation_requires='nice -n 19; schedule one bounded pass; no automatic retries')


def prepare(profile_path, trusted_sha256, model_root, output, draft_root=None, tokenizer_root=None,
            seconds=7200):
    require(1 <= seconds <= 86400, 'bounded preparation time')
    profile, raw, placement, rows, draft_rows, template = load_profile(profile_path, trusted_sha256)
    target = shard_map(profile['target'], True)
    draft = shard_map(profile['draft']) if draft_root is not None else {}
    total = sum(r['bytes'] for r in [*target.values(), *draft.values()])
    require(total <= 64 * 1024**2 or os.getpriority(os.PRIO_PROCESS, 0) == 19,
            'large model authentication requires nice -n 19')
    output = Path(output).absolute()
    require(not output.exists() and not output.is_symlink(), 'fresh deployment output required')
    deadline = time.monotonic() + seconds
    verified, handles = {}, []
    with ExitStack() as stack:
        parent = stack.enter_context(Directory(output.parent))
        roots = {'target': stack.enter_context(Directory(model_root))}
        if draft:
            roots['draft'] = stack.enter_context(Directory(draft_root))
        # Keep every authenticated input open until the binding is sealed.
        for kind, shards in [('target', target), ('draft', draft)]:
            verified[kind] = {}
            for name, record in shards.items():
                held = stack.enter_context(HeldFile(roots[kind], name)); handles.append(held)
                require(held.before['bytes'] == record['bytes'], 'shard size mismatch: ' + name)
                require(held.hash_range(0, record['bytes'], deadline) == record['sha256'], 'full shard SHA256 mismatch: ' + name)
                if kind == 'target':
                    require(held.hash_range(0, record['header_bytes'], deadline) == record['header_sha256'], 'header SHA256 mismatch')
                else:
                    for tensor in (t for t in draft_rows if t['shard'] == name):
                        require(held.hash_range(tensor['offset'], tensor['bytes'], deadline) == tensor['sha256'], 'draft payload SHA256 mismatch: ' + tensor['name'])
                verified[kind][name] = held.before
        tokenizer_binding = None
        if tokenizer_root is not None:
            tokroot = stack.enter_context(Directory(tokenizer_root))
            tok = profile['tokenizer']; held = stack.enter_context(HeldFile(tokroot, basename(tok['file']))); handles.append(held)
            require(held.before['bytes'] <= 64 * 1024**2, 'tokenizer size cap')
            require(held.hash_range(0, held.before['bytes'], deadline) == tok['sha256'], 'tokenizer SHA256 mismatch')
            tokenizer_binding = dict(path=str(tokroot.path / tok['file']), **held.before)
        for held in handles:
            held.stable()
        os.mkdir(output.name, mode=0o700, dir_fd=parent.fd)
        with Directory(output) as destination:
            artifacts = {}
            def write(name, data):
                fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=destination.fd)
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data)
                artifacts[name] = digest(data)
            write('profile.json', raw)
            write('placement.tsv', placement)
            write('draft-tensors.tsv', asset(profile_path, profile['draft']['tensors']))
            auth = ''.join(' '.join([name, *(str(verified['target'][name][k]) for k in
                           ('bytes', 'dev', 'ino', 'mtime_ns', 'ctime_ns'))])+'\n' for name in target).encode()
            write('shard-auth.tsv', auth)
            write('chat-template.jinja', template)
            if draft:
                manifest = ''.join(' '.join(map(str, [t['name'], t['shard'], t['offset'], t['bytes'],
                    t['dtype'], t['rows'], t['cols'], t['sha256'], *(verified['draft'][t['shard']][k]
                    for k in ('bytes', 'dev', 'ino', 'mtime_ns', 'ctime_ns'))]))+'\n' for t in draft_rows)
                write('draft-manifest.tsv', manifest.encode())
            header = output / 'include' / HEADER
            header.parent.mkdir(parents=True)
            header_bytes = render_header(output/'placement.tsv', output/'shard-auth.tsv', roots['target'].path,
                                        rows, target, verified['target'], placement_sha=digest(placement), auth_sha=digest(auth))
            with Directory(header.parent) as header_directory:
                fd = os.open(header.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=header_directory.fd)
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(header_bytes)
            artifacts['include/'+HEADER] = digest(header_bytes)
            for held in handles:
                held.stable()
            binding = dict(schema='ownrt.local-deployment.v1', profile_sha256=trusted_sha256,
                profile_id=profile['id'], target_root=str(roots['target'].path),
                draft_root=str(roots['draft'].path) if draft else None, tokenizer=tokenizer_binding,
                shards=verified, artifacts=dict(artifacts), header=HEADER,
                generator_sha256=digest(read_small(Path(__file__))), template_sha256=digest(read_small(HERE/'bound.hpp.in')),
                full_content_authenticated=True, device_executed=False, clean_host_qualified=False)
            write('binding.json', encoded(binding))
    return binding


def validate_overlay(include, profile_sha256, binding_sha256):
    """Metadata-only build check. The independently pinned binding is local authority."""
    include = Path(include).absolute()
    require(include.name == 'include', 'generated include must be deployment/include')
    output = include.parent
    raw = read_small(output / 'binding.json')
    require(hexhash(binding_sha256) and digest(raw) == binding_sha256, 'deployment binding SHA256 mismatch')
    binding = json.loads(raw, object_pairs_hook=pairs)
    require(binding['schema'] == 'ownrt.local-deployment.v1'
            and binding['profile_sha256'] == profile_sha256
            and binding['full_content_authenticated'] is True and binding['header'] == HEADER,
            'deployment authority identity')
    profile, _, _, rows, _, _ = load_profile(output/'profile.json', profile_sha256)
    shards = shard_map(profile['target'], True)
    require(set(binding['shards']['target']) == set(shards), 'binding shard coverage')
    for name, local in binding['shards']['target'].items():
        require(set(local) == {'bytes', 'dev', 'ino', 'mtime_ns', 'ctime_ns'}
                and all(type(v) is int and v >= 0 for v in local.values())
                and local['bytes'] == shards[name]['bytes'], 'binding stat identity')
    expected = {'profile.json', 'placement.tsv', 'shard-auth.tsv', 'draft-tensors.tsv', 'chat-template.jinja', 'include/'+HEADER}
    if binding['draft_root'] is not None:
        expected.add('draft-manifest.tsv')
    require(set(binding['artifacts']) == expected, 'deployment artifact inventory')
    verified_artifacts = {}
    for name, want in binding['artifacts'].items():
        data = read_small(output/name)
        require(hexhash(want) and digest(data) == want, 'deployment artifact hash mismatch: ' + name)
        verified_artifacts[name] = data
    for path in include.rglob('*'):
        require(not path.is_symlink(), 'generated include symlink refused')
        if path.is_file():
            require(path.relative_to(include).as_posix() == HEADER, 'extra generated header refused')
    actual = verified_artifacts['include/'+HEADER]
    regenerated = render_header(output/'placement.tsv', output/'shard-auth.tsv', Path(binding['target_root']),
                                rows, shards, binding['shards']['target'],
                                placement_sha=digest(verified_artifacts['placement.tsv']),
                                auth_sha=digest(verified_artifacts['shard-auth.tsv']))
    require(actual == regenerated, 'generated authority differs from pinned profile/binding')
    return dict(include=str(include), binding=str(output/'binding.json'), binding_sha256=binding_sha256,
                profile_sha256=profile_sha256, header=HEADER, header_sha256=digest(actual),
                artifacts=binding['artifacts'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--profile-sha256', required=True, help='independently trusted release digest')
    parser.add_argument('--model-root', type=Path, required=True)
    parser.add_argument('--draft-root', type=Path)
    parser.add_argument('--tokenizer-root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=7200)
    parser.add_argument('--plan-only', action='store_true', help='validate small metadata and local stats, print read budget; no model payload reads or output writes')
    a = parser.parse_args()
    if a.plan_only:
        print(json.dumps(plan(a.profile, a.profile_sha256, a.model_root, a.output,
                              a.draft_root, a.tokenizer_root), indent=2))
        return
    result = prepare(a.profile, a.profile_sha256, a.model_root, a.output,
                     a.draft_root, a.tokenizer_root, a.seconds)
    print(json.dumps(dict(output=str(a.output.absolute()), profile_sha256=result['profile_sha256'],
                          device_executed=False, clean_host_qualified=False)))


if __name__ == '__main__':
    main()
