"""Read-only packet pin admission. No packet imports, devices or model reads.

The immutable allowlist is code below, not a packet-controlled override. Hashes
are streamed afresh on each admission; no cache survives between checks. Model
bytes remain the existing model-identity gate's responsibility.
"""
import gzip
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import re
import stat

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / 'experiments/own-xpu-runtime/stage2'
SHA256 = re.compile(r'[0-9a-fA-F]{64}\Z')
PACKET = re.compile(r'packet\d+[a-z]*(?:-|$)')
MODEL_SUFFIXES = {'.gguf', '.safetensors'}
MAX_METADATA = 16 * 1024 * 1024


class PinRefusal(ValueError):
    def __init__(self, errors, packet=None):
        self.receipt = dict(schema='own-runtime.pin-guard.refusal.v1', passed=False,
                            device_executed=False, child_still_running=False,
                            launch_attempted=False, packet=str(packet) if packet else None,
                            errors=errors, error='pin guard refused before launch')
        super().__init__('pin guard: ' + '; '.join(errors[:8]) +
                         (f'; {len(errors)} errors total' if len(errors) > 8 else ''))


def absolute(value, root):
    return Path(os.path.abspath(root / value))


def packet_for_job(job, root=ROOT, stage=STAGE):
    """Prefer entry-point ownership; shared coordinators use packet job names."""
    argv = job.get('argv', [])
    entry = job.get('script') or (argv[2] if len(argv) > 2 and
            Path(argv[0]).name.startswith('python') else (argv[0] if argv else ''))
    path = absolute(entry, root)
    try:
        part = path.relative_to(stage).parts[0]
        if PACKET.match(part):
            return stage / part
    except (ValueError, IndexError):
        pass
    match = re.match(r'^(?:packet|p)(\d+[a-z]*)(?=[-_.]|$)', job.get('name', ''))
    if match:
        candidates = sorted(stage.glob('packet' + match[1] + '-*'))
        if len(candidates) == 1:
            return candidates[0]
        raise PinRefusal(['cannot identify unique packet for ' + job['name']])
    return None


def read_metadata(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rb') as stream:
        raw = stream.read(MAX_METADATA + 1)
    if len(raw) > MAX_METADATA:
        raise ValueError('pin metadata exceeds size bound: ' + str(path))
    return raw


def is_pin_file(path):
    name = path.name.lower()
    return ('seal' in name or 'sources' in name or 'pins' in name or
            name in {'build-receipt.json', 'ready.json', 'ready-for-device.json',
                     'oracle-binding.json', 'readiness.json', 'source-manifest.json'})


def metadata_paths(packet, root=ROOT):
    """Current metadata, excluding historical snapshots and generated run trees.

    Hash-linked JSON inside the packet is followed by collect_pins, so seals
    inside build/evidence remain included when part of the sealed closure.
    """
    paths = set()
    for directory, dirs, files in os.walk(packet, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in
                         {'build', 'evidence', 'lineage', 'lineage-inputs', 'submission', '.git', '__pycache__'}
                         and not (Path(directory) / d).is_symlink())
        for name in files:
            path = Path(directory) / name
            if (name.endswith(('.json', '.sha256')) or name == 'SHA256SUMS'
                    or is_pin_file(path) and name.endswith(('.json.gz', '-sources', '.txt'))):
                paths.add(path)
    prefix = packet.name.split('-', 1)[0]
    ops = root / 'experiments/own-xpu-runtime/ops'
    for directory in ops.glob(prefix + '-*'):
        for path in directory.glob('*.json'):
            if is_pin_file(path):
                paths.add(path)
    return sorted(paths)


def pin_path(value, manifest, packet, root):
    path = Path(value)
    if path.parts and path.parts[0] in {'stage1', 'stage2'}:
        return absolute(path, root / 'experiments/own-xpu-runtime')
    if path.is_absolute() or path.parts and path.parts[0] in {'experiments', 'notes', 'scripts', 'data', 'ops'}:
        return absolute(path, root)
    # Seal-relative maps and packet-relative build artifacts both occur. Never
    # select a base by whether the file happens to exist.
    base = manifest.parent
    if base.name in {'evidence', 'build'}:
        base = packet
    return absolute(path, base)


def extract_pins(row, map_name=''):
    """Handle nested hash maps, path/sha256 records and named path/hash pairs."""
    if isinstance(row, list):
        for item in row:
            yield from extract_pins(item, map_name)
    elif isinstance(row, dict):
        hash_map = map_name in {'sources', 'screen_sources', 'files_sha256', 'artifacts', 'gates', 'pins', 'files'} or map_name.endswith(('_sources', '-sources'))
        record_path = row.get('path', row.get('file'))
        if isinstance(record_path, str) and ('sha256' in row or 'hash' in row):
            digest = row.get('sha256', row.get('hash'))
            if not isinstance(digest, str) or not SHA256.fullmatch(digest):
                raise ValueError('invalid SHA256 pin for ' + record_path)
            yield record_path, digest.lower()
            row = {k: v for k, v in row.items() if k not in {'path', 'file', 'sha256', 'hash'}}
            hash_map = False
        for key, value in row.items():
            if isinstance(value, str) and SHA256.fullmatch(value):
                if hash_map or '/' in key or '.' in key and not key.endswith(('_sha256', '.sha256')):
                    yield key, value.lower()
                elif key in {'sha256', 'hash'}:
                    for field in ('path', 'file'):
                        if isinstance(row.get(field), str):
                            yield row[field], value.lower()
                elif key.endswith('_sha256') and isinstance(row.get(key[:-7]), str):
                    candidate = row[key[:-7]]
                    if '/' in candidate or '.' in candidate:
                        yield candidate, value.lower()
            elif isinstance(value, (dict, list)):
                if hash_map and isinstance(value, dict) and 'sha256' in value and not {'path', 'file'}.intersection(value):
                    yield from extract_pins(dict(value, path=key))
                    continue
                # A list of {path, sha256} records is not itself a hash map.
                yield from extract_pins(value, key if isinstance(value, dict) else '')
            elif hash_map:
                raise ValueError('invalid SHA256 pin for ' + key)


def collect_pins(packet, root=ROOT):
    pins, manifests, visited = {}, [], set()
    pending = deque(metadata_paths(packet, root))
    scheduled = set(pending)
    while pending:
        path = pending.popleft()
        if path in visited:
            continue
        visited.add(path)
        raw = read_metadata(path)
        manifests.append(path)
        if path.name.endswith(('.json', '.json.gz')) or raw.lstrip().startswith((b'{', b'[')):
            row = json.loads(raw)
            if is_pin_file(path) and not isinstance(row, (dict, list)):
                raise ValueError('pin metadata must be an object or list: ' + str(path))
            direct_map = (is_pin_file(path) and isinstance(row, dict) and 'schema' not in row
                          and all(isinstance(v, str) for v in row.values()))
            entries = extract_pins(row, 'sources' if direct_map else '')
        else:
            entries = []
            for line in raw.decode().splitlines():
                if not line.strip() or line.startswith('#'):
                    continue
                match = re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?(.+)', line)
                if not match:
                    raise ValueError('invalid pin list: ' + str(path))
                entries.append((match[2], match[1].lower()))
        for name, digest in entries:
            target = pin_path(name, path, packet, root)
            # Seals frequently embed identical parent maps hundreds of times.
            # Retain each path/hash obligation once, preserving oracle binding
            # provenance for its explicit allowlist. Conflicting hashes remain
            # separate obligations and therefore cannot silently overwrite.
            identity = (target, digest)
            if identity not in pins or path.name == 'oracle-binding.json':
                pins[identity] = path
            if (target.suffix == '.json' and target.is_relative_to(packet)
                    and target.resolve().is_relative_to(packet.resolve())
                    and not {'lineage', 'lineage-inputs'}.intersection(target.relative_to(packet).parts) and target.is_file()
                    and target not in scheduled):
                scheduled.add(target)
                pending.append(target)
    return sorted((target, digest, source) for (target, digest), source in pins.items()), manifests


def model_file(path):
    return path.suffix.lower() in MODEL_SUFFIXES


def completed_evidence(path, stage):
    try:
        parts = path.relative_to(stage).parts
    except ValueError:
        return False
    if len(parts) < 4 or not PACKET.match(parts[0]) or parts[1] not in {'evidence', 'build'}:
        return False
    for directory in path.parents:
        if directory == stage / parts[0] / parts[1]:
            break
        for name in ('queue.json', 'window.json'):
            receipt = directory / name
            if not receipt.is_file():
                continue
            row = json.loads(read_metadata(receipt))
            ended = bool(row.get('end_utc') or row.get('finished_utc_ns'))
            if (path.resolve().is_relative_to(directory.resolve())
                    and row.get('passed') is True and ended and row.get('child_still_running') is not True
                    and (name == 'window.json' and row.get('device_executed') is True
                         or name == 'queue.json' and bool(row.get('completed')))):
                return True
    return False


def immutable_reason(path, digest, packet, oracle_targets, stage):
    resolved = path.resolve()
    if model_file(path) or model_file(resolved):
        return 'model; content verification delegated to existing model gate'
    if (path, digest) in oracle_targets:
        return 'oracle-binding.json target'
    oracle = stage / 'packet49-integrate/oracle'
    wrappers = stage / 'screen/v4-lanes'
    for folder, reason in ((oracle, 'packet49 oracle'), (wrappers, 'frozen v4 wrappers')):
        if path.is_relative_to(folder) and resolved.is_relative_to(folder.resolve()):
            return reason
    try:
        relative = path.relative_to(stage)
    except ValueError:
        relative = Path('.')
    if (relative.parts and PACKET.match(relative.parts[0]) and 'build' in relative.parts
            and path.is_file() and resolved.is_relative_to(
                stage.joinpath(*relative.parts[:relative.parts.index('build') + 1]).resolve())):
        with path.open('rb') as stream:
            magic = stream.read(8)
        if magic.startswith((b'\x7fELF', b'!<arch>\n')):
            return 'hash-pinned parent binary'
    if completed_evidence(path, stage):
        return 'completed chain evidence'
    return None


def sha256(path):
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('pin is not a regular file: ' + str(path))
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError('pin changed while hashing: ' + str(path))
    return digest.hexdigest()


def check_job(job, root=ROOT, stage=STAGE):
    packet = packet_for_job(job, root, stage)
    if packet is None:
        return dict(passed=True, packet=None, pins=0)
    try:
        if not packet.is_dir():
            raise ValueError('packet directory missing: ' + str(packet))
        pins, manifests = collect_pins(packet, root)
        oracle_targets = {(p, h) for p, h, source in pins if source.name == 'oracle-binding.json'}
        identities = {}
        for path, digest, source in pins:
            identities.setdefault((path, digest), source)
        unique = [(path, digest, source) for (path, digest), source in identities.items()]
        errors, models = [], set()
        for path, digest, source in unique:
            if model_file(path) or model_file(path.resolve()):
                models.add(str(path))
            if path.is_relative_to(packet) and path.resolve().is_relative_to(packet.resolve()):
                continue
            if not immutable_reason(path, digest, packet, oracle_targets, stage):
                errors.append(f'cross-packet mutable pin {path} (sealed by {source})')
        if errors:
            raise PinRefusal(sorted(set(errors)), packet)
        hashes = {}
        for path, digest, source in unique:
            if str(path) in models:
                continue
            if path not in hashes:
                hashes[path] = sha256(path)
            if hashes[path] != digest:
                errors.append(f'hash changed: {path} (sealed by {source})')
        if errors:
            raise PinRefusal(sorted(set(errors)), packet)
        return dict(passed=True, packet=str(packet), pins=len(pins),
                    manifests=len(manifests), model_hashes_deferred=sorted(models))
    except PinRefusal:
        raise
    except (OSError, ValueError, TypeError, AttributeError, RecursionError) as exc:
        raise PinRefusal(['unreadable or invalid pin metadata: ' + str(exc)], packet) from None
