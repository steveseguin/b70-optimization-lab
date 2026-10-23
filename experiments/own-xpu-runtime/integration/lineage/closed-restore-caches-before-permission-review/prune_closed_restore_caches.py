#!/usr/bin/env python3
"""Remove only individually reverified archived restore20..28 compiler files."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil

spec=importlib.util.spec_from_file_location('_closed_cache_archive_for_prune',Path(__file__).with_name('archive_closed_restore_caches.py'))
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)

def prune():
    A.placement()
    with A.locked() as check_lock:
        A.require(not any(os.path.lexists(p) for p in (A.PRUNE_START,A.PRUNE_RECEIPT)),
                  'prior prune attempt exists; no retry')
        fixed=A.admitted();A.storage();services=A.current_services(fixed)
        receipt_pin=A.pin(A.RECEIPT);archived=A.read(A.RECEIPT)
        A.require(archived.get('passed') is True and archived.get('phase')=='verified-copy-only' and
                  archived.get('source_rehash_equal') is True and archived.get('deleted_files')==0,'verified archive required')
        A.require(A.code_pins()==archived['source_sha256'],'archive/prune source changed')
        files=A.inventory(fixed,hash_files=True);A.require(files==archived['files'],'source rehash/inventory mismatch')
        markers=[t.parent/A.MARKER_NAME for t in A.TREES]
        A.require(not any(os.path.lexists(p) for p in markers),'prior incomplete cache marker exists')
        with A.verified_archive(files) as (archive_pin,members,check_archive):
            A.require(archive_pin==archived['archive_pin'] and members==archived['member_sha256'],'recovery archive mismatch')
            A.require(A.SIDECAR.read_text()==archive_pin['sha256']+'  '+A.ARCHIVE.name+'\n','archive sidecar mismatch')
            row=dict(schema='closed-restore-caches-prune.v1',passed=False,started_utc=A.utc(),
                archive_receipt_sha256=receipt_pin['sha256'],archive_sha256=archive_pin['sha256'],
                source_sha256=A.code_pins(),initial_services=services,removed_files=[],removed_bytes=0,
                root_free_before_bytes=shutil.disk_usage(A.ROOT).free,
                restore_map={n:v['archive_member'] for n,v in files.items()})
            # Exclusive durable journal and every per-root marker precede ALL unlinks.
            A.write(A.PRUNE_START,row)
            try:
                for tree,marker in zip(A.TREES,markers):
                    A.write(marker,dict(schema='incomplete-archived-compiler-cache.v1',complete_local_cache=False,
                        tree=str(tree),archive=str(A.ARCHIVE),archive_sha256=archive_pin['sha256'],
                        archive_receipt=str(A.RECEIPT),archive_receipt_sha256=receipt_pin['sha256'],
                        restore_map={n:v['archive_member'] for n,v in files.items() if Path(n).is_relative_to(tree)},
                        recovery='Verify tar and member SHA256; extract into a fresh directory, then restore each exact map entry. No automatic reuse/restart. Logs/state/overlay/modelinfos and active restore29 are untouched.'))
                A.current_services(fixed);A.storage();check_lock();check_archive()
                A.require(A.pin(A.RECEIPT)==receipt_pin,'verified receipt changed')
                for tree in A.TREES:
                    A.current_services(fixed);check_lock();check_archive()
                    for name,entry in sorted(files.items()):
                        path=Path(name)
                        if not path.is_relative_to(tree):continue
                        check_archive()
                        A.require(A.directory(path.parent)==fixed['directories'][str(path.parent)],'source directory changed')
                        A.require(A.pin(path)=={k:entry[k] for k in ('stamp','sha256')},'source changed before unlink')
                        # A held no-follow parent FD prevents pathname redirection at unlink.
                        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
                        try:
                            s=os.fstat(fd);expected=fixed['directories'][str(path.parent)]
                            A.require((s.st_dev,s.st_ino)==(expected['dev'],expected['ino']),'parent changed before unlink')
                            s=os.stat(path.name,dir_fd=fd,follow_symlinks=False)
                            A.require((s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==
                                tuple(entry['stamp'][k] for k in ('dev','ino','bytes','mtime_ns','ctime_ns')),'file changed at unlink')
                            check_archive();os.unlink(path.name,dir_fd=fd);os.fsync(fd)
                        finally:os.close(fd)
                        row['removed_files'].append(name);row['removed_bytes']+=entry['stamp']['bytes']
                check_lock();check_archive();A.current_services(fixed)
                A.require(row['removed_bytes']==A.TOTAL and len(row['removed_files'])==A.COUNT,'removal count mismatch')
                row.update(passed=True,finished_utc=A.utc(),root_free_after_bytes=shutil.disk_usage(A.ROOT).free)
            except BaseException as error:
                row.update(error_type=type(error).__name__,error=str(error)[:4096],finished_utc=A.utc())
                A.write(A.PRUNE_RECEIPT,row);raise
            A.write(A.PRUNE_RECEIPT,row)
    return row

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prune-verified-copies',action='store_true',required=True);p.parse_args()
    row=prune();print(json.dumps({k:row[k] for k in ('passed','removed_bytes','root_free_before_bytes','root_free_after_bytes')}))

if __name__=='__main__':main()
