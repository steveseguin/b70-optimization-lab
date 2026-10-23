#!/usr/bin/env python3
"""Separate one-shot removal of verified archived p199 tensor copies only."""
import argparse
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import shutil

spec=importlib.util.spec_from_file_location('_p199_archive_for_prune',Path(__file__).with_name('archive_p199_checkpoints.py'))
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)

def prune():
    A.placement();A.storage()
    A.require(not any(os.path.lexists(p) for p in (A.PRUNE_RECEIPT,A.MARKER)),'prior prune attempt exists; no retry')
    with A.locked() as check_locks,ExitStack() as retained:
        archived=A.read(A.RECEIPT)
        A.require(archived.get('passed') is True and archived.get('phase')=='verified-copy-only'
                  and archived.get('original_files_unchanged') is True and archived.get('deleted_files')==0,'verified copy required')
        before=A.inventory()
        A.require(before==archived['originals'] and not before['tracked_tensor_candidates'],'original/source/tracked status changed')
        archive_pin,members,check_archive=retained.enter_context(A.verified_archive(before))
        A.require(archive_pin==archived['archive_pin'] and members==archived['verified_member_sha256'],'archive changed')
        A.require(A.SIDECAR.read_text()==archive_pin['sha256']+'  '+A.ARCHIVE.name+'\n','archive sidecar differs')
        candidates={n:v for n,v in before['files'].items() if v['tensor_prune_candidate']}
        result=dict(schema='p199-verified-tensor-prune-v1',passed=False,started_utc=A.utc(),removed_files=[],removed_bytes=0,
                    archive_receipt_sha256=A.pin(A.RECEIPT)['sha256'],archive_sha256=archive_pin['sha256'],
                    script_sha256=A.pin(Path(__file__))['sha256'],root_free_before_bytes=shutil.disk_usage(A.ROOT).free,
                    restore_map={n:v['archive_member'] for n,v in candidates.items()})
        # Mark incomplete BEFORE the first unlink; even interruption preserves the recovery pointer.
        A.write(A.PRUNE_RECEIPT,result)
        A.write(A.MARKER,dict(complete_local_checkpoints=False,prune_started=True,archive=str(A.ARCHIVE),
            archive_sha256=archive_pin['sha256'],archive_receipt=str(A.RECEIPT),prune_receipt=str(A.PRUNE_RECEIPT),
            restore_map=result['restore_map'],retained='all4 metadata and16 small binary files; lock siblings unchanged',
            restoration='Verify archive/member hashes, reconstruct both complete trees in a fresh private destination using archive receipt restore_map; never native-inspect incomplete local trees.'))
        try:
            A.no_owner();A.storage();check_locks();check_archive()
            for name,entry in sorted(candidates.items()):
                path=A.ROOT/name
                check_locks();check_archive()
                A.require(A.directory(path.parent)==before['directories'][A.rel(path.parent)],'checkpoint directory replaced')
                A.require(A.pin(path)=={k:entry[k] for k in ('sha256','stamp')},'candidate changed before unlink')
                path.unlink();result['removed_files'].append(name);result['removed_bytes']+=entry['stamp']['bytes']
            for name,entry in before['files'].items():
                if name not in candidates:
                    A.require(A.pin(A.ROOT/name)=={k:entry[k] for k in ('sha256','stamp')},'retained metadata/control changed')
            check_locks();check_archive()
            result.update(passed=True,finished_utc=A.utc(),root_free_after_bytes=shutil.disk_usage(A.ROOT).free,
                          retained_metadata_files=4,retained_binary_files=16)
        except BaseException as error:result.update(error=str(error),finished_utc=A.utc());raise
        finally:A.write(A.PRUNE_RECEIPT,result,'w')
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prune-verified-copies',action='store_true',required=True);parser.parse_args()
    row=prune();print(json.dumps({k:row[k] for k in ('passed','removed_bytes','root_free_before_bytes','root_free_after_bytes')}))

if __name__=='__main__':main()
