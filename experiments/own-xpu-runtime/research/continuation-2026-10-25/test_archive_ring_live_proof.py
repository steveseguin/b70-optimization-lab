"""CPU-only tiny sealed bundles exercise reuse, fallback, and independent restore."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

import archive_ring_live_proof as archive
import restore_ring_live_archive as reader
sys.path.insert(0,str(archive.OWNRT/'engine/tools'))
from test_compare_draft_state import fixture,seal


def sha(raw):return hashlib.sha256(raw).hexdigest()
def pack(path,files):
    with tarfile.open(path,'x:gz') as out:
        for name,data in files.items():
            info=tarfile.TarInfo(name);info.size=len(data);out.addfile(info,io.BytesIO(data))


def setup(root):
    manifest,buffers,state=fixture(root/'source-state');dump=manifest.parent/'dump'
    base={name:(dump/name).read_bytes() for name in (*reader.META,'state.bundle')}
    source=root/'source.tgz';pack(source,{'old/'+name:raw for name,raw in base.items()})
    source_id=archive.archive_identity(source);source_id.update(durable=True,copied_content_independently_rehashed=True)
    source_receipt=root/'source-receipt.json';source_receipt.write_text(json.dumps(source_id))
    changed=dict(buffers);changed['card0:draft:scratch']=bytes([1])+changed['card0:draft:scratch'][1:]
    seal(dump,changed,state);new={name:(dump/name).read_bytes() for name in (*reader.META,'state.bundle')}
    files={};rows=[]
    for label,data in [('same-a',base),('same-b',base),('different',new)]:
        prefix='run/'+label
        files.update({prefix+'/'+name:raw for name,raw in data.items()})
        rows.append(dict(original_path='/original/'+label+'/state.bundle',archive_path=prefix+'/state.bundle',
            bytes=len(data['state.bundle']),sha256=sha(data['state.bundle']),qualified=True,
            metadata_sha256={n:sha(data[n]) for n in reader.META}))
    complete=root/'complete.tgz';pack(complete,files)
    receipt=root/'complete.json';receipt.write_text(json.dumps(dict(schema='ownrt.ring-live-full-archive.v1',passed=True,
        archive=archive.archive_identity(complete),bundles=rows,member_inventory=archive.inventory(complete))))
    return receipt,source_receipt,files,rows


class ArchiveLiveTests(unittest.TestCase):
    def test_mixed_reuse_and_new_bytes_are_restored_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);full,source,files,rows=setup(root)
            result=archive.reuse(full,source,root/'mixed.tgz',root/'receipt.json',root/'out')
            self.assertEqual((result['restoration_check']['reused'],result['restoration_check']['embedded']),(2,1))
            self.assertTrue(all(r['native_sealed_reader_passed'] for r in result['restored_sealed_bundles']))
            self.assertTrue((root/'complete.tgz').is_file())
            a,b=root/'out/run/same-a/state.bundle',root/'out/run/same-b/state.bundle'
            self.assertEqual(a.read_bytes(),b.read_bytes());self.assertNotEqual(a.stat().st_ino,b.stat().st_ino)
            self.assertEqual(a.stat().st_nlink,1);self.assertEqual(b.stat().st_nlink,1)
            a.write_bytes(b'changed');self.assertNotEqual(a.read_bytes(),b.read_bytes())
            with self.assertRaisesRegex(ValueError,'fresh output'):
                reader.restore(root/'mixed.tgz',result['archive']['sha256'],root/'source.tgz',root/'out')

    def test_no_source_preserves_every_raw_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);full,_,files,rows=setup(root)
            result=archive.reuse(full,None,root/'embedded.tgz',root/'receipt.json',root/'out')
            self.assertEqual(result['restoration_check']['embedded'],3)
            self.assertEqual(result['restoration_check']['reused'],0)
            self.assertEqual(result['manifest']['new_raw_bytes'],sum(r['bytes'] for r in rows))

    def test_equal_raw_but_different_metadata_must_not_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,source,_,rows=setup(root)
            catalog=archive.source_catalog(json.loads(source.read_text()))
            bad=copy.deepcopy(rows[0]);bad['metadata_sha256']['state.json']='0'*64
            chosen=archive.choose_storage([rows[0],bad],catalog)
            self.assertEqual([r['storage'] for r in chosen],['reuse','embedded'])

    def test_missing_unlisted_and_conflicting_raw_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,_,_,rows=setup(root)
            selected=archive.choose_storage(rows,[])
            manifest=dict(schema='ownrt.ring-live-reuse-archive.v1',bundles=selected)
            embedded={r['archive_path']:(r['bytes'],r['sha256']) for r in rows}
            reader.validate_manifest(manifest,embedded)
            for change in ('missing','extra','changed','duplicate','old-schema'):
                m=copy.deepcopy(manifest);e=dict(embedded)
                if change=='missing':e.pop(rows[0]['archive_path'])
                if change=='extra':e['run/unlisted/state.bundle']=(1,'a'*64)
                if change=='changed':e[rows[0]['archive_path']]=(1,'a'*64)
                if change=='duplicate':m['bundles'].append(m['bundles'][0])
                if change=='old-schema':m['schema']='ownrt.reused-state-archive.v1'
                with self.subTest(change=change),self.assertRaises(ValueError):reader.validate_manifest(m,e)

    def test_source_hash_and_unsafe_packet_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,source,_,_=setup(root)
            wrong=json.loads(source.read_text());wrong['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'checksum'):archive.source_catalog(wrong)
            bad=root/'bad.tgz';pack(bad,{'../escape':b'x'})
            with self.assertRaises(ValueError):reader.restore(bad,sha(bad.read_bytes()),None,root/'out')
            self.assertFalse((root/'out').exists())

    def test_full_archive_refuses_old_or_failed_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run=root/'run';proof=root/'proof';run.mkdir();proof.mkdir()
            (run/'ring-live-result.json').write_text('{}')
            for schema,passed in [('ownrt.scripted-ring-proof.v1',True),('ownrt.ring-live-proof.v1',False)]:
                (proof/'summary.json').write_text(json.dumps(dict(schema=schema,passed=passed)))
                with self.assertRaisesRegex(ValueError,'PASSED explicit'):
                    archive.full(run,proof,root/'archive.tgz',root/'receipt.json')
            self.assertFalse((root/'archive.tgz').exists())


if __name__=='__main__':unittest.main()
