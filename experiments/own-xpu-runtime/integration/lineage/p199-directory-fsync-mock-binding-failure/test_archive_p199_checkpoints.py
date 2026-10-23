"""Tiny CPU fixtures/in-memory tar only; never archive or prune real checkpoints."""
from contextlib import ExitStack, contextmanager
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import stat
import tempfile
import unittest
from unittest.mock import patch, MagicMock

spec=importlib.util.spec_from_file_location('p199_archive_test',Path(__file__).with_name('archive_p199_checkpoints.py'))
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
spec=importlib.util.spec_from_file_location('p199_prune_test',Path(__file__).with_name('prune_p199_checkpoints.py'))
P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)

class ArchiveTests(unittest.TestCase):
    def test_json_creation_syncs_file_then_parent_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'receipt.json';modes=[]
            with patch.object(A.os,'fsync',side_effect=lambda fd:modes.append(os.fstat(fd).st_mode)):
                A.write(target,{'fixture':True})
            self.assertEqual(len(modes),2);self.assertTrue(stat.S_ISREG(modes[0]));self.assertTrue(stat.S_ISDIR(modes[1]))

    def test_directory_sync_failure_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            def fsync(fd):
                if stat.S_ISDIR(os.fstat(fd).st_mode):raise OSError('synthetic directory fsync refusal')
            with patch.object(A.os,'fsync',side_effect=fsync):
                with self.assertRaisesRegex(OSError,'directory fsync'):A.write(Path(directory)/'marker.json',{'incomplete':True})

    def test_pin_rejects_symlink_and_changed_open(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);f=root/'source';f.write_bytes(b'x');link=root/'link';link.symlink_to(f)
            with self.assertRaises(RuntimeError):A.pin(link)
            self.assertEqual(A.pin(f)['sha256'],hashlib.sha256(b'x').hexdigest())

    def stream(self, *, value=b'x',duplicate=False,extra=False):
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as tar:
            for name in ['checkpoints',*('checkpoints/'+cid for cid in A.IDS)]:
                info=tarfile.TarInfo(name);info.type=tarfile.DIRTYPE;tar.addfile(info)
            name='checkpoints/'+A.IDS[0]+'/tiny.bin'
            for _ in range(2 if duplicate else 1):
                info=tarfile.TarInfo(name);info.size=len(value);tar.addfile(info,io.BytesIO(value))
            if extra:tar.addfile(tarfile.TarInfo('../extra'))
        stream.seek(0);return stream

    def original(self):
        return {'files':{'original':dict(archive_member='checkpoints/'+A.IDS[0]+'/tiny.bin',
                sha256=hashlib.sha256(b'x').hexdigest(),stamp={'bytes':1})}}

    def test_every_archive_member_verified(self):
        with tarfile.open(fileobj=self.stream(),mode='r:') as tar:
            self.assertEqual(len(A.verify_members(tar,self.original())),1)

    def test_corrupt_duplicate_and_foreign_members_refused(self):
        for kwargs in ({'value':b'y'},{'duplicate':True},{'extra':True}):
            with self.subTest(kwargs=kwargs),tarfile.open(fileobj=self.stream(**kwargs),mode='r:') as tar:
                with self.assertRaises(RuntimeError):A.verify_members(tar,self.original())

    def test_inventory_checks_native_digests_and_closed_file_set(self):
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            root=Path(directory);cp=root/'checkpoints';cp.mkdir();audit={'artifact_sha256':{}}
            for cid in A.IDS:
                tree=cp/cid;tree.mkdir();blobs=[]
                for i in range(128):
                    name=f'blk.{i}.state' if i<121 else f'control{i}'
                    (tree/(name+'.bin')).write_bytes(b'x')
                    blobs.append(dict(name=name,bytes=1,sha256=hashlib.sha256(b'x').hexdigest()))
                (tree/'tokens.bin').write_bytes(b'1234');(tree/'fields.tsv').write_text('synthetic fixture\n')
                manifest=dict(checkpoint_id=cid,label='experimental-postreply-front',contract='v1.2+p198',blobs=blobs,
                              token_state=dict(length=1,tokens_sha256=hashlib.sha256(b'1234').hexdigest()))
                f=tree/'manifest.json';f.write_text(json.dumps(manifest));audit['artifact_sha256'][f.relative_to(root).as_posix()]={'sha256':A.pin(f)['sha256']}
            total=sum(f.stat().st_size for f in cp.rglob('*') if f.is_file())
            for key,value in [('ROOT',root),('PACKET',cp),('CHECKPOINTS',cp),('TOTAL_BYTES',total),('TENSOR_BYTES',242)]:stack.enter_context(patch.object(A,key,value))
            stack.enter_context(patch.object(A,'closed_guards',return_value=({},audit)))
            stack.enter_context(patch.object(A.subprocess,'check_output',return_value=b''))
            self.assertEqual(len(A.inventory()['files']),262)
            (cp/A.IDS[0]/'blk.0.state.bin').write_bytes(b'y')
            with self.assertRaisesRegex(RuntimeError,'manifest extent/hash'):A.inventory()
            (cp/A.IDS[0]/'blk.0.state.bin').write_bytes(b'x');(cp/A.IDS[0]/'foreign').write_bytes(b'')
            with self.assertRaisesRegex(RuntimeError,'file set'):A.inventory()

    def test_copy_refuses_existing_output_before_any_inventory(self):
        with patch.object(A.os.path,'lexists',return_value=True),patch.object(A,'inventory') as inventory:
            with self.assertRaisesRegex(RuntimeError,'one-shot'):A.copy_verify()
            inventory.assert_not_called()

    def test_archive_fd_retained_and_replacement_refused(self):
        class Stream(io.BytesIO):
            def fileno(self):return 123
        stream=Stream(b'x');before=dict(sha256='digest',stamp=dict(dev=1,ino=2))
        with ExitStack() as stack:
            stack.enter_context(patch.object(A,'pin',return_value=before))
            stamps=stack.enter_context(patch.object(A,'stamp',return_value=before['stamp']))
            stack.enter_context(patch.object(A,'directory',return_value={}))
            stack.enter_context(patch.object(A.os,'open',return_value=123))
            stack.enter_context(patch.object(A.os,'fdopen',return_value=stream))
            stack.enter_context(patch.object(A.os,'fstat',return_value=type('S',(),dict(st_dev=1,st_ino=2))()))
            stack.enter_context(patch.object(A.tarfile,'open',return_value=MagicMock()))
            stack.enter_context(patch.object(A,'verify_members',return_value={}))
            stack.enter_context(patch.object(A.U,'sha_stream',return_value='digest'))
            with self.assertRaisesRegex(RuntimeError,'held archive'):
                with A.verified_archive({}) as (_,_,recheck):
                    self.assertFalse(stream.closed)
                    stamps.return_value=dict(dev=1,ino=3)
                    recheck()
            self.assertTrue(stream.closed)

    def test_prune_requires_verified_copy_before_any_unlink(self):
        with patch.object(P.A,'placement'),patch.object(P.A,'storage'),patch.object(P.A.os.path,'lexists',return_value=False),patch.object(P.A,'locked') as lock,patch.object(P.A,'read',return_value={'passed':False}),patch.object(Path,'unlink') as unlink:
            with self.assertRaisesRegex(RuntimeError,'verified copy'):P.prune()
            unlink.assert_not_called()

    def _prune_refusal(self,late=False,marker_sync_failure=False):
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            root=Path(directory);source=root/'tensor.bin';entry=dict(sha256='digest',stamp={'bytes':1},archive_member='checkpoints/id/tensor.bin',tensor_prune_candidate=True)
            original=dict(files={'tensor.bin':entry},directories={'.':{}},tracked_tensor_candidates=[])
            ap={'sha256':'archive'};archived=dict(passed=True,phase='verified-copy-only',original_files_unchanged=True,deleted_files=0,originals=original,archive_pin=ap,verified_member_sha256={})
            for name in ('placement','storage','locked','no_owner'):stack.enter_context(patch.object(P.A,name))
            stack.enter_context(patch.object(P.A.os.path,'lexists',return_value=False))
            stack.enter_context(patch.object(P.A,'ROOT',root));stack.enter_context(patch.object(P.A,'read',return_value=archived))
            stack.enter_context(patch.object(P.A,'inventory',return_value=original))
            checks=[]
            def final_check():
                checks.append(True)
                if late and len(checks)==3:raise OSError('synthetic final archive refusal')
            @contextmanager
            def verified(_):yield ap,{},final_check
            stack.enter_context(patch.object(P.A,'verified_archive',verified))
            stack.enter_context(patch.object(P.A,'directory',return_value={}))
            stack.enter_context(patch.object(P.A,'pin',side_effect=lambda path:{k:entry[k] for k in ('sha256','stamp')} if path==source else {'sha256':'proof'}))
            stack.enter_context(patch.object(Path,'read_text',return_value='archive  '+P.A.ARCHIVE.name+'\n'))
            writes=[]
            def write(path,row,mode='x'):
                writes.append((path,dict(row)))
                if marker_sync_failure and path==P.A.MARKER:raise OSError('synthetic marker directory fsync refusal')
            stack.enter_context(patch.object(P.A,'write',side_effect=write))
            def refuse(path):
                self.assertTrue(any(p==P.A.MARKER and not row['complete_local_checkpoints'] for p,row in writes))
                if not late:raise OSError('synthetic unlink refusal')
            unlinks=stack.enter_context(patch.object(Path,'unlink',side_effect=refuse))
            with self.assertRaisesRegex(OSError,'synthetic'):P.prune()
            if marker_sync_failure:
                unlinks.assert_not_called();self.assertFalse(writes[0][1]['passed'])
            else:self.assertFalse(writes[-1][1]['passed'])
            self.assertEqual(writes[-1][1]['restore_map'],{'tensor.bin':'checkpoints/id/tensor.bin'})

    def test_marker_precedes_first_unlink_and_failure_retains_map(self):
        self._prune_refusal()

    def test_final_archive_recheck_failure_never_publishes_passed(self):
        self._prune_refusal(late=True)

    def test_marker_parent_sync_failure_prevents_first_unlink(self):
        self._prune_refusal(marker_sync_failure=True)

if __name__=='__main__':unittest.main()
