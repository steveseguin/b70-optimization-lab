"""Temporary files and intercepted privilege/service calls only."""
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import archive_closed_restore_caches_privileged as C
F=C.F;A=C.A

@contextmanager
def fixture():
    with tempfile.TemporaryDirectory() as tmp:
        top=Path(tmp);base=top/'inference';base.mkdir();rec=top/'receipts';rec.mkdir()
        external=top/'external';external.mkdir();trees=[];files={};dirs={str(base):A.directory(base)}
        for label in ('old-a','old-b'):
            tree=base/label/'cache/torch_compile_cache';tree.mkdir(parents=True);trees.append(tree)
            for p in (tree.parent.parent,tree.parent,tree):dirs[str(p)]=A.directory(p)
            p=tree/'model';p.write_bytes(b'fixture '+label.encode());files[str(p)]=A.stamp(p)
            (tree.parent/'modelinfos').write_bytes(b'retain')
        fixed=dict(files=files,directories=dirs,closure=[],active_units={})
        inp=top/'inputs.json';inp.write_text(json.dumps(fixed))
        archive=external/'fixed.tar'
        paths=dict(REC=rec,ARCHIVE=archive,SIDECAR=external/'fixed.tar.sha256',
            COPY_START=rec/'copy-start.json',COPY_RESULT=rec/'copy.json',VERIFY_RESULT=rec/'verify.json',
            PRUNE_START=rec/'prune-start.json',PRUNE_RESULT=rec/'prune.json')
        def admission(op,index=None):return fixed,{},dict(sha256='admission')
        def invoke(op,index=None):
            result=F.perform(op,index)
            if not result['passed']:
                error=RuntimeError(result['error']);error.child_result=result;raise error
            return result
        with patch.multiple(A,BASE=base,TREES=tuple(trees),INPUT=inp,ROOT=top,
            COUNT=len(files),TOTAL=sum(x['bytes'] for x in files.values())),\
             patch.multiple(F,**paths),patch.object(A,'admitted',return_value=fixed),\
             patch.object(F,'source_pins',return_value={'fixture':'fixed'}),\
             patch.object(F,'verify_admission',side_effect=admission),\
             patch.object(C,'user_boundary'),patch.object(C,'guards',return_value=({'fixture':True},{'fixture':True})),\
             patch.object(C,'invoke',side_effect=invoke):
            yield top,fixed

class FilesystemTests(unittest.TestCase):
    def test_full_copy_verify_all_markers_before_any_prune(self):
        with fixture() as (_,fixed):
            copied=C.copy();self.assertTrue(copied['passed']);self.assertTrue(all(Path(n).exists() for n in fixed['files']))
            unlink=os.unlink;seen=[]
            def checked(name,*args,**kwargs):
                self.assertTrue(F.VERIFY_RESULT.exists());self.assertTrue(F.PRUNE_START.exists())
                for tree in A.TREES:self.assertTrue((tree.parent/F.MARKER_NAME).exists())
                seen.append(name);return unlink(name,*args,**kwargs)
            with patch.object(F.os,'unlink',side_effect=checked):result=C.prune()
            self.assertTrue(result['passed']);self.assertEqual(len(seen),2)
            for tree in A.TREES:
                self.assertTrue(tree.is_dir());self.assertEqual(list(tree.iterdir()),[])
                self.assertEqual((tree.parent/'modelinfos').read_bytes(),b'retain')
            with self.assertRaisesRegex(RuntimeError,'prior privileged'):C.prune()

    def test_tar_attributes_preserved_and_wrong_attributes_refused(self):
        with fixture() as (_,fixed):
            files=F.inventory(fixed);F.copy_archive(files,fixed)
            with F.ARCHIVE.open('rb') as stream:self.assertEqual(len(F.verify_members(stream,files)),2)
            name,row=next(iter(files.items()));buf=io.BytesIO()
            with tarfile.open(fileobj=buf,mode='w') as tar:
                item=tarfile.TarInfo(row['archive_member']);item.size=row['stamp']['bytes'];item.mode=0
                tar.addfile(item,io.BytesIO(Path(name).read_bytes()))
            with self.assertRaisesRegex(RuntimeError,'attributes'):F.verify_members(buf,files)

    def test_copy_post_child_guard_failure_preserves_full_copy_map(self):
        with fixture() as (_,fixed):
            failure=OSError('post-copy service changed')
            with patch.object(C,'guards',side_effect=[({},{}),failure]):
                with self.assertRaises(OSError) as caught:C.copy()
            self.assertIs(caught.exception,failure)
            row=A.read(F.COPY_RESULT);self.assertFalse(row['passed']);self.assertEqual(set(row['files']),set(fixed['files']))
            self.assertIn('archive_pin',row);self.assertTrue(all(Path(n).exists() for n in fixed['files']))

    def test_prune_post_child_guard_failure_keeps_batch_and_halts_next(self):
        with fixture() as (_,fixed):
            C.copy();failure=OSError('post-batch service changed')
            with patch.object(C,'guards',side_effect=[({},{}),({},{}),({},{}),failure]):
                with self.assertRaises(OSError) as caught:C.prune()
            self.assertIs(caught.exception,failure);row=A.read(F.PRUNE_RESULT)
            self.assertFalse(row['passed']);self.assertEqual(len(row['failed_batch']['removed_files']),1)
            self.assertEqual(len(row['removed_files']),1)
            self.assertTrue((A.TREES[1]/'model').exists());self.assertFalse(F.admission_path('prune-root',1).exists())

    def test_all_original_verification_failure_precedes_markers(self):
        with fixture() as (_,fixed):
            C.copy();Path(next(iter(fixed['files']))).write_bytes(b'changed')
            with self.assertRaises(RuntimeError):C.prune()
            self.assertFalse(F.PRUNE_START.exists())
            self.assertTrue(all(not (tree.parent/F.MARKER_NAME).exists() for tree in A.TREES))

    def test_marker_fsync_failure_prevents_all_deletion(self):
        with fixture() as (_,fixed):
            C.copy();save=C.save
            def failed(path,row):
                save(path,row)
                if path==A.TREES[-1].parent/F.MARKER_NAME:raise OSError('marker fsync')
            with patch.object(C,'save',side_effect=failed):
                with self.assertRaisesRegex(OSError,'marker fsync'):C.prune()
            self.assertTrue(all(Path(n).exists() for n in fixed['files']))

    def test_archive_replacement_after_markers_refuses_unlink(self):
        with fixture() as (_,fixed):
            C.copy();save=C.save
            def replaced(path,row):
                save(path,row)
                if path==A.TREES[-1].parent/F.MARKER_NAME:
                    F.ARCHIVE.rename(F.ARCHIVE.with_suffix('.old'));F.ARCHIVE.write_bytes(b'wrong')
            with patch.object(C,'save',side_effect=replaced):
                with self.assertRaises(RuntimeError):C.prune()
            self.assertTrue(all(Path(n).exists() for n in fixed['files']))

    def test_failed_second_batch_preserves_first_and_full_restore_map(self):
        with fixture() as (_,fixed):
            C.copy();unlink=os.unlink;calls=0
            def failed(*args,**kwargs):
                nonlocal calls
                calls+=1
                if calls==2:raise OSError('unlink refused')
                return unlink(*args,**kwargs)
            with patch.object(F.os,'unlink',side_effect=failed):
                with self.assertRaisesRegex(RuntimeError,'unlink refused'):C.prune()
            row=A.read(F.PRUNE_RESULT);self.assertFalse(row['passed']);self.assertEqual(set(row['restore_map']),set(fixed['files']))
            self.assertEqual(len(row['removed_files']),1);self.assertTrue(F.ARCHIVE.exists())

    def test_explicit_user_mode_and_secondary_receipt_preserve_primary(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'receipt';old=os.umask(0)
            try:C.save(p,{'small':True})
            finally:os.umask(old)
            self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o600)
            error=OSError('primary')
            with patch.object(C,'save',side_effect=OSError('secondary')):C.preserve_failure(p,{},error)
            self.assertIn('secondary failure receipt',' '.join(error.__notes__))

class AdmissionTests(unittest.TestCase):
    def setUp(self):self.addCleanup(C.RETAINED.clear)

    def test_fixed_cli_no_paths_or_unknown_operations(self):
        for op,index in [('shell',None),('prune-root',-1),('prune-root',18),('copy',0)]:
            with self.assertRaises(RuntimeError):C.child_argv(op,index)
        argv=C.child_argv('prune-root',17)
        self.assertEqual(argv[:5],['/usr/bin/sudo','-S','-p','','--'])
        self.assertIn('-I',argv);self.assertEqual(argv[-4:],['--operation','prune-root','--root-index','17'])
        self.assertNotIn('systemctl',' '.join(argv))

    def test_intercepted_privileged_dispatch_secret_not_argv_or_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            secret=Path(tmp)/'secret';secret.write_bytes(b'fixture-secret\n')
            row=dict(passed=True,operation='copy',root_index=None,source_sha256={'fixture':'pin'})
            process=Mock(returncode=0);process.communicate.return_value=(json.dumps(row).encode(),b'')
            popen=Mock(return_value=process)
            with patch.object(C,'SECRET',secret),patch.object(F,'source_pins',return_value={'fixture':'pin'}):result=C.invoke('copy',popen=popen)
            self.assertTrue(result['passed']);self.assertEqual(process.communicate.call_args.args,(b'fixture-secret\n',))
            self.assertNotIn('fixture-secret',repr(popen.call_args));self.assertNotIn('HOME',popen.call_args.kwargs['env'])
            process.kill.assert_not_called();process.terminate.assert_not_called()

    def test_uncertain_privileged_child_is_retained_without_kill_or_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            secret=Path(tmp)/'secret';secret.write_bytes(b'fixture\n');process=Mock()
            process.communicate.side_effect=subprocess.TimeoutExpired('fixed',900);popen=Mock(return_value=process)
            with patch.object(C,'SECRET',secret):
                with self.assertRaises(subprocess.TimeoutExpired):C.invoke('copy',popen=popen)
            self.assertEqual(len(C.RETAINED),1);self.assertIs(C.RETAINED[0]['process'],process)
            popen.assert_called_once();process.kill.assert_not_called();process.terminate.assert_not_called()

    def test_user_boundary_refuses_root_before_service_queries(self):
        with patch.object(C.os,'geteuid',return_value=0),patch.object(A,'current_services') as query:
            with self.assertRaisesRegex(RuntimeError,'normal user'):C.user_boundary()
            query.assert_not_called()

    def test_admission_freshness_sources_and_exact_three_service_proof(self):
        fixed=A.read(A.INPUT);services={}
        for unit,x in fixed['active_units'].items():
            services[unit]=dict(active=True,main_pid=123,state_root=x['state_root'],working_directory=x['working_directory'],
                argv_sha256=hashlib.sha256(json.dumps(x['argv'],separators=(',',':')).encode()).hexdigest())
        parent=dict(dev=2050,ino=2778419,uid=0,mode=0o777)
        row=dict(schema='closed-cache-privileged-admission.v1',operation='prune-root',root_index=0,
                 source_sha256={'source':'pin'},monotonic=100,boot_id='fixture-boot',services=services,
                 storage=dict(parent=parent,mount=dict(target='/mnt/usb-models',source='/dev/sda2',fstype='fuseblk',uuid='4E0E66ED0E66CD91'),reserve_bytes=A.RESERVE,free_bytes=A.RESERVE))
        with patch.object(F,'user_json',return_value=(row,{})),patch.object(F,'source_pins',return_value={'source':'pin'}),\
             patch.object(F.time,'monotonic',return_value=110),patch.object(Path,'read_text',return_value='fixture-boot'),\
             patch.object(A,'admitted',return_value=fixed),patch.object(A,'directory',return_value=parent):
            F.verify_admission('prune-root',0)
            row['monotonic']=-100
            with self.assertRaisesRegex(RuntimeError,'stale'):F.verify_admission('prune-root',0)
            row['monotonic']=100;row['source_sha256']={}
            with self.assertRaisesRegex(RuntimeError,'source binding'):F.verify_admission('prune-root',0)
            row['source_sha256']={'source':'pin'};next(iter(services.values()))['state_root']='old'
            with self.assertRaisesRegex(RuntimeError,'restore29'):F.verify_admission('prune-root',0)

if __name__=='__main__':unittest.main(verbosity=2)
