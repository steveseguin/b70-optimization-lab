#!/usr/bin/env python3
"""User coordinator for fixed privileged cache filesystem operations only."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_fixed_cache_filesystem_child',HERE/'closed_restore_cache_fs.py')
F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F)
A=F.A
RETAINED=[]
SECRET=Path('/home/steve/SUDOPASSWORD.txt')
MAX_OUTPUT=32*1024**2

def save(path,row):
    # Explicit new-file mode; never chmod/chown an original or rely on umask.
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    with os.fdopen(fd,'w') as out:
        json.dump(row,out,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
    A.sync_parent(path)

def preserve_failure(path,row,error):
    row.update(passed=False,error_type=type(error).__name__,error=str(error)[:4096])
    try:save(path,row)
    except BaseException as secondary:error.add_note('secondary failure receipt: '+type(secondary).__name__)

def user_boundary():
    A.require(os.geteuid()==F.USER_UID,'service coordinator must remain the normal user')
    A.placement()

def guards(*,before_copy=False):
    fixed=A.admitted()
    return A.current_services(fixed),A.storage(before_copy=before_copy)

def admit(operation,index=None):
    services,storage=guards(before_copy=operation=='copy')
    row=dict(schema='closed-cache-privileged-admission.v1',operation=operation,root_index=index,
             source_sha256=F.source_pins(),services=services,storage=storage,
             boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),monotonic=time.monotonic())
    path=F.admission_path(operation,index)
    save(path,row)
    return row

def child_argv(operation,index=None):
    F.key(operation,index)
    result=['/usr/bin/sudo','-S','-p','','--','/usr/bin/nice','-n','19',
            '/usr/bin/taskset','-c','8-15,24-31','/usr/bin/python3','-I','-B',str(F.CHILD),
            '--operation',operation]
    if index is not None:result+=['--root-index',str(index)]
    return result

def invoke(operation,index=None,*,popen=subprocess.Popen):
    """Password is consumed only by sudo, never printed or sent as an argument."""
    argv=child_argv(operation,index)
    secret=SECRET.read_bytes().strip()+b'\n'
    A.require(1<len(secret)<=4096 and b'\n' not in secret[:-1],'local sudo credential format refused')
    environment={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8',
                 'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'}
    # Do not use subprocess.run(timeout=...): its timeout would kill a filesystem
    # operation at an uncertain boundary. Retain the process and coordinator.
    uncertain=dict(process=None,argv=argv)
    try:
        child=popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment)
        uncertain['process']=child
    except BaseException:
        RETAINED.append(uncertain);raise
    try:
        stdout,stderr=child.communicate(secret,timeout=900)
    except BaseException:
        RETAINED.append(uncertain);raise
    finally:secret=b''
    A.require(len(stdout)<=MAX_OUTPUT and len(stderr)<=65536,'privileged output exceeded fixed bound')
    try:row=json.loads(stdout)
    except (ValueError,UnicodeError):
        raise RuntimeError('fixed filesystem child returned no valid result; stderr SHA256='+
                           __import__('hashlib').sha256(stderr).hexdigest()) from None
    A.require(type(row) is dict and row.get('operation')==operation and row.get('root_index')==index and
              row.get('source_sha256')==F.source_pins(),'filesystem result identity mismatch')
    row['child_returncode']=child.returncode
    row['stderr_sha256']=__import__('hashlib').sha256(stderr).hexdigest()
    if child.returncode!=0 or row.get('passed') is not True:
        error=RuntimeError('fixed filesystem child refused: '+str(row.get('error','unsuccessful exit'))[:4096])
        error.child_result=row
        raise error
    return row

def fresh(*paths):
    A.require(not any(os.path.lexists(p) for p in paths),'prior privileged operation exists; no retry')

def copy():
    user_boundary()
    fresh(F.COPY_START,F.COPY_RESULT,F.VERIFY_RESULT,F.PRUNE_START,F.PRUNE_RESULT,
          F.ARCHIVE,F.SIDECAR,F.admission_path('copy'),F.attempt_path('copy'))
    proof=admit('copy')
    start=dict(passed=False,phase='copy-started',source_sha256=F.source_pins(),
               original_refusal_preserved=True,archive=str(F.ARCHIVE),admission=proof)
    save(F.COPY_START,start)
    result=None
    try:
        result=invoke('copy')
        A.require(result['phase']=='copy-verified' and result['source_rehash_equal'] is True and
                  len(result['files'])==A.COUNT and sum(v['stamp']['bytes'] for v in result['files'].values())==A.TOTAL,
                  'complete eighteen-root copy proof required')
        result['final_services'],result['final_storage']=guards()
        save(F.COPY_RESULT,result)
    except BaseException as error:
        failed=getattr(error,'child_result',result if result is not None else start)
        preserve_failure(F.COPY_RESULT,failed,error);raise
    return result

def prune():
    user_boundary()
    fresh(F.PRUNE_START,F.PRUNE_RESULT,F.VERIFY_RESULT,F.admission_path('verify'),F.attempt_path('verify'))
    copied,copy_pin=F.copy_result();files=copied['files']
    markers=[t.parent/F.MARKER_NAME for t in A.TREES]
    fresh(*markers,*[F.admission_path('prune-root',i) for i in range(18)],
          *[F.attempt_path('prune-root',i) for i in range(18)])
    A.require(all(os.access(p.parent,os.W_OK|os.X_OK,effective_ids=True) for p in markers),
              'user marker parents must be writable')
    admit('verify')
    row=dict(passed=False,phase='prune-started',source_sha256=F.source_pins(),
             copy_receipt_sha256=copy_pin['sha256'],
             restore_map={n:v['archive_member'] for n,v in files.items()},batches=[],removed_files=[],removed_bytes=0)
    last_batch=None
    try:
        verified=invoke('verify');verified['final_services'],verified['final_storage']=guards()
        A.require(verified['phase']=='all-originals-and-archive-verified' and
                  verified['copy_receipt_sha256']==copy_pin['sha256'],'full verification before all markers required')
        save(F.VERIFY_RESULT,verified)
        save(F.PRUNE_START,row)
        for tree,marker in zip(A.TREES,markers):
            save(marker,dict(schema='incomplete-privileged-archived-cache.v1',complete_local_cache=False,
                 tree=str(tree),archive=str(F.ARCHIVE),archive_sha256=copied['archive_pin']['sha256'],
                 copy_receipt=str(F.COPY_RESULT),copy_receipt_sha256=copy_pin['sha256'],
                 restore_map={n:v for n,v in row['restore_map'].items() if Path(n).is_relative_to(tree)},
                 recovery='Verify whole archive and all member hashes; reconstruct exact recorded files in a fresh directory. No automatic restart or reuse.'))
        F.check_markers(files,copy_pin)
        for index,tree in enumerate(A.TREES):
            admit('prune-root',index)
            batch=invoke('prune-root',index)
            last_batch=batch
            expected={n for n in files if Path(n).is_relative_to(tree)}
            A.require(batch['phase']=='root-pruned' and set(batch['removed_files'])==expected and
                      batch['removed_bytes']==sum(files[n]['stamp']['bytes'] for n in expected),'batch result differs')
            row['batches'].append(dict(root_index=index,files=len(expected),bytes=batch['removed_bytes']))
            row['removed_files']+=batch['removed_files'];row['removed_bytes']+=batch['removed_bytes']
            batch['final_services'],batch['final_storage']=guards()
            save(F.REC/(F.PREFIX+f'-batch-{index:02d}.json'),batch)
            last_batch=None
        A.require(len(row['removed_files'])==A.COUNT and row['removed_bytes']==A.TOTAL,'total prune proof differs')
        row.update(passed=True,phase='all-fixed-cache-files-pruned')
        save(F.PRUNE_RESULT,row)
    except BaseException as error:
        if hasattr(error,'child_result'):row['failed_batch']=error.child_result
        elif last_batch is not None:row['failed_batch']=last_batch
        preserve_failure(F.PRUNE_RESULT,row,error);raise
    return row

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--plan',action='store_true');modes.add_argument('--copy-verify',action='store_true')
    modes.add_argument('--prune-verified',action='store_true');args=parser.parse_args()
    user_boundary()
    try:
        if args.plan:
            files=A.inventory(A.admitted(),hash_files=False)
            result=dict(read_only=True,privileged_calls=False,service_queries=False,cache_contents_read=False,
                        roots=18,files=len(files),bytes=A.TOTAL,archive=str(F.ARCHIVE),source_sha256=F.source_pins())
        else:
            row=copy() if args.copy_verify else prune()
            result={k:row[k] for k in ('passed','phase')}
        print(json.dumps(result,indent=2))
    except BaseException:
        if RETAINED:
            while True:time.sleep(30)  # no signal/retry/FD disposal of uncertain child
        raise

if __name__=='__main__':main()
