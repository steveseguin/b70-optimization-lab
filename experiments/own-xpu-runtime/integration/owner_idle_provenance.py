"""Read-only provenance for the optional conservative initial-idle adjustment.

The coordinator must call prepare_owner_origin before its sole Popen and retain
exclusive ownership of the fresh private run directory. No process is started,
signalled, waited for or admitted here. A refusal must not be disguised as proof.
This checks a trusted local launch, not hostile mutation by the same Unix user.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import struct
import time

import initial_idle_origin as origin

LIBC = Path('/usr/lib/x86_64-linux-gnu/libc.so.6')
LIBC_SHA256 = '3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf'
SYMBOLS = {b'_ZNSt6chrono3_V212steady_clock3nowEv', b'clock_gettime'}
BOOT = Path('/proc/sys/kernel/random/boot_id')
ENV_KEYS = {'HOME', 'LANG', 'LC_ALL', 'LC_CTYPE', 'OMP_NUM_THREADS', 'PATH', 'TMPDIR', 'LD_LIBRARY_PATH'}
DEVICE_ENV = dict(NEOReadDebugKeys='1', FilterBdfPath='0000:23:00.0',
    ZE_ENABLE_PCI_ID_DEVICE_ORDER='1', ZE_AFFINITY_MASK='0', ONEAPI_DEVICE_SELECTOR='level_zero:0')


class ProvenanceRefusal(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise ProvenanceRefusal(reason)


def _bounded(path, limit):
    with Path(path).open('rb') as stream:
        data = stream.read(limit + 1)
    require(len(data) <= limit, 'bounded provenance input exceeded: ' + str(path))
    return data


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _preload():
    # Even an empty system preload file is outside this exact launch proof.
    require(not os.path.lexists('/etc/ld.so.preload'), 'system loader preload file present')


def _private_parent(owner):
    require(owner.is_absolute() and '..' not in owner.parts and
            owner.parent.resolve(strict=True) == owner.parent, 'real absolute owner parent required')
    info = owner.parent.stat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
            stat.S_IMODE(info.st_mode) == 0o700, 'private0700 owner parent required')
    return (info.st_dev, info.st_ino)


def _process_stat(raw, pid):
    # comm can contain spaces or parentheses; fields after its last ')' are fixed.
    left, separator, right = raw.rpartition(b') ')
    require(separator and left.startswith(str(pid).encode() + b' ('), 'process stat PID/grammar mismatch')
    fields = right.split()
    require(len(fields) >= 20, 'short process stat')
    return dict(pid=pid, ppid=int(fields[1]), start_ticks=int(fields[19]))


def _mapped_objects(raw):
    result = {}
    for line in raw.decode('utf-8', errors='strict').splitlines():
        fields = line.split(None, 5)
        require(len(fields) >= 5, 'malformed process map')
        if 'x' not in fields[1]:
            continue
        name = fields[5] if len(fields) == 6 else ''
        if name in ('[vdso]', '[vsyscall]'):
            continue
        require(name.startswith('/') and not name.endswith(' (deleted)'),
                'unresolved executable mapping')
        path = Path(name)
        require(path.resolve(strict=True) == path, 'noncanonical executable mapping')
        major, minor = (int(piece, 16) for piece in fields[3].split(':'))
        identity = (os.makedev(major, minor), int(fields[4]))
        require(identity[1] > 0 and result.get(path, identity) == identity,
                'inconsistent executable mapping identity')
        result[path] = identity
    require(0 < len(result) <= 128, 'executable mapping count outside proof budget')
    return result


def _exports(path, identity, *, max_bytes=32 * 1024**2):
    """Read bounded ELF64 dynamic-symbol metadata without running ELF tools."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and (before.st_dev, before.st_ino) == identity,
                'mapped object inode changed')
        bytes_read = 0
        def read_at(offset, size):
            nonlocal bytes_read
            require(0 <= offset <= before.st_size and 0 <= size <= 32 * 1024**2 and
                    offset + size <= before.st_size, 'ELF metadata bounds refused')
            require(bytes_read + size <= max_bytes, 'ELF metadata read budget exceeded')
            data = os.pread(fd, size, offset)
            bytes_read += len(data)
            require(len(data) == size, 'short ELF metadata read')
            return data
        header = read_at(0, 64)
        require(header[:7] == b'\x7fELF\x02\x01\x01' and struct.unpack_from('<H', header, 18)[0] == 62,
                'ELF64 little-endian x86_64 object required')
        phoffset = struct.unpack_from('<Q', header, 32)[0]
        phwidth, phcount = struct.unpack_from('<HH', header, 54)
        require(phwidth == 56 and 0 < phcount <= 4096, 'unsupported ELF program layout')
        programs = read_at(phoffset, phwidth * phcount)
        segments = [struct.unpack_from('<IIQQQQQQ', programs, i * phwidth) for i in range(phcount)]
        def address_offset(address, size):
            candidates = [r[2] + address - r[3] for r in segments
                if r[0] == 1 and r[3] <= address and address + size <= r[3] + r[5]]
            require(len(candidates) == 1, 'runtime metadata not in one file-backed PT_LOAD')
            return candidates[0]
        dynamic = [r for r in segments if r[0] == 2]
        require(len(dynamic) == 1 and 0 < dynamic[0][5] <= 1024**2 and dynamic[0][5] % 16 == 0,
                'one bounded PT_DYNAMIC required')
        dyn = dynamic[0]
        require(address_offset(dyn[3], dyn[5]) == dyn[2], 'PT_DYNAMIC address/offset mismatch')
        entries = read_at(dyn[2], dyn[5]); tags = {}; terminated = False
        for i in range(0, len(entries), 16):
            key, value = struct.unpack_from('<QQ', entries, i)
            if key == 0:
                terminated = True; break
            if key in (4, 5, 6, 10, 11, 0x6ffffef5):
                require(key not in tags, 'duplicate runtime symbol metadata')
                tags[key] = value
        require(terminated and {5, 6, 10, 11} <= set(tags) and tags[11] == 24 and
                (4 in tags or 0x6ffffef5 in tags), 'runtime symbol/hash metadata missing')
        offset = struct.unpack_from('<Q', header, 40)[0]
        width, count = struct.unpack_from('<HH', header, 58)
        require(width == 64 and 0 < count <= 4096, 'unsupported ELF section layout')
        sections = read_at(offset, width * count)
        rows = [struct.unpack_from('<IIQQQQIIQQ', sections, i * width) for i in range(count)]
        found = set(); metadata = hashlib.sha256(header + programs + entries + sections)
        require(sum(row[1] == 11 for row in rows) == 1, 'one runtime dynamic-symbol section required')
        total = 0
        for row in rows:
            if row[1] != 11:  # SHT_DYNSYM
                continue
            require(row[9] == 24 and row[5] % 24 == 0 and row[6] < count,
                    'unsupported ELF dynamic symbol layout')
            strings = rows[row[6]]
            require(strings[1] == 3, 'dynamic string table missing')
            require(row[3] == tags[6] and strings[3] == tags[5] and strings[5] == tags[10] and
                    address_offset(tags[6], row[5]) == row[4] and
                    address_offset(tags[5], strings[5]) == strings[4],
                    'section symbols differ from runtime dynamic tables')
            symbol_count = row[5] // 24
            if 4 in tags:
                hash_offset = address_offset(tags[4], 8)
                buckets, chains = struct.unpack('<II', read_at(hash_offset, 8))
                require(buckets > 0 and chains == symbol_count, 'SysV runtime symbol extent differs')
                hash_size = 8 + 4 * (buckets + chains)
                require(address_offset(tags[4], hash_size) == hash_offset, 'SysV hash extent outside PT_LOAD')
                hash_bytes = read_at(hash_offset, hash_size)
                require(all(index[0] < chains for index in struct.iter_unpack('<I', hash_bytes[8:])),
                        'SysV hash index beyond runtime symbol extent')
                metadata.update(hash_bytes)
            if 0x6ffffef5 in tags:
                hash_address = tags[0x6ffffef5]
                hash_offset = address_offset(hash_address, 16)
                buckets, first, bloom, shift = struct.unpack('<IIII', read_at(hash_offset, 16))
                require(0 < buckets <= symbol_count and 0 < bloom <= 2**20 and
                        0 < first <= symbol_count and shift < 64, 'GNU runtime hash dimensions refused')
                prefix_size = 16 + bloom * 8 + buckets * 4
                hash_size = prefix_size + (symbol_count - first) * 4
                require(address_offset(hash_address, hash_size) == hash_offset, 'GNU hash extent outside PT_LOAD')
                hash_bytes = read_at(hash_offset, hash_size); metadata.update(hash_bytes)
                # Every runtime-reachable bucket chain must terminate within the
                # section extent. Otherwise a shortened section hides exports.
                terminated_indices = set()
                for i in range(buckets):
                    index = struct.unpack_from('<I', hash_bytes, 16 + bloom * 8 + i * 4)[0]
                    if index == 0:
                        continue
                    require(first <= index < symbol_count, 'GNU hash bucket beyond symbol extent')
                    trail = []
                    while index not in terminated_indices:
                        require(index < symbol_count, 'GNU hash chain exceeds symbol extent')
                        trail.append(index)
                        value = struct.unpack_from('<I', hash_bytes, prefix_size + (index - first) * 4)[0]
                        if value & 1:
                            break
                        index += 1
                    terminated_indices.update(trail)
                require((max(terminated_indices) + 1 if terminated_indices else first) == symbol_count,
                        'GNU runtime symbol extent differs')
            total += row[5] + strings[5]
            require(total <= 32 * 1024**2, 'aggregate ELF metadata budget exceeded')
            table, names = read_at(row[4], row[5]), read_at(strings[4], strings[5])
            metadata.update(table); metadata.update(names)
            for i in range(0, len(table), 24):
                name, info, other, section, _, _ = struct.unpack_from('<IBBHQQ', table, i)
                if section == 0 or info >> 4 not in (1, 2, 10) or other & 3 not in (0, 3):
                    continue
                require(name < len(names), 'dynamic symbol name outside table')
                end = names.find(b'\0', name)
                require(end >= 0, 'unterminated dynamic symbol name')
                symbol = names[name:end]
                if symbol in SYMBOLS:
                    found.add(symbol)
        require(_signature(before) == _signature(os.fstat(fd)) == _signature(path.stat()),
                'mapped object changed during ELF read')
        return found, dict(path=str(path), identity=list(identity), metadata_sha256=metadata.hexdigest(),
                           metadata_bytes_read=bytes_read)
    finally:
        os.close(fd)


@dataclass(frozen=True)
class PreparedOrigin:
    owner_output: Path
    parent_identity: tuple
    environment: tuple
    boot_id: str
    prepared_monotonic: float

    def prove(self, process, *, admitted_argv, launch_monotonic):
        """After READY, prove this fresh launch's clock and output provenance.

        Exact loaded symbol providers rule out clock interposition in the observed
        namespace. Caller retains the sealed native code and exclusive launch
        contract (no injected code, debugger or concurrent output writer).
        """
        require(type(admitted_argv) is list and admitted_argv[:3] ==
                ['/usr/bin/ionice', '-c3', str(origin.BINARY)], 'unexpected owner command')
        require(admitted_argv.count('--output') == 1 and
                admitted_argv.index('--output') + 1 < len(admitted_argv) and
                admitted_argv[admitted_argv.index('--output') + 1] == str(self.owner_output),
                'owner output argument differs from prepared fresh path')
        require(process.args == admitted_argv and type(process.pid) is int and process.pid > 0 and
                process.poll() is None, 'fresh running owner handle required')
        require(self.prepared_monotonic <= launch_monotonic <= time.monotonic(), 'launch origin precedes preparation')
        require(BOOT.read_text().strip() == self.boot_id and
                _private_parent(self.owner_output) == self.parent_identity, 'boot/parent identity changed')
        _preload()
        proc = Path('/proc') / str(process.pid)
        before = _process_stat(_bounded(proc / 'stat', 8192), process.pid)
        require(before['ppid'] == os.getpid(), 'owner is not this coordinator child')
        require(os.readlink(proc / 'exe') == str(origin.BINARY), 'running native executable differs')
        expected_command = b'\0'.join(os.fsencode(arg) for arg in admitted_argv[2:]) + b'\0'
        require(_bounded(proc / 'cmdline', 65536) == expected_command, 'running owner argv differs')
        expected_environment = {os.fsencode(k) + b'=' + os.fsencode(v) for k, v in self.environment}
        raw_environment = _bounded(proc / 'environ', 65536).split(b'\0')
        require(raw_environment[-1:] == [b''] and len(raw_environment) - 1 == len(expected_environment) and
                set(raw_environment[:-1]) == expected_environment, 'running loader environment differs')
        maps = _bounded(proc / 'maps', 4 * 1024**2)
        objects = _mapped_objects(maps)
        require(origin.BINARY in objects and origin.CLOCK_LIBRARY in objects and LIBC in objects,
                'native binary/clock objects absent')
        providers = {symbol: set() for symbol in SYMBOLS}; records = []; total_bytes = 0
        for path, identity in sorted(objects.items()):
            symbols, row = _exports(path, identity, max_bytes=min(32 * 1024**2, 128 * 1024**2 - total_bytes))
            records.append(row); total_bytes += row['metadata_bytes_read']
            for symbol in symbols:
                providers[symbol].add(path)
        require(providers[b'_ZNSt6chrono3_V212steady_clock3nowEv'] == {origin.CLOCK_LIBRARY} and
                providers[b'clock_gettime'] == {LIBC}, 'clock symbol provider differs or is interposed')
        require(origin.sha(LIBC) == LIBC_SHA256, 'mapped libc identity drift')
        owner_info = self.owner_output.lstat()
        require(stat.S_ISDIR(owner_info.st_mode) and owner_info.st_uid == os.getuid(), 'fresh owner output missing')
        cold = origin.read_cold_start(self.owner_output,
            expected_owner_identity=(owner_info.st_dev, owner_info.st_ino))
        after = _process_stat(_bounded(proc / 'stat', 8192), process.pid)
        require(before == after and process.poll() is None and
                BOOT.read_text().strip() == self.boot_id and
                _private_parent(self.owner_output) == self.parent_identity and
                _mapped_objects(_bounded(proc / 'maps', 4 * 1024**2)) == objects,
                'owner identity or executable mappings changed during proof')
        adjusted = origin.derive_initial_idle_origin(launch_monotonic=launch_monotonic,
            observed_monotonic=time.monotonic(), cold_start_bytes=cold['raw'],
            cold_start_sha256=cold['sha256'], admitted_binary_sha256=origin.BINARY_SHA256,
            mapped_clock_library_path=origin.CLOCK_LIBRARY, mapped_clock_library_sha256=origin.CLOCK_SHA256)
        return dict(schema='ownrt.owner-idle-provenance.v1', passed=True,
            last_native_activity=adjusted['last_native_activity'], derivation=adjusted,
            fresh_owner_provenance_verified=True, process_mapping_verified=True,
            live_admission_ready=False, owner=before, boot_id=self.boot_id,
            parent_identity=list(self.parent_identity), owner_identity=list(cold['owner_identity']),
            cold_start_sha256=cold['sha256'], executable_maps_sha256=hashlib.sha256(maps).hexdigest(),
            mapped_objects=records, libc_sha256=LIBC_SHA256,
            trust_scope='Exclusive fresh private directory, sealed native launch, no hostile same-user mutation or code injection.')


def prepare_owner_origin(owner_output, environment):
    owner = Path(owner_output)
    parent = _private_parent(owner)
    require(not os.path.lexists(owner), 'owner output already exists; no historical adoption')
    require(type(environment) is dict and set(environment) <= ENV_KEYS | set(DEVICE_ENV) and
            {'PATH', 'OMP_NUM_THREADS', 'LD_LIBRARY_PATH'} <= set(environment) and
            environment['PATH'] == '/usr/bin:/bin' and environment['OMP_NUM_THREADS'] == '2' and
            all(type(k) is str and type(v) is str and '\0' not in k + v for k, v in environment.items()),
            'closed admitted loader environment required')
    present = set(environment) & set(DEVICE_ENV)
    require(not present or (present == set(DEVICE_ENV) and
            all(environment[key] == value for key, value in DEVICE_ENV.items())),
            'one-card native visibility environment differs')
    _preload()
    return PreparedOrigin(owner, parent, tuple(sorted(environment.items())), BOOT.read_text().strip(), time.monotonic())
