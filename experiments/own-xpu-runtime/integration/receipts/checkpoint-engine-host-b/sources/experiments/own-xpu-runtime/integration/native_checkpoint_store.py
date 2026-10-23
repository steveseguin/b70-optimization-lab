"""Bounded local checkpoint metadata/maintenance through a pinned native tool.

The caller admits the fixed real root, binary digest and closed loader environment.
Only checkpoint IDs cross the operation API. This module never starts a model,
changes checkpoint identity/labels, implements serialization, or recursively deletes.
Native restore must still validate all state before upload; these are metadata snapshots.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import errno
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
from types import MappingProxyType
from typing import Mapping


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
MAX_MANIFEST = 4 * 1024**2
MAX_TOKENS = 32768
MAX_STDOUT = MAX_MANIFEST + 65536
MAX_STDERR = 131072
MAX_BINARY = 256 * 1024**2
MAX_FILES = 4096


class StoreRefusal(RuntimeError):
    """No operation may treat this failure as a cache hit or retry permission."""


class CheckpointInUse(StoreRefusal):
    """The native-compatible lock is held exclusively; no waiting was attempted."""


def _require(condition, message):
    if not condition:
        raise StoreRefusal(message)


def _valid_id(value):
    _require(type(value) is str and _ID.fullmatch(value) is not None and not value.endswith('.lock'),
             'invalid checkpoint id')


def _json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value): raise StoreRefusal('non-finite JSON value: ' + value)
    try:
        result = json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise StoreRefusal('malformed native metadata JSON') from error
    _require(type(result) is dict, 'native JSON object required')
    return result


def _sha(data): return hashlib.sha256(data).hexdigest()


def _same(a, b): return (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)


def _stable(a, b):
    return _same(a, b) and (a.st_size, a.st_mtime_ns, a.st_ctime_ns) == (b.st_size, b.st_mtime_ns, b.st_ctime_ns)


@dataclass(frozen=True)
class CheckpointSnapshot:
    checkpoint_id: str
    inspect_stdout: bytes
    inspect_returncode: int
    inspect_stderr: bytes
    manifest_bytes: bytes
    tokens_bytes: bytes
    next_token_bytes: bytes
    storage_bytes: int

    def bridge_arguments(self):
        """Caller must separately inject trusted expected_identity/admitted_contract."""
        return {key: getattr(self, key) for key in ('checkpoint_id', 'inspect_stdout', 'inspect_returncode',
                                                   'manifest_bytes', 'tokens_bytes', 'next_token_bytes')}


class NativeCheckpointStore:
    def __init__(self, root: Path, binary: Path, binary_sha256: str, environment: Mapping[str, str],
                 *, timeout_seconds=15, runner=subprocess.run):
        self._root_fd = self._binary_fd = None
        self.root, self.binary = Path(root), Path(binary)
        self.binary_sha256 = binary_sha256
        self.timeout_seconds, self._runner = timeout_seconds, runner
        self.last_result = None
        _require(type(binary_sha256) is str and _SHA.fullmatch(binary_sha256) is not None, 'admitted binary SHA256 required')
        _require(type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds) and 0 < timeout_seconds <= 60,
                 'tool timeout must be bounded to 0..60 seconds')
        env = dict(environment)
        _require(set(env) == {'PATH', 'OMP_NUM_THREADS', 'LD_LIBRARY_PATH'}, 'closed three-key loader environment required')
        _require(all(type(value) is str and '\x00' not in value and '\n' not in value for value in env.values()),
                 'invalid environment value')
        _require(env['PATH'] == '/usr/bin:/bin' and env['OMP_NUM_THREADS'] == '2', 'fixed tool PATH and two threads required')
        _require(env['LD_LIBRARY_PATH'] and all(Path(part).is_absolute() for part in env['LD_LIBRARY_PATH'].split(':')),
                 'explicit absolute loader paths required; no empty/current-directory component')
        self.environment = MappingProxyType(env)
        try:
            self._real_path(self.root)
            self._real_path(self.binary)
            self._root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
            before = os.stat(self.binary, follow_symlinks=False)
            _require(stat.S_ISREG(before.st_mode), 'binary must be a regular file')
            self._binary_fd = os.open(self.binary, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
            _require(_same(before, os.fstat(self._binary_fd)), 'binary changed during open')
            self._root_identity = os.fstat(self._root_fd)
            self._check_binary()
        except (OSError, ValueError) as error:
            self.close()
            raise StoreRefusal('fixed root/binary admission failed: ' + str(error)) from error
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _real_path(path):
        _require(path.is_absolute() and path.resolve(strict=True) == path, 'fixed path must be real, absolute and contain no symlink or traversal')

    def close(self):
        for name in ('_root_fd', '_binary_fd'):
            fd = getattr(self, name, None)
            if fd is not None:
                os.close(fd)
                setattr(self, name, None)

    def __enter__(self): return self

    def __exit__(self, *ignored): self.close()

    def __del__(self):
        try: self.close()
        except OSError: pass

    def _check_root(self):
        _require(self._root_fd is not None and self._binary_fd is not None, 'checkpoint store is closed')
        self._real_path(self.root)
        live = os.stat(self.root, follow_symlinks=False)
        _require(stat.S_ISDIR(live.st_mode) and _same(live, self._root_identity), 'fixed checkpoint root replaced')

    def _check_binary(self):
        self._check_root()
        self._real_path(self.binary)
        before = os.fstat(self._binary_fd)
        _require(stat.S_ISREG(before.st_mode) and bool(before.st_mode & 0o111) and 4 <= before.st_size <= MAX_BINARY,
                 'bounded regular executable required')
        _require(_same(before, os.stat(self.binary, follow_symlinks=False)), 'admitted binary path replaced')
        digest = hashlib.sha256()
        for offset in range(0, before.st_size, 1024**2):
            data = os.pread(self._binary_fd, min(1024**2, before.st_size-offset), offset)
            _require(data, 'binary truncated during verification')
            if offset == 0: _require(data[:4] == b'\x7fELF', 'admitted native ELF required')
            digest.update(data)
        _require(_stable(before, os.fstat(self._binary_fd)) and digest.hexdigest() == self.binary_sha256,
                 'admitted binary digest changed')

    def _lstat(self, name):
        try: return os.stat(name, dir_fd=self._root_fd, follow_symlinks=False)
        except FileNotFoundError: return None

    def _directory(self, checkpoint_id):
        before = self._lstat(checkpoint_id)
        if before is None: return None
        _require(stat.S_ISDIR(before.st_mode), 'checkpoint target is not a real directory')
        fd = os.open(checkpoint_id, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=self._root_fd)
        try:
            _require(_same(before, os.fstat(fd)), 'checkpoint directory changed during open')
            return fd
        except BaseException:
            os.close(fd); raise

    def _check_directory(self, checkpoint_id, fd):
        self._check_root()
        current = self._lstat(checkpoint_id)
        _require(current is not None and stat.S_ISDIR(current.st_mode) and _same(current, os.fstat(fd)),
                 'checkpoint directory replaced during operation')

    @contextmanager
    def _shared_lock(self, checkpoint_id):
        """Same sibling inode/dev retry rule as native CheckpointLock; never wait."""
        name = checkpoint_id + '.lock'
        for _ in range(3):
            before = self._lstat(name)
            _require(before is None or stat.S_ISREG(before.st_mode), 'checkpoint lock is not a regular file')
            fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
                         0o644, dir_fd=self._root_fd)
            held = False
            try:
                _require(stat.S_ISREG(os.fstat(fd).st_mode), 'checkpoint lock is not a regular file')
                try: fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except OSError as error:
                    if error.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                        raise CheckpointInUse('checkpoint is being saved or deleted') from error
                    raise
                current = self._lstat(name)
                held = current is not None and stat.S_ISREG(current.st_mode) and _same(os.fstat(fd), current)
                if held:
                    yield
                    return
            finally:
                os.close(fd)
        raise StoreRefusal('checkpoint lock replaced during three bounded attempts')

    @staticmethod
    def _read_small(directory_fd, name, maximum, *, exact=None):
        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        _require(stat.S_ISREG(before.st_mode) and 0 <= before.st_size <= maximum, 'nonregular or oversized metadata file: ' + name)
        fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        try:
            opened = os.fstat(fd)
            _require(stat.S_ISREG(opened.st_mode) and _same(before, opened), 'metadata file changed during open: ' + name)
            _require(exact is None or opened.st_size == exact, 'metadata extent mismatch: ' + name)
            data = bytearray()
            while len(data) <= maximum:
                part = os.read(fd, min(65536, maximum + 1 - len(data)))
                if not part: break
                data.extend(part)
            _require(len(data) == opened.st_size and len(data) <= maximum and _stable(opened, os.fstat(fd)),
                     'metadata file changed or exceeded bound: ' + name)
            return bytes(data)
        finally:
            os.close(fd)

    def _preflight_metadata(self, directory_fd):
        # Native metadata mode also reads fields.tsv. Bound both before running
        # its pinned parser; neither mode is permitted to read a huge file.
        manifest = self._read_small(directory_fd, 'manifest.json', MAX_MANIFEST)
        self._read_small(directory_fd, 'fields.tsv', MAX_MANIFEST)
        return manifest

    @staticmethod
    def _inventory(directory_fd, manifest):
        blobs = manifest.get('blobs')
        _require(type(blobs) is list and len(blobs) + 3 <= MAX_FILES, 'bounded native blob inventory required')
        expected = {'manifest.json': None, 'fields.tsv': None, 'tokens.bin': None}
        for blob in blobs:
            _require(type(blob) is dict, 'invalid native blob metadata')
            name = blob.get('name')
            _valid_id(name)
            _require(name not in ('manifest', 'fields', 'tokens') and name + '.bin' not in expected,
                     'duplicate/reserved native blob name')
            extent = blob.get('bytes')
            _require(type(extent) is int and extent >= 0, 'invalid native blob extent')
            expected[name + '.bin'] = extent
        result = {}
        with os.scandir(directory_fd) as entries:
            for entry in entries:
                _require(len(result) < MAX_FILES and entry.name in expected, 'unclosed checkpoint inventory')
                info = entry.stat(follow_symlinks=False)
                _require(stat.S_ISREG(info.st_mode) and info.st_size >= 0, 'nonregular checkpoint inventory entry')
                _require(expected[entry.name] is None or info.st_size == expected[entry.name],
                         'checkpoint blob extent differs from manifest: ' + entry.name)
                result[entry.name] = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        _require(set(result) == set(expected), 'checkpoint inventory has missing files')
        return result

    def _run(self, operation, checkpoint_id):
        _require(operation in ('--checkpoint-inspect-metadata', '--checkpoint-delete'), 'unsupported native tool operation')
        self._check_binary()
        argv = [str(self.binary), operation, str(self.root / checkpoint_id)]
        self.last_result = None
        try:
            # Execute the verified open ELF inode, retaining the admitted pathname
            # in argv[0]; a later pathname replacement cannot substitute an ELF.
            result = self._runner(argv, executable='/proc/self/fd/' + str(self._binary_fd),
                                  pass_fds=(self._binary_fd,), close_fds=True,
                                  env=dict(self.environment), stdin=subprocess.DEVNULL,
                                  capture_output=True, timeout=self.timeout_seconds)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise StoreRefusal('bounded native metadata tool failed: ' + str(error)) from error
        self.last_result = result
        _require(type(result.returncode) is int and type(result.stdout) is bytes and type(result.stderr) is bytes,
                 'native tool result types')
        _require(len(result.stdout) <= MAX_STDOUT and len(result.stderr) <= MAX_STDERR, 'native tool output exceeds bound')
        self._check_root()
        row = _json(result.stdout)
        _require(row.get('checkpoint_id') == checkpoint_id and row.get('checkpoint_dir') == str(self.root / checkpoint_id),
                 'native result checkpoint identity differs')
        return result, row

    def snapshot(self, checkpoint_id: str) -> CheckpointSnapshot | None:
        _valid_id(checkpoint_id)
        directory = None
        try:
            self._check_binary()
            directory = self._directory(checkpoint_id)
            if directory is None: return None
            with self._shared_lock(checkpoint_id):
                self._check_directory(checkpoint_id, directory)
                initial_manifest = _json(self._preflight_metadata(directory))
                initial_inventory = self._inventory(directory, initial_manifest)
                result, row = self._run('--checkpoint-inspect-metadata', checkpoint_id)
                _require(result.returncode == 0 and row.get('schema') == 'ownrt.checkpoint-inspect.v1'
                         and row.get('ok') is True and row.get('error') is None
                         and row.get('device_required') is False and row.get('mode') == 'metadata', 'native metadata inspection refused')
                verified = row.get('verified', {})
                _require(type(verified) is dict and all(verified.get(key) is True for key in
                         ('manifest_seal', 'fields_tsv_cross_check', 'file_set_closed')), 'native metadata seal checks missing')
                _require(all(key in verified and verified[key] is None for key in
                         ('tokens', 'semantic_blob_checks', 'blobs_verified', 'blob_bytes_verified')),
                         'metadata inspect must not claim full state verification')
                manifest_bytes = self._read_small(directory, 'manifest.json', MAX_MANIFEST)
                manifest = _json(manifest_bytes)
                _require(row.get('manifest_sha256') == _sha(manifest_bytes), 'inspected manifest digest differs')
                _require(json.dumps(row.get('manifest'), sort_keys=True, separators=(',', ':')) ==
                         json.dumps(manifest, sort_keys=True, separators=(',', ':')), 'inspect/raw manifest differ')
                _require(manifest.get('checkpoint_id') == checkpoint_id and manifest.get('format') == 'ownrt.session-checkpoint.v1',
                         'native manifest identity differs')
                for key in ('label', 'contract'):
                    _require(type(manifest.get(key)) is str and row.get(key) == manifest[key], 'native ' + key + ' differs')
                state = manifest['token_state']; count = state['length']
                _require(type(count) is int and 1 <= count <= MAX_TOKENS, 'bounded token state required')
                tokens = self._read_small(directory, 'tokens.bin', 4 * MAX_TOKENS, exact=4 * count)
                pending = self._read_small(directory, 'next_token.bin', 4, exact=4)
                _require(_sha(tokens) == state['tokens_sha256'], 'tokens.bin digest differs')
                _require(type(manifest.get('blobs')) is list and all(type(blob) is dict for blob in manifest['blobs']),
                         'invalid native blob inventory')
                blobs = [blob for blob in manifest['blobs'] if blob.get('name') == 'next_token']
                _require(len(blobs) == 1 and type(blobs[0].get('bytes')) is int and blobs[0]['bytes'] == 4
                         and blobs[0].get('sha256') == _sha(pending), 'next_token.bin digest differs')
                self._check_directory(checkpoint_id, directory)
                final_inventory = self._inventory(directory, manifest)
                _require(initial_inventory == final_inventory, 'checkpoint files changed during snapshot')
                storage_bytes = sum(info[2] for info in final_inventory.values())
                return CheckpointSnapshot(checkpoint_id, result.stdout, result.returncode, result.stderr,
                                          manifest_bytes, tokens, pending, storage_bytes)
        except (OSError, KeyError, TypeError, ValueError, RecursionError) as error:
            raise StoreRefusal('checkpoint snapshot refused: ' + str(error)) from error
        finally:
            if directory is not None: os.close(directory)

    def delete(self, checkpoint_id: str) -> str:
        _valid_id(checkpoint_id)
        directory = None
        try:
            self._check_binary()
            directory = self._directory(checkpoint_id)
            if directory is None: return 'missing'
            self._preflight_metadata(directory)
            self._check_directory(checkpoint_id, directory)
            # No outer shared lock here: the native delete needs its own
            # exclusive nonblocking lock. It validates the exact closed file set.
            result, row = self._run('--checkpoint-delete', checkpoint_id)
            _require(row.get('schema') == 'ownrt.checkpoint-delete.v1' and type(row.get('files_removed')) is int
                     and row['files_removed'] >= 0, 'native delete result schema')
            if result.returncode == 0:
                _require(row.get('ok') is True and row.get('deleted') is True and row.get('reason') is None
                         and row.get('error') is None and row['files_removed'] > 0, 'native delete success proof missing')
                _require(self._lstat(checkpoint_id) is None, 'checkpoint still exists or was replaced after native delete')
                return 'ok'
            _require(result.returncode == 1 and row.get('ok') is False and row.get('deleted') is False
                     and row['files_removed'] == 0 and type(row.get('error')) is dict, 'native delete failure')
            if row.get('reason') == 'in_use' and row['error'].get('check') == 'lock': return 'in_use'
            if row.get('reason') == 'not_a_checkpoint' and row['error'].get('check') == 'visibility' and self._lstat(checkpoint_id) is None:
                return 'missing'
            raise StoreRefusal('native delete refused: ' + str(row.get('reason')))
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise StoreRefusal('checkpoint deletion refused: ' + str(error)) from error
        finally:
            if directory is not None: os.close(directory)
