"""Tiny temporary cache/archive fixtures only; no actual service/cache operation."""
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import prune_closed_restore_caches as P
A=P.A

@contextmanager
def fixture():
    with tempfile.TemporaryDirectory() as tmp:
        top=Path(tmp);base=top/'inference';base.mkdir()
        trees=[];files={};dirs={str(base):A.directory(base)}
        for name in ('closed-a','closed-b'):
            tree=base/name/'cache/torch_compile_cache';tree.mkdir(parents=True);trees.append(tree)
            for q in (tree.parent.parent,tree.parent,tree):dirs[str(q)]=A.directory(q)
            p=tree/'generated.py';p.write_bytes(b'compiled fixture '+name.encode());files[str(p)]=A.stamp(p)
            (tree.parent/'modelinfos').mkdir();(tree.parent/'modelinfos/keep').write_bytes(b'metadata')
            (tree.parent.parent/'server.log').write_bytes(b'closed log')
        fixed=dict(trees=list(map(str,trees)),files=files,directories=dirs,closure=[],active_units={})
        inp=top/'inputs.json';inp.write_text(json.dumps(fixed));external=top/'external';external.mkdir()
        archive=external/'cache.tar'
        names=dict(BASE=base,TREES=tuple(trees),INPUT=inp,TOTAL=sum(v['bytes'] for v in files.values()),COUNT=len(files),
            ARCHIVE=archive,SIDECAR=external/'cache.tar.sha256',START=top/'start.json',RECEIPT=top/'archive.json',
            PRUNE_START=top/'prune-start.json',PRUNE_RECEIPT=top/'prune.json',ROOT=top)
        with patch.multiple(A,**names),patch.object(A,'placement'),patch.object(A,'admitted',return_value=fixed),\
             patch.object(A,'storage',return_value={'fixture':True}),patch.object(A,'current_services',return_value={'fixture':True}):
            yield top,fixed

class ArchiveTests(unittest.TestCase):
    def test_copy_readback_rehash_then_marked_individual_prune(self):
        with fixture() as (top,fixed):
            row=A.copy_verify();self.assertTrue(row['passed']);self.assertEqual(row['deleted_files'],0)
            self.assertTrue(all(Path(n).exists() for n in fixed['files']))
            real_unlink=os.unlink;calls=[]
            def unlink(path,*args,**kwargs):
                self.assertTrue(A.PRUNE_START.exists())
                for tree in A.TREES:
                    marker=A.read(tree.parent/A.MARKER_NAME)
                    self.assertFalse(marker['complete_local_cache']);self.assertTrue(marker['restore_map'])
                calls.append(str(path));return real_unlink(path,*args,**kwargs)
            with patch.object(P.os,'unlink',side_effect=unlink):result=P.prune()
            self.assertTrue(result['passed']);self.assertEqual(len(calls),2)
            for tree in A.TREES:
                self.assertTrue(tree.is_dir());self.assertEqual(list(tree.iterdir()),[])
                self.assertEqual((tree.parent/'modelinfos/keep').read_bytes(),b'metadata')
                self.assertEqual((tree.parent.parent/'server.log').read_bytes(),b'closed log')
            with self.assertRaisesRegex(RuntimeError,'prior prune'):P.prune()

    def test_copy_failure_preserved_no_second_attempt(self):
        with fixture() as (_,fixed):
            with patch.object(A,'copy_archive',side_effect=OSError('copy fixture failure')):
                with self.assertRaisesRegex(OSError,'copy fixture failure'):A.copy_verify()
            self.assertFalse(A.read(A.RECEIPT)['passed'])
            self.assertTrue(all(Path(n).exists() for n in fixed['files']))
            with self.assertRaisesRegex(RuntimeError,'prior operation'):A.copy_verify()

    def test_missing_extra_and_changed_files_refuse(self):
        with fixture() as (_,fixed):
            first=Path(next(iter(fixed['files'])));data=first.read_bytes();first.unlink()
            with self.assertRaisesRegex(RuntimeError,'incomplete'):A.inventory(fixed,hash_files=False)
            first.write_bytes(data)
            with self.assertRaisesRegex(RuntimeError,'metadata changed'):A.inventory(fixed,hash_files=False)
        with fixture() as (_,fixed):
            (A.TREES[0]/'extra').write_bytes(b'x')
            with self.assertRaisesRegex(RuntimeError,'unexpected cache file'):A.inventory(fixed,hash_files=False)

    def test_symlink_and_hardlink_refuse(self):
        with fixture() as (_,fixed):
            p=Path(next(iter(fixed['files'])));target=p.parent/'outside';p.rename(target);p.symlink_to(target)
            with self.assertRaisesRegex(RuntimeError,'aliased file|unexpected cache'):A.inventory(fixed,hash_files=False)
        with fixture() as (top,fixed):
            p=Path(next(iter(fixed['files'])));os.link(p,top/'outside')
            with self.assertRaisesRegex(RuntimeError,'private regular'):A.inventory(fixed,hash_files=False)

    def test_directory_replacement_refuses_before_archive(self):
        with fixture() as (_,fixed):
            tree=A.TREES[0];tree.rename(tree.with_name('old'));tree.mkdir()
            with self.assertRaisesRegex(RuntimeError,'directory identity'):A.copy_verify()
            self.assertFalse(A.ARCHIVE.exists())

    def test_source_change_after_copy_fails_readback_or_rehash(self):
        with fixture() as (_,fixed):
            original=A.copy_archive
            def copy(*args):
                original(*args);Path(next(iter(fixed['files']))).write_bytes(b'changed')
            with patch.object(A,'copy_archive',side_effect=copy):
                with self.assertRaisesRegex(RuntimeError,'metadata changed'):A.copy_verify()
            self.assertFalse(A.read(A.RECEIPT)['passed']);self.assertTrue(A.ARCHIVE.exists())

    def test_tampered_archive_and_code_refuse_without_prune(self):
        with fixture() as (_,fixed):
            A.copy_verify()
            with A.ARCHIVE.open('r+b') as f:f.seek(512);f.write(b'BAD!')
            with self.assertRaisesRegex(RuntimeError,'member hash'):P.prune()
            self.assertFalse(A.PRUNE_START.exists());self.assertTrue(all(Path(n).exists() for n in fixed['files']))
        with fixture() as (_,fixed):
            A.copy_verify()
            with patch.object(A,'code_pins',return_value={'changed':'source'}):
                with self.assertRaisesRegex(RuntimeError,'source changed'):P.prune()
            self.assertFalse(A.PRUNE_START.exists())

    def test_marker_directory_fsync_failure_prevents_all_unlinks(self):
        with fixture() as (_,fixed):
            A.copy_verify();original=A.write
            def write(path,row,*args):
                original(path,row,*args)
                if path==A.TREES[-1].parent/A.MARKER_NAME:raise OSError('marker directory fsync failed')
            with patch.object(A,'write',side_effect=write):
                with self.assertRaisesRegex(OSError,'marker directory'):P.prune()
            self.assertTrue(all(Path(n).exists() for n in fixed['files']))
            self.assertFalse(A.read(A.PRUNE_RECEIPT)['passed']);self.assertTrue(A.PRUNE_START.exists())

    def test_held_archive_replacement_refused_before_unlink(self):
        with fixture() as (_,fixed):
            A.copy_verify();original=A.write
            def write(path,row,*args):
                original(path,row,*args)
                if path==A.TREES[-1].parent/A.MARKER_NAME:
                    A.ARCHIVE.rename(A.ARCHIVE.with_suffix('.retained'));A.ARCHIVE.write_bytes(b'replacement')
            with patch.object(A,'write',side_effect=write):
                with self.assertRaisesRegex(RuntimeError,'held recovery archive'):P.prune()
            self.assertTrue(all(Path(n).exists() for n in fixed['files']))

    def test_changed_source_immediately_before_unlink_refuses(self):
        with fixture() as (_,fixed):
            A.copy_verify();original=A.write
            def write(path,row,*args):
                original(path,row,*args)
                if path==A.TREES[-1].parent/A.MARKER_NAME:Path(next(iter(fixed['files']))).write_bytes(b'changed')
            with patch.object(A,'write',side_effect=write):
                with self.assertRaisesRegex(RuntimeError,'source changed before unlink'):P.prune()
            self.assertTrue(all(Path(n).exists() for n in fixed['files']))

    def test_partial_unlink_failure_keeps_full_recovery_map(self):
        with fixture() as (_,fixed):
            A.copy_verify();original=os.unlink;count=0
            def unlink(*args,**kwargs):
                nonlocal count
                count+=1
                if count==2:raise OSError('second unlink refused')
                return original(*args,**kwargs)
            with patch.object(P.os,'unlink',side_effect=unlink):
                with self.assertRaisesRegex(OSError,'second unlink'):P.prune()
            row=A.read(A.PRUNE_RECEIPT);self.assertFalse(row['passed']);self.assertEqual(len(row['removed_files']),1)
            self.assertEqual(set(row['restore_map']),set(fixed['files']))
            self.assertTrue(A.ARCHIVE.exists())

    def test_archive_verifier_rejects_duplicate_member(self):
        import tarfile
        with fixture() as (_,fixed):
            files=A.inventory(fixed,hash_files=True);name,row=next(iter(files.items()));data=Path(name).read_bytes();buf=io.BytesIO()
            with tarfile.open(fileobj=buf,mode='w') as tar:
                for _ in range(2):
                    info=tarfile.TarInfo(row['archive_member']);info.size=len(data);tar.addfile(info,io.BytesIO(data))
            with self.assertRaisesRegex(RuntimeError,'duplicate'):A.verify_members(buf,files)

    def test_current_service_exact_restore29_only_and_bounded_queries(self):
        fixed=A.read(A.INPUT);calls=[]
        def runner(argv,**kwargs):
            calls.append((argv,kwargs));unit=argv[3].removesuffix('.service');v=fixed['active_units'][unit]
            import shlex
            return SimpleNamespace(returncode=0,stdout='ActiveState=active\nSubState=running\nMainPID=123\nWorkingDirectory='+v['working_directory']+'\nExecStart={ path=/usr/bin/python3 ; argv[]='+shlex.join(v['argv'])+' ; ignore_errors=no ; }\n')
        self.assertEqual(len(A.current_services(fixed,runner=runner)),3)
        self.assertTrue(all(k['timeout']==15 and 'Environment' not in ' '.join(a) for a,k in calls))
        def stale(*args,**kw):
            row=runner(*args,**kw);row.stdout=row.stdout.replace('restore29','restore28');return row
        with self.assertRaisesRegex(RuntimeError,'restore29'):A.current_services(fixed,runner=stale)
        with self.assertRaisesRegex(RuntimeError,'unavailable'):
            A.current_services(fixed,runner=lambda *a,**k:SimpleNamespace(returncode=1,stdout=''))

    def test_external_mount_and_50gib_reserve(self):
        good=dict(target='/mnt/usb-models',source='/dev/sda2',fstype='fuseblk',uuid='4E0E66ED0E66CD91')
        runner=lambda *a,**k:SimpleNamespace(returncode=0,stdout=json.dumps({'filesystems':[good]}))
        with patch.object(A,'directory',return_value=dict(dev=2050,ino=2778419,uid=0,mode=0o777)),\
             patch.object(A.shutil,'disk_usage',return_value=SimpleNamespace(free=A.RESERVE+A.TOTAL+A.ARCHIVE_ALLOWANCE)):
            self.assertEqual(A.storage(before_copy=True,runner=runner)['reserve_bytes'],50*1024**3)
            good['uuid']='wrong'
            with self.assertRaisesRegex(RuntimeError,'mount identity'):A.storage(runner=runner)
            good['uuid']='4E0E66ED0E66CD91'
            with patch.object(A.shutil,'disk_usage',return_value=SimpleNamespace(free=A.RESERVE-1)):
                with self.assertRaisesRegex(RuntimeError,'50GiB'):A.storage(runner=runner)

if __name__=='__main__':unittest.main(verbosity=2)
