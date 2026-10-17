"""Packet-local storage admission and disposable CPU fixture retention."""
import base64
import gzip
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

P = Path(__file__).resolve().parent
B = (P / 'build').resolve()

def packet_relative(path):
    path=Path(path)
    if path.is_relative_to(P):return path.relative_to(P)
    resolved=path.resolve()
    if resolved.is_relative_to(B):return Path('build')/resolved.relative_to(B)
    raise ValueError('path outside packet storage: '+str(path))

FREE_FLOOR = 8_000_000_000
BUILD_BASE_BUDGET = 2_500_000_000
CHAIN_WINDOWS = ('K0','K1a','K1b','K2','W0p','KD','W2m','WS','WSs','WS128x','WS128')

def state_write_bytes(context):
    if context not in (256,4096,32768):raise ValueError('unregistered storage context')
    # Thirteen full BF16 QSA dumps, plus the historical scratch/recurrent reserve.
    # Strict snapshot allocations are hashed in place, not dumped a second time.
    return 550_000_000 + 13*2368*(context-256)

def request_write_bytes(retained_steps):
    if type(retained_steps) is not int or retained_steps<0:raise ValueError('invalid retained-step count')
    # Rank output and checker hardlinks coexist: build_size counts both paths.
    # Each layer is [1,4,2560] BF16 = 20,480 bytes. 32 MB includes eight
    # steps in both trees plus logs/metadata; reserve both logical extents.
    return 32_000_000 + 2*48*20480*max(0,retained_steps-8)

def projected_write_bytes(name, requests=1, context=32768, retained_steps=16):
    if type(requests) is not int or requests<1:raise ValueError('positive request count required')
    state=state_write_bytes(context)
    if name=='K2':return 2_500_000_000
    if name in ('K1a','K1b'):return 1_100_000_000
    if name in ('K0','W0p'):return 32_000_000
    if name=='KD':
        # Host reference and two fresh device captures coexist until comparison.
        return 550_000_000 + 3*2368*(context-256)
    # At most one raw state survives RESET; retained layer bytes grow per request.
    # Account for both rank files and combined checker copies at WS128x.
    return state + requests*request_write_bytes(retained_steps)

# This packet has one registered 4K chain. Protect the complete pending p49
# model phase, plus oracle growth, rather than reserving an unrelated 32K
# nine-window chain at every write. No p49 budget/source is changed.
LATE_WINDOWS = ('KD','W2m','WS','WSs','WS128x','WS128')
def chain_window_bytes(name):
    return projected_write_bytes(name, 13 if name.startswith('WS') else 1,
                                 4096, 0 if name=='WS128' else 16 if name=='WS128x' else 8)
MODEL_CHAIN_BYTES = sum(chain_window_bytes(n) for n in LATE_WINDOWS)
ORACLE_GROWTH_RESERVE = 500_000_000
CHAIN_RESERVE = MODEL_CHAIN_BYTES + ORACLE_GROWTH_RESERVE
# Early windows discard only their own oversized generated fixture scratch
# after binding its hashes and restoration argv. Enforce the retained cap in
# the queue. Model outputs need no compression credit in this envelope.
EARLY_RETAINED_LIMIT = 128_000_000
OWN_CHAIN_PEAK = EARLY_RETAINED_LIMIT + max(MODEL_CHAIN_BYTES, 2_500_000_000)
BUILD_LIMIT = BUILD_BASE_BUDGET + OWN_CHAIN_PEAK

def early_retention_gate(out):
    used = sum(build_size(Path(out)/name) for name in CHAIN_WINDOWS if name not in LATE_WINDOWS)
    used += sum(f.stat().st_size for f in Path(out).glob('*')
                if f.is_file() and f.stem not in LATE_WINDOWS)
    if used > EARLY_RETAINED_LIMIT:
        raise RuntimeError('packet49b early retained evidence exceeds registered 128 MB cap; preserve evidence and review storage')
    return dict(early_retained_bytes=used, limit_bytes=EARLY_RETAINED_LIMIT)

def precheck():
    free = shutil.disk_usage(B).free
    used = build_size(B)
    # No credit for actual build smaller than its registered 2.5 GB maximum.
    required = FREE_FLOOR + CHAIN_RESERVE + max(0, BUILD_LIMIT-used)
    return dict(passed=free>=required, device_executed=False, root_free_bytes=free,
                required_free_bytes=required, margin_bytes=free-required,
                build_bytes=used, build_budget_bytes=BUILD_BASE_BUDGET,
                free_floor_bytes=FREE_FLOOR, parent_model_reserve_bytes=MODEL_CHAIN_BYTES,
                oracle_growth_reserve_bytes=ORACLE_GROWTH_RESERVE,
                early_retained_limit_bytes=EARLY_RETAINED_LIMIT,
                own_chain_peak_bytes=OWN_CHAIN_PEAK,
                full_chain_uncompressed_bytes=sum(chain_window_bytes(n) for n in CHAIN_WINDOWS))

def budget(free, used, extra, build_extra):
    if any(type(n) is not int or n<0 for n in (free,used,extra,build_extra)):
        raise ValueError('storage byte counts must be nonnegative integers')
    cap=min(BUILD_LIMIT, used+free-FREE_FLOOR-CHAIN_RESERVE)
    row=dict(root_free_bytes=free,build_bytes=used,admitted_write_bytes=extra,
             projected_build_write_bytes=build_extra,build_limit_bytes=cap,
             structural_build_limit_bytes=BUILD_LIMIT,free_floor_bytes=FREE_FLOOR,
             remaining_chain_reserve_bytes=CHAIN_RESERVE)
    if free-extra < FREE_FLOOR+CHAIN_RESERVE or used+build_extra >= cap:
        raise RuntimeError('Packet49b storage admission refused: '+str(row))
    return row

def build_size(root):
    """Concurrent gates may remove completed scratch between discovery and stat."""
    used=0
    for file in root.rglob('*'):
        try:
            if file.is_file() and not file.is_symlink():used+=file.stat().st_size
        except FileNotFoundError:
            # Only a vanished member is benign; permission/I/O errors still refuse.
            continue
    return used

def admit(extra=0, *, build_extra=None):
    # Explicit df check before every build or fixture-producing stage.
    result = subprocess.run(['nice', '-n', '19', 'ionice', '-c', '3',
                             'df', '-B1', '/'], capture_output=True, text=True, check=True)
    free = int(result.stdout.splitlines()[-1].split()[3])
    used = build_size(B)
    build_extra = extra if build_extra is None else build_extra
    return budget(free,used,extra,build_extra)

RETAINED_SUFFIXES = {'.json', '.jsonl', '.log', '.txt', '.tsv', '.gz', '.py'}

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def verify_archive(path):
    """Verify a streamed archive, including exact bytes of nested gzip evidence."""
    files = retained = total = 0
    current = None
    with gzip.open(path, 'rt', encoding='utf-8') as source:
        header = json.loads(next(source))
        if header != {'schema': 'packet38.scratch-stream.v1'}:
            raise ValueError('scratch archive schema')
        for line in source:
            row = json.loads(line)
            if row['kind'] == 'file':
                if current is not None:
                    raise ValueError('unfinished scratch member')
                current = row; observed = hashlib.sha256(); count = 0; files += 1
            elif row['kind'] == 'chunk':
                if current is None or not current['retained']:
                    raise ValueError('unexpected scratch content')
                chunk = base64.b64decode(row['base64'], validate=True)
                observed.update(chunk); count += len(chunk)
            elif row['kind'] == 'end':
                if current is None or row['path'] != current['path']:
                    raise ValueError('scratch member framing')
                if current['retained']:
                    if count != current['bytes'] or observed.hexdigest() != current['sha256']:
                        raise ValueError('scratch member hash mismatch')
                    retained += 1; total += count
                current = None
            else:
                raise ValueError('unknown scratch record')
    if current is not None:
        raise ValueError('truncated scratch member')
    return dict(files=files, retained_files=retained, retained_bytes=total)

def archive_files(paths, destination):
    """Write and verify bounded-memory JSONL/gzip before any caller deletes files."""
    paths = sorted(set(Path(f) for f in paths))
    for f in paths:
        if f.is_symlink() or not f.is_file() or not (f.resolve().is_relative_to(P) or f.resolve().is_relative_to(B)):
            raise ValueError('scratch member outside packet or symlink: '+str(f))
    # Base64 worst-case plus JSON/gzip overhead, checked before the large write.
    estimate = sum(f.stat().st_size * 4 // 3 + 4096 for f in paths if f.suffix in RETAINED_SUFFIXES) + len(paths) * 1024 + 1_000_000
    destination = Path(destination)
    admit(estimate, build_extra=estimate if destination.resolve().is_relative_to(B) else 0)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name+'.tmp')
    with temporary.open('wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as archive:
            def emit(row):
                archive.write((json.dumps(row, separators=(',', ':'))+'\n').encode())
            emit(dict(schema='packet38.scratch-stream.v1'))
            for f in paths:
                row=dict(kind='file', path=str(packet_relative(f)), bytes=f.stat().st_size,
                         sha256=digest(f), retained=f.suffix in RETAINED_SUFFIXES)
                emit(row)
                if row['retained']:
                    observed=hashlib.sha256(); count=0
                    with f.open('rb') as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b''):
                            observed.update(chunk); count+=len(chunk)
                            emit(dict(kind='chunk', base64=base64.b64encode(chunk).decode('ascii')))
                    if count!=row['bytes'] or observed.hexdigest()!=row['sha256']:
                        raise ValueError('scratch member changed during archive: '+str(f))
                emit(dict(kind='end', path=row['path']))
    verified=verify_archive(temporary)
    if verified['files']!=len(paths):
        raise ValueError('scratch archive file coverage')
    temporary.replace(destination)
    return dict(path=str(packet_relative(destination)), sha256=digest(destination),
                format='packet38.scratch-stream.v1 JSONL/gzip; text and nested gzip exact bytes, other scratch hashes', **verified)

def discard(root):
    """Retain exact text/nested archives and all hashes, then remove CPU scratch."""
    root = Path(root).resolve()
    assert root.parent == B or B in root.parents
    assert root != B and not root.is_symlink()
    paths = [f for f in root.rglob('*') if f.is_file()]
    dest = P / 'evidence' / ('scratch-' + '-'.join(root.relative_to(B).parts) + '.jsonl.gz')
    result=archive_files(paths, dest)
    shutil.rmtree(root)
    return result
