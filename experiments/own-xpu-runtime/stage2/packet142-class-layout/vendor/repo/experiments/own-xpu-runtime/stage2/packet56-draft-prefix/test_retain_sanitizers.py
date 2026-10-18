"""Temporary CPU fixtures only: no real packet binaries are opened or removed."""
import gzip
import hashlib
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import retain_sanitizers as r


def digest(value):
    return hashlib.sha256(value).hexdigest()


class RetainSanitizersTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='p49c-sanitizer-retention-test-')
        self.addCleanup(self.tmp.cleanup)
        self.packet = Path(self.tmp.name)/'packet'
        self.build = self.packet/'build'
        (self.build/'asan').mkdir(parents=True)
        self.payloads = {'asan/model': b'\x7fELF\x00same exact sanitizer bytes\xff'*2048,
                         'asan/libbridge.so': bytes(range(256))*37}
        self.permissions = {'asan/model':0o751, 'asan/libbridge.so':0o640}
        for name, data in self.payloads.items():
            path=self.build/name
            path.write_bytes(data)
            path.chmod(self.permissions[name])
        self.build_receipt = self.packet/'build-asan-receipt.json'
        self.build_receipt.write_text(json.dumps(dict(passed=True, device_executed=False, mode='asan',
            artifacts_sha256={name:digest(data) for name,data in self.payloads.items()})))
        for name, value in [('P',self.packet), ('B',self.build)]:
            context=patch.object(r,name,value);context.start();self.addCleanup(context.stop)
        context=patch.object(r.storage,'cpu_build_admit');self.admit=context.start();self.addCleanup(context.stop)
        self.consumer=SimpleNamespace(SANITIZER_ARCHIVE_RETENTION=r.SCHEMA)
        context=patch.object(r.importlib,'import_module',return_value=self.consumer)
        self.importer=context.start();self.addCleanup(context.stop)

    def receipt(self):
        return json.loads((self.packet/r.RECEIPT_NAME).read_text())

    def save_receipt(self, row):
        (self.packet/r.RECEIPT_NAME).write_text(json.dumps(row))

    def test_exact_roundtrip_permissions_archives_and_idempotence(self):
        first=r.retain()
        self.assertEqual(first['original_bytes'],sum(map(len,self.payloads.values())))
        self.assertEqual(set(row['original'] for row in first['artifacts']),set(self.payloads))
        for row in first['artifacts']:
            self.assertFalse((self.build/row['original']).exists())
            archive=self.build/row['archive']
            self.assertEqual(gzip.decompress(archive.read_bytes()),self.payloads[row['original']])
        self.assertEqual(first,r.retain())
        before={row['archive']:digest((self.build/row['archive']).read_bytes()) for row in first['artifacts']}
        restored=r.restore()
        self.assertEqual(restored,first)
        for name,data in self.payloads.items():
            path=self.build/name
            self.assertEqual(path.read_bytes(),data)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),self.permissions[name])
        self.assertEqual(r.restore(),first)
        self.assertEqual(before,{name:digest((self.build/name).read_bytes()) for name in before})
        r.retain()
        self.assertEqual(first,r.verify_retention())

    def test_consumer_must_exist_before_first_deletion(self):
        self.consumer.SANITIZER_ARCHIVE_RETENTION=None
        with self.assertRaisesRegex(ValueError,'consumer'):
            r.retain()
        for name,data in self.payloads.items():
            self.assertEqual((self.build/name).read_bytes(),data)
        self.assertTrue((self.packet/r.RECEIPT_NAME).is_file())
        self.consumer.SANITIZER_ARCHIVE_RETENTION=r.SCHEMA
        r.retain()
        self.assertTrue(all(not (self.build/name).exists() for name in self.payloads))

    def test_every_write_is_admitted_and_restore_refuses_budget(self):
        r.retain()
        self.assertEqual(self.admit.call_count,len(self.payloads)+1)
        self.assertTrue(all(call.args[0]>0 for call in self.admit.call_args_list))
        self.admit.reset_mock()
        self.admit.side_effect=RuntimeError('storage admission refused')
        with self.assertRaisesRegex(RuntimeError,'storage admission'):
            r.restore()
        self.assertTrue(all(not (self.build/name).exists() for name in self.payloads))
        self.assertTrue(all((self.build/row['archive']).exists() for row in self.receipt()['artifacts']))

    def test_compression_budget_refusal_preserves_originals(self):
        self.admit.side_effect=RuntimeError('budget refused')
        with self.assertRaisesRegex(RuntimeError,'budget refused'):
            r.retain()
        self.assertFalse((self.packet/r.RECEIPT_NAME).exists())
        for name,data in self.payloads.items():
            self.assertEqual((self.build/name).read_bytes(),data)

    def test_changed_original_is_never_archived_or_removed(self):
        name='asan/model'
        (self.build/name).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):
            r.retain()
        self.assertEqual((self.build/name).read_bytes(),b'changed')
        self.assertFalse((self.packet/r.RECEIPT_NAME).exists())

    def test_source_mutation_during_compression_refuses(self):
        first='asan/libbridge.so'
        changed=b'Z'*len(self.payloads[first])
        def mutate(_):
            (self.build/first).write_bytes(changed)
        self.admit.side_effect=mutate
        with self.assertRaisesRegex(ValueError,'mutated'):
            r.retain()
        self.assertEqual((self.build/first).read_bytes(),changed)
        self.assertFalse((self.packet/r.RECEIPT_NAME).exists())
        self.assertFalse(list(self.build.rglob('*.partial-*')))

    def test_source_build_receipt_mutation_breaks_binding(self):
        r.retain()
        row=json.loads(self.build_receipt.read_text());row['changed']=True
        self.build_receipt.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError,'binding'):
            r.verify_retention()

    def test_archive_hash_or_stream_corruption_refuses_restore(self):
        r.retain()
        receipt=self.receipt();row=receipt['artifacts'][0];path=self.build/row['archive']
        corrupt=bytearray(path.read_bytes());corrupt[-5]^=1;path.write_bytes(corrupt)
        with self.assertRaisesRegex(ValueError,'archive identity'):
            r.restore()
        row['archive_sha256']=digest(bytes(corrupt));self.save_receipt(receipt)
        with self.assertRaises((ValueError,OSError,EOFError)):
            r.restore()
        self.assertTrue(all(not (self.build/name).exists() for name in self.payloads))

    def test_archive_extent_lie_is_rejected(self):
        r.retain()
        receipt=self.receipt();receipt['artifacts'][0]['bytes']-=1;receipt['original_bytes']-=1
        self.save_receipt(receipt)
        with self.assertRaisesRegex(ValueError,'extent'):
            r.restore()

    def test_restore_does_not_overwrite_different_bytes(self):
        r.retain();name='asan/model';path=self.build/name
        path.write_bytes(b'other version');path.chmod(self.permissions[name])
        with self.assertRaises(ValueError):
            r.restore()
        self.assertEqual(path.read_bytes(),b'other version')

    def test_restore_does_not_overwrite_changed_permissions(self):
        r.retain();r.restore();path=self.build/'asan/model';path.chmod(0o600)
        with self.assertRaisesRegex(ValueError,'permissions'):
            r.restore()
        self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)

    def test_traversal_other_mode_and_symlinks_refuse(self):
        for name in ('../outside','/tmp/outside','device/model','asan/../device/model','asan//model','asan/model/sub'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                r._path(name)
        name='asan/model';path=self.build/name;outside=Path(self.tmp.name)/'protected'
        outside.write_bytes(self.payloads[name]);path.unlink();path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError,'symlink|regular'):
            r.retain()
        self.assertEqual(outside.read_bytes(),self.payloads[name])

    def test_archive_directory_symlink_refuses(self):
        outside=Path(self.tmp.name)/'outside';outside.mkdir()
        (self.build/'asan/retained').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):
            r.retain()
        self.assertEqual(list(outside.iterdir()),[])
        self.assertTrue(all((self.build/name).is_file() for name in self.payloads))

    def test_inventory_omission_and_duplicate_refuse(self):
        r.retain();original=self.receipt()
        omitted=dict(original,artifacts=original['artifacts'][:-1]);self.save_receipt(omitted)
        with self.assertRaisesRegex(ValueError,'inventory'):
            r.verify_retention()
        duplicate=dict(original,artifacts=[original['artifacts'][0]]*2);self.save_receipt(duplicate)
        with self.assertRaisesRegex(ValueError,'identity'):
            r.verify_retention()

    def test_original_mutation_after_receipt_preserves_all_survivors(self):
        writer=r._write_receipt
        def mutate_after(receipt):
            writer(receipt)
            (self.build/'asan/model').write_bytes(b'changed after compression')
        with patch.object(r,'_write_receipt',side_effect=mutate_after):
            with self.assertRaises(ValueError):
                r.retain()
        self.assertTrue(all((self.build/name).exists() for name in self.payloads))

if __name__=='__main__':
    unittest.main()
