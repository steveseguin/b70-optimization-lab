import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from restore_state_bundles import restore


class RestoreTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.raw=b'authenticated state bytes';self.sha=hashlib.sha256(self.raw).hexdigest()
        self.blob=self.root/'blobs/sha256'/self.sha;self.blob.parent.mkdir(parents=True);self.blob.write_bytes(self.raw)
        self.rows=[]
        for i in range(2):
            folder=self.root/f'run/{i}/state';folder.mkdir(parents=True)
            self.rows.append(dict(archive_path=f'run/{i}/state/state.bundle',blob='blobs/sha256/'+self.sha,
                                  sha256=self.sha,bytes=len(self.raw)))
        self.write()

    def write(self):
        (self.root/'state-bundle-map.json').write_text(json.dumps(dict(schema='ownrt.state-bundle-cas.v1',bundles=self.rows)))

    def test_shared_blob_restores_as_independent_exact_copies(self):
        self.assertEqual(restore(self.root)['restored'],2)
        a,b=[self.root/r['archive_path'] for r in self.rows]
        self.assertEqual(a.read_bytes(),self.raw);self.assertEqual(b.read_bytes(),self.raw)
        self.assertEqual(a.stat().st_nlink,1);self.assertEqual(b.stat().st_nlink,1)
        self.assertNotEqual(a.stat().st_ino,b.stat().st_ino)

    def test_corrupted_blob_refused_before_any_copy(self):
        self.blob.write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'digest'):restore(self.root)
        self.assertFalse((self.root/self.rows[0]['archive_path']).exists())

    def test_path_escape_and_existing_destination_refused(self):
        self.rows[0]['archive_path']='../state.bundle';self.write()
        with self.assertRaisesRegex(ValueError,'relative'):restore(self.root)
        self.rows[0]['archive_path']=self.rows[1]['archive_path'];self.write()
        with self.assertRaisesRegex(ValueError,'unique'):restore(self.root)


if __name__=='__main__':unittest.main()
