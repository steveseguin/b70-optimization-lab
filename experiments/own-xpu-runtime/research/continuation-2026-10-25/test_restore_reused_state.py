import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from restore_reused_state import restore


def sha(data):return hashlib.sha256(data).hexdigest()


def archive(path,files):
    with tarfile.open(path,'x:gz') as out:
        for name,data in files:
            info=tarfile.TarInfo(name);info.size=len(data);out.addfile(info,io.BytesIO(data))


class ReuseTests(unittest.TestCase):
    def fixture(self,root,malicious=None,bad_blob=False):
        raw=b'original sealed bytes';metadata={name:name.encode() for name in ('state-seal.txt','state-index.tsv','state.json')}
        source=root/'raw.tgz'
        archive(source,[('base/state.bundle',b'changed' if bad_blob else raw)]+[('base/'+n,b) for n,b in metadata.items()])
        bundles=[dict(original_path='/original/'+part+'/state.bundle',archive_path='run/'+part+'/state.bundle',
            source_member='base/state.bundle',bytes=len(raw),sha256=sha(raw),metadata_sha256={n:sha(b) for n,b in metadata.items()}) for part in ('first','second')]
        manifest=dict(schema='ownrt.reused-state-archive.v1',source_archive=dict(bytes=source.stat().st_size,sha256=sha(source.read_bytes())),bundles=bundles)
        files=[('reused-state-map.json',json.dumps(manifest).encode())]+[('run/'+part+'/'+n,b) for part in ('first','second') for n,b in metadata.items()]
        if malicious:files.insert(0,(malicious,b'bad'))
        small=root/'metadata.tgz';archive(small,files)
        return small,sha(small.read_bytes()),source

    def test_repeated_source_restores_distinct_single_link_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);args=self.fixture(root);out=root/'restored'
            result=restore(*args,out);self.assertEqual(result['restored'],2)
            a=out/'run/first/state.bundle';b=out/'run/second/state.bundle'
            self.assertEqual(a.read_bytes(),b.read_bytes());self.assertNotEqual(a.stat().st_ino,b.stat().st_ino)
            self.assertEqual(a.stat().st_nlink,1);self.assertEqual(b.stat().st_nlink,1)
            a.write_bytes(b'mutated');self.assertNotEqual(a.read_bytes(),b.read_bytes())
            with self.assertRaises(ValueError):restore(*args,out)

    def test_wrong_archive_hash_refused_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);small,_,raw=self.fixture(root);out=root/'out'
            with self.assertRaisesRegex(ValueError,'checksum'):restore(small,'0'*64,raw,out)
            self.assertFalse(out.exists())

    def test_path_escape_and_raw_in_metadata_refused(self):
        for name in ('../escape','/absolute','run/x/state.bundle'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);args=self.fixture(root,malicious=name)
                with self.assertRaises(ValueError):restore(*args,root/'out')

    def test_source_bytes_must_match_independent_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);args=self.fixture(root,bad_blob=True)
            with self.assertRaisesRegex(ValueError,'source member bytes'):restore(*args,root/'out')

    def test_tar_links_refused_even_when_archive_hash_is_known(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);small,_,raw=self.fixture(root)
            linked=root/'links.tgz'
            with tarfile.open(linked,'x:gz') as out:
                item=tarfile.TarInfo('bad');item.type=tarfile.SYMTYPE;item.linkname='/tmp';out.addfile(item)
            with self.assertRaisesRegex(ValueError,'links'):restore(linked,sha(linked.read_bytes()),raw,root/'out')


if __name__=='__main__':unittest.main()
