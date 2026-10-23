"""CPU-only ELF, filesystem and synthetic /proc checks; no owner is launched."""
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import owner_idle_provenance as proof


ENV = dict(PATH='/usr/bin:/bin', OMP_NUM_THREADS='2', LD_LIBRARY_PATH='/trusted/library')
COLD = (b'{"load_and_pin_ms":215480.035061,"initial_cache_fill_bytes":0,'
        b'"initial_cache_policy":"empty-content-independent","first_prompt_fills_charged_in_request":true}\n')


def stat_bytes(pid, *, ppid=None, start=1234):
    fields = ['S', str(os.getpid() if ppid is None else ppid)] + ['0'] * 17 + [str(start)]
    return str(pid).encode() + b' (a tricky ) name) ' + ' '.join(fields).encode()


def maps_bytes(paths):
    rows = []
    for i, path in enumerate(paths):
        info = path.stat()
        rows.append(f'{i+1:x}000-{i+2:x}000 r-xp 00000000 {os.major(info.st_dev):x}:{os.minor(info.st_dev):x} {info.st_ino} {path}')
    return ('\n'.join(rows) + '\n').encode()


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.parent = Path(tmp.name); self.parent.chmod(0o700)
        self.owner = self.parent / 'owner'
        self.argv = ['/usr/bin/ionice', '-c3', str(proof.origin.BINARY), '--output', str(self.owner)]
        self.child = SimpleNamespace(args=self.argv, pid=123456, poll=lambda: None)
        self.maps = maps_bytes([proof.origin.BINARY, proof.origin.CLOCK_LIBRARY, proof.LIBC])
        self.files = dict(stat=stat_bytes(self.child.pid), cmdline=b'\0'.join(os.fsencode(x) for x in self.argv[2:]) + b'\0',
                          environ=b'\0'.join(os.fsencode(k + '=' + v) for k, v in ENV.items()) + b'\0', maps=self.maps)

    def prepare(self, **env):
        return proof.prepare_owner_origin(self.owner, ENV | env)

    def run_proof(self, prepared=None, *, mutate=None):
        with patch.object(proof.time, 'monotonic', return_value=1000.0):
            prepared = prepared or self.prepare()
        self.owner.mkdir(exist_ok=True); (self.owner / 'cold-start.json').write_bytes(COLD)
        if mutate:
            mutate()
        readlink = os.readlink
        def link(path, *args, **kwargs):
            return str(proof.origin.BINARY) if str(path) == '/proc/123456/exe' else readlink(path, *args, **kwargs)
        with patch.object(proof, '_bounded', side_effect=lambda path, limit: self.files[Path(path).name]), \
             patch.object(proof.os, 'readlink', side_effect=link), \
             patch.object(proof.time, 'monotonic', return_value=1216.0):
            return prepared.prove(self.child, admitted_argv=self.argv, launch_monotonic=1000.0)

    def test_actual_elf_symbols_and_synthetic_owner_proof(self):
        row = self.run_proof()
        self.assertTrue(row['passed']); self.assertTrue(row['process_mapping_verified'])
        self.assertTrue(row['fresh_owner_provenance_verified']); self.assertFalse(row['live_admission_ready'])
        self.assertLess(row['last_native_activity'], 1215.0)
        self.assertEqual(row['derivation']['whole_seconds_added'], 215)
        self.assertFalse(row['derivation']['absolute_deadline_changed'])
        self.assertEqual(row['cold_start_sha256'], hashlib.sha256(COLD).hexdigest())

    def test_existing_output_and_nonprivate_parent_refused(self):
        self.owner.mkdir()
        with self.assertRaises(proof.ProvenanceRefusal): self.prepare()
        self.owner.rmdir(); self.parent.chmod(0o750)
        with self.assertRaises(proof.ProvenanceRefusal): self.prepare()

    def test_environment_injection_and_system_preload_refused(self):
        for key in ('LD_PRELOAD', 'LD_AUDIT', 'LD_DEBUG', 'PYTHONPATH'):
            with self.assertRaises(proof.ProvenanceRefusal): self.prepare(**{key: 'injected'})
        actual = os.path.lexists
        with patch.object(proof.os.path, 'lexists', side_effect=lambda p: str(p) == '/etc/ld.so.preload' or actual(p)):
            with self.assertRaises(proof.ProvenanceRefusal): self.prepare()

    def test_actual_retained_p199_environment_and_visibility_drift(self):
        path = proof.origin.HERE.parent / 'stage2/packet199-chat-parking/evidence/device-p199-chat-A-a/worker.json'
        environment = json.loads(path.read_text())['environment']
        prepared = proof.prepare_owner_origin(self.owner, environment)
        self.assertEqual(dict(prepared.environment), environment)
        for key in proof.DEVICE_ENV:
            changed = dict(environment); changed[key] = 'wrong'
            with self.assertRaises(proof.ProvenanceRefusal): proof.prepare_owner_origin(self.owner, changed)
            del changed[key]
            with self.assertRaises(proof.ProvenanceRefusal): proof.prepare_owner_origin(self.owner, changed)

    def test_different_output_argument_refused(self):
        self.argv[-1] = str(self.parent / 'another-owner')
        with self.assertRaisesRegex(proof.ProvenanceRefusal, 'output argument'): self.run_proof()

    def test_running_command_environment_parent_and_exit_refused(self):
        for key, value in (('cmdline', b'wrong\0'), ('environ', b'LD_PRELOAD=bad\0'),
                           ('stat', stat_bytes(self.child.pid, ppid=1))):
            with self.subTest(key=key):
                saved = self.files[key]; self.files[key] = value
                with self.assertRaises(proof.ProvenanceRefusal): self.run_proof()
                self.files[key] = saved
                for p in self.owner.iterdir(): p.unlink()
                self.owner.rmdir()
        self.child.poll = lambda: 0
        with self.assertRaises(proof.ProvenanceRefusal): self.run_proof()

    def test_interposed_clock_symbol_refused(self):
        actual = proof._exports
        def exports(path, identity, **kwargs):
            symbols, row = actual(path, identity, **kwargs)
            if path == proof.origin.BINARY:
                symbols.add(b'clock_gettime')
            return symbols, row
        with patch.object(proof, '_exports', side_effect=exports):
            with self.assertRaisesRegex(proof.ProvenanceRefusal, 'interposed'): self.run_proof()

    def test_executable_map_changes_and_unknown_code_refused(self):
        self.files['maps'] += b'9000-a000 rwxp 0 00:00 0\n'
        with self.assertRaisesRegex(proof.ProvenanceRefusal, 'unresolved'): self.run_proof()

    def test_parent_replacement_and_symlink_cold_file_refused(self):
        def replace_cold():
            target = self.owner / 'target'; (self.owner / 'cold-start.json').rename(target)
            (self.owner / 'cold-start.json').symlink_to(target)
        with self.assertRaises((OSError, proof.ProvenanceRefusal, proof.origin.IdleOriginRefusal)):
            self.run_proof(mutate=replace_cold)

    def test_process_reuse_during_proof_refused(self):
        original = proof._process_stat; calls = 0
        def changing(raw, pid):
            nonlocal calls
            row = original(raw, pid); calls += 1
            if calls > 1: row['start_ticks'] += 1
            return row
        with patch.object(proof, '_process_stat', side_effect=changing):
            with self.assertRaisesRegex(proof.ProvenanceRefusal, 'identity'): self.run_proof()


class MetadataTests(unittest.TestCase):
    def test_actual_pinned_clock_providers(self):
        for path, symbol in ((proof.origin.CLOCK_LIBRARY, b'_ZNSt6chrono3_V212steady_clock3nowEv'),
                             (proof.LIBC, b'clock_gettime')):
            info = path.stat(); symbols, row = proof._exports(path, (info.st_dev, info.st_ino))
            self.assertIn(symbol, symbols); self.assertEqual(row['path'], str(path))

    def test_changed_inode_and_malformed_elf_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.so'; path.write_bytes(b'not an ELF' * 16)
            info = path.stat()
            with self.assertRaises(proof.ProvenanceRefusal): proof._exports(path, (info.st_dev, info.st_ino))
            with self.assertRaises(proof.ProvenanceRefusal): proof._exports(path, (info.st_dev, info.st_ino + 1))

    def test_runtime_tables_and_hash_extent_must_match_sections(self):
        original = proof.origin.CLOCK_LIBRARY.read_bytes()
        section_offset = struct.unpack_from('<Q', original, 40)[0]
        section_count = struct.unpack_from('<H', original, 60)[0]
        sym = next(section_offset + i * 64 for i in range(section_count)
                   if struct.unpack_from('<I', original, section_offset + i * 64 + 4)[0] == 11)
        cases = [('missing-dynsym', sym + 4, '<I', 1),
                 ('different-address', sym + 16, '<Q', struct.unpack_from('<Q', original, sym + 16)[0] + 8),
                 ('shortened-symbol-extent', sym + 32, '<Q', 24)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'altered.so'
            for name, offset, format_, value in cases:
                with self.subTest(name=name):
                    changed = bytearray(original); struct.pack_into(format_, changed, offset, value)
                    path.write_bytes(changed); info = path.stat()
                    with self.assertRaises(proof.ProvenanceRefusal): proof._exports(path, (info.st_dev, info.st_ino))

    def test_sysv_hash_index_outside_runtime_extent_refused(self):
        raw = bytearray(proof.LIBC.read_bytes())
        offset = struct.unpack_from('<Q', raw, 32)[0]
        count = struct.unpack_from('<H', raw, 56)[0]
        segments = [struct.unpack_from('<IIQQQQQQ', raw, offset + i * 56) for i in range(count)]
        dynamic = next(row for row in segments if row[0] == 2)
        tags = dict(struct.iter_unpack('<QQ', raw[dynamic[2]:dynamic[2] + dynamic[5]]))
        address = tags[4]
        load = next(row for row in segments if row[0] == 1 and row[3] <= address < row[3] + row[5])
        hash_offset = load[2] + address - load[3]
        chains = struct.unpack_from('<I', raw, hash_offset + 4)[0]
        struct.pack_into('<I', raw, hash_offset + 8, chains)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad-hash.so'; path.write_bytes(raw); info = path.stat()
            with self.assertRaisesRegex(proof.ProvenanceRefusal, 'SysV hash index'):
                proof._exports(path, (info.st_dev, info.st_ino))

    def test_map_parser_rejects_deleted_and_accepts_kernel_vdso(self):
        raw = maps_bytes([proof.LIBC]) + b'a000-b000 r-xp 0 00:00 0 [vdso]\n'
        self.assertEqual(set(proof._mapped_objects(raw)), {proof.LIBC})
        with self.assertRaises(proof.ProvenanceRefusal): proof._mapped_objects(raw.replace(b'libc.so.6', b'libc.so.6 (deleted)'))

    def test_bounded_reader_and_tricky_process_stat(self):
        self.assertEqual(proof._process_stat(stat_bytes(123), 123)['start_ticks'], 1234)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'small'; path.write_bytes(b'12345')
            with self.assertRaises(proof.ProvenanceRefusal): proof._bounded(path, 4)
            self.assertEqual(proof._bounded(path, 5), b'12345')


if __name__ == '__main__':
    unittest.main()
