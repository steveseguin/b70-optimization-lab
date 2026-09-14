#!/usr/bin/env python3
"""Own one separately admitted standard-XCCL recovery check; no model/retries.

--check-only reads source/receipts only and calls neither Docker nor GPU APIs.
The root agent reviews and runs the single health attempt. Historical faults
remain immutable; this controller can latch only its new recovery parent.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import uuid

ROOT=Path(__file__).resolve().parents[3]
IMAGE='sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2'
ORIGINAL=Path('/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914/control-identity.json')
HOST_REFERENCE=ORIGINAL.parent/'restored-service/container-inspect.json'
OLD_FAULT=Path('/mnt/fast-ai/bench-results/mtp-lossless-transfer-20260914/FAULT.json')
WORKER=ROOT/'experiments/qwen38-27b-b70/probes/mtp-recovery-20260914/health_worker.py'
HELPER=ROOT/'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w') as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)


def load_helper():
    spec=importlib.util.spec_from_file_location('qualified_fp8_recovery_helpers',HELPER)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    return helper


def admission(out,timeout):
    out=out.resolve()
    if out.exists():raise RuntimeError('Recovery output must be new')
    if out.is_relative_to(OLD_FAULT.parent) or (out.parent/'FAULT.json').exists():
        raise RuntimeError('Historical/current faulted campaign cannot admit a new check')
    if not 1<=timeout<=180:raise RuntimeError('Execution timeout must be between 1 and 180 seconds')
    control=json.loads(ORIGINAL.read_text());reference=json.loads(HOST_REFERENCE.read_text())
    if control['image']!=IMAGE or reference['Image']!=IMAGE:
        raise RuntimeError('Only the original qualified image is admitted')
    host=reference['HostConfig']
    required={'NetworkMode':'bridge','IpcMode':'host','CapAdd':['CAP_SYS_PTRACE'],'Privileged':False}
    if any(host.get(k)!=v for k,v in required.items()):raise RuntimeError('Qualified container transport/IPC contract differs')
    env=dict(item.split('=',1) for item in control['env'])
    required_env={'ONEAPI_DEVICE_SELECTOR':'level_zero:0,1','ZE_AFFINITY_MASK':'0,1',
                  'CCL_ZE_IPC_EXCHANGE':'pidfd','CCL_ATL_TRANSPORT':'ofi','CCL_TOPO_P2P_ACCESS':'1'}
    if any(env.get(k)!=v for k,v in required_env.items()):raise RuntimeError('Qualified device/transport selectors differ')
    # Avoid inherited Python injection; use only the qualified complete recorded env.
    if any(key in env for key in ('PYTHONPATH','PYTHONSTARTUP','LD_PRELOAD')):
        raise RuntimeError('Unexpected Python/native injection in qualified env')
    source=WORKER.read_bytes();compile(source,str(WORKER),'exec')
    return env,source,{'original_control_sha256':sha(ORIGINAL),'qualified_container_sha256':sha(HOST_REFERENCE),
        'historical_fault_sha256':sha(OLD_FAULT),'worker_sha256':hashlib.sha256(source).hexdigest(),
        'controller_sha256':sha(Path(__file__)),'helper_sha256':sha(HELPER),'host_contract':required,
        'image_id':IMAGE,'timeout_seconds':timeout,'mode':'standard Torch XCCL only; no model/custom IPC'}


def owned(info,state):
    if (info['Id']!=state['container_id'] or info['Name'].lstrip('/')!=state['container_name'] or info['Image']!=IMAGE):
        raise RuntimeError('Container ownership differs; refusing action')


def latch_fault(helper,journal,out):
    lines=[line for line in journal.splitlines() if helper.FAULT.search(line)]
    if lines:
        receipt={'at':helper.now(),'lines':lines,'scope':'new recovery check only'}
        write(out/'GPU-FAULT.json',receipt)
        latch=out.parent/'FAULT.json'
        # Do not overwrite even a fault from this newly admitted recovery window.
        try:
            with latch.open('x') as stream:
                json.dump(receipt,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        except FileExistsError:pass
        return True
    return False


def latch_failure(helper,out,reason):
    """Any attempted health failure closes this recovery root, even without Xe logs."""
    receipt={'at':helper.now(),'kind':'health_attempt_failed','reason':reason,
             'gpu_fault_confirmed':(out/'GPU-FAULT.json').exists(),'no_retry':True}
    write(out/'FAILURE.json',receipt)
    try:
        with (out.parent/'FAULT.json').open('x') as stream:
            json.dump(receipt,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    except FileExistsError:pass


def finish_owned(helper,child,out,state):
    receipt={'at':helper.now(),'stop_attempted':False,'confirmed':False,'errors':[]}
    try:
        info=helper.inspect_container(state['container_id'])
        if info is not None:
            owned(info,state)
            if info['State']['Running']:
                receipt['stop_attempted']=True
                try:
                    result=helper.run(['docker','stop','--time','30',info['Id']],check=False,timeout=45)
                    receipt.update(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
                except Exception as exc:receipt['errors'].append(f'{type(exc).__name__}: {exc}')
            info=helper.inspect_container(state['container_id'])
            if info is not None:
                owned(info,state);write(out/'container-final.json',info)
                receipt['confirmed']=not info['State']['Running']
            else:receipt['confirmed']=True
        else:receipt['confirmed']=True
        if child is not None:
            try:receipt['client_returncode']=child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                receipt['confirmed']=False;receipt['errors'].append('Attached client exit unconfirmed')
    except Exception as exc:
        receipt['confirmed']=False;receipt['errors'].append(f'{type(exc).__name__}: {exc}')
    write(out/'stop.json',receipt)
    if not receipt['confirmed']:(out/'STOP_UNCONFIRMED').write_text('Owned health container/client exit unconfirmed; no successor\n')
    return receipt['confirmed']


def worker_gate(out):
    rows=[]
    for rank in (0,1):
        row=json.loads((out/'results'/f'rank{rank}.json').read_text())
        if (type(row.get('rank')) is not int or row.get('rank')!=rank or row.get('passed') is not True or row.get('backend')!='xccl'
                or row.get('group_cleanup_completed') is not True or row.get('custom_ipc') is not False
                or row.get('model_loaded') is not False):raise RuntimeError('Worker health/cleanup gate incomplete')
        checks=row['checks']
        if len(checks)!=3 or checks[0].get('kind')!='copy_compute' or checks[0].get('values')!=4096 or checks[0].get('exact') is not True:
            raise RuntimeError('Local copy/compute check incomplete')
        for check,shape in zip(checks[1:],([1,5120],[512,5120])):
            if (check.get('kind')!='all_reduce' or check.get('shape')!=shape or check.get('exact') is not True
                    or check.get('rank_input')!=rank+1 or check.get('expected')!=3 or check.get('dtype')!='torch.float16'):raise RuntimeError('Standard XCCL health check incomplete')
        rows.append(row)
    for index in (1,2):
        if rows[0]['checks'][index]['output_sha256']!=rows[1]['checks'][index]['output_sha256']:
            raise RuntimeError('Rank all-reduce outputs differ')
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--timeout',type=int,default=180)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args();out=args.out.resolve()
    env,source,contract=admission(out,args.timeout)
    if args.check_only:
        print(json.dumps({'check_only':True,'passed':True,'docker_calls':0,'gpu_actions':0,'contract':contract},indent=2));return
    helper=load_helper()
    with open('/tmp/qwen-short-prefill-stage.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # Revalidate after lock acquisition; a preceding window may have faulted.
        env,source,contract=admission(out,args.timeout)
        name='fp8-recovery-health-'+uuid.uuid4().hex
        helper.check_available(18130,name)
        started=helper.now();helper.journal(started)
        out.mkdir(parents=True,exist_ok=False);snapshot=out/'snapshot';snapshot.mkdir();(out/'results').mkdir()
        (snapshot/'health_worker.py').write_bytes(source);(snapshot/'health_worker.py').chmod(0o444);snapshot.chmod(0o555)
        write(out/'source-contract.json',contract)
        (out/'controller-source.py').write_bytes(Path(__file__).read_bytes())
        (out/'qualified-helper-source.py').write_bytes(HELPER.read_bytes())
        (out/'qualified-control-identity.json').write_bytes(ORIGINAL.read_bytes())
        (out/'qualified-container-reference.json').write_bytes(HOST_REFERENCE.read_bytes())
        write(out/'image.json',json.loads(helper.run(['docker','image','inspect',IMAGE]).stdout))
        nodes=sorted(str(path) for path in Path('/dev/dri').glob('renderD*'))
        owners=helper.run(['fuser',*nodes],check=False)
        write(out/'owners-before.json',{'returncode':owners.returncode,'stdout':owners.stdout,'stderr':owners.stderr})
        argv=['docker','create','--name',name,'--restart','no','--network','bridge','--device','/dev/dri','--group-add','render',
              '--ipc','host','--cap-add','SYS_PTRACE','--shm-size','8g','--memory','12g','--memory-swap','16g',
              '--ulimit','core=0','--security-opt','label=disable','--workdir','/',
              '--mount',f'type=bind,source={snapshot},target=/probe,readonly',
              '--mount',f'type=bind,source={out}/results,target=/results',
              '--entrypoint','/opt/venv/bin/torchrun']
        for key,value in sorted(env.items()):argv += ['--env',f'{key}={value}']
        argv += [IMAGE,'--nnodes=1','--node-rank=0','--nproc-per-node=2','--master-addr=127.0.0.1',
                 '--master-port=29500','--max-restarts=0','/probe/health_worker.py','--out','/results']
        write(out/'launch.json',{'create_argv':argv,'started_at':started,'source_contract':contract})
        state={'status':'creating','passed':False,'container_name':name,'image_id':IMAGE,'owner_pid':os.getpid(),
               'started_at':started,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
        write(out/'state.json',state);child=None;failure=None
        def interrupted(signum,frame):raise InterruptedError(f'Health controller interrupted: {signum}')
        signal.signal(signal.SIGINT,interrupted);signal.signal(signal.SIGTERM,interrupted)
        try:
            created=helper.run(argv);identity=created.stdout.strip()
            if not re.fullmatch(r'[0-9a-f]{64}',identity):raise RuntimeError('Docker create returned no immutable container ID')
            state.update(container_id=identity,status='starting');write(out/'state.json',state)
            info=helper.inspect_container(identity);owned(info,state);write(out/'container-created.json',info)
            with (out/'worker.log').open('x') as log,(out/'memory.jsonl').open('x') as memory:
                child=subprocess.Popen(['docker','start','--attach',identity],env=helper.clean_env(),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                deadline=time.monotonic()+args.timeout;last_memory=0
                while True:
                    journal=helper.journal(started);(out/'kernel.log').write_text(journal)
                    if latch_fault(helper,journal,out):raise RuntimeError('GPU/kernel fault; all later recovery work halted')
                    if (out.parent/'FAULT.json').exists():raise RuntimeError('Recovery fault latch present')
                    if child.poll() is not None:
                        if child.returncode:raise RuntimeError(f'Health worker exited {child.returncode}; no retry')
                        break
                    if time.monotonic()>deadline:raise TimeoutError('Health execution exceeded bounded deadline; no retry')
                    if time.monotonic()-last_memory>=5:
                        info=helper.inspect_container(identity);owned(info,state)
                        entry={'at':helper.now(),'host_meminfo':Path('/proc/meminfo').read_text()}
                        try:
                            pid=info['State']['Pid'];group=next(line.split(':',2)[2] for line in Path(f'/proc/{pid}/cgroup').read_text().splitlines() if line.startswith('0::'))
                            cg=Path('/sys/fs/cgroup')/group.lstrip('/')
                            entry['cgroup']={key:(cg/key).read_text().strip() for key in ('memory.current','memory.peak','memory.events','memory.swap.current') if (cg/key).exists()}
                        except (OSError,StopIteration):entry['cgroup']='unavailable'
                        memory.write(json.dumps(entry)+'\n');memory.flush();os.fsync(memory.fileno());last_memory=time.monotonic()
                    time.sleep(1)
            state['worker_receipts']=worker_gate(out)
        except BaseException as exc:
            failure=f'{type(exc).__name__}: {exc}';state['error']=failure
            (out/'ABORTED').write_text(failure+'\n')
        finally:
            confirmed=finish_owned(helper,child,out,state) if state.get('container_id') else child is None
            try:
                # Catch kernel messages delivered just after worker exit. Read-only.
                for _ in range(3):
                    time.sleep(1)
                    journal=helper.journal(started);(out/'kernel.log').write_text(journal)
                    if latch_fault(helper,journal,out):failure=failure or 'GPU/kernel fault in tail postflight'
                owners=helper.run(['fuser',*nodes],check=False)
                write(out/'owners-after.json',{'returncode':owners.returncode,'stdout':owners.stdout,'stderr':owners.stderr})
                if owners.returncode!=1 or owners.stdout.strip():failure=failure or 'Render ownership not clear after health check'
            except Exception as exc:failure=failure or f'Postflight failed: {type(exc).__name__}: {exc}'
            state.update(status='passed' if failure is None and confirmed else ('failed' if confirmed else 'stop_unconfirmed'),
                         passed=failure is None and confirmed,stop_confirmed=confirmed,finished_at=helper.now())
            if failure:state['error']=failure
            if sha(OLD_FAULT)!=contract['historical_fault_sha256']:
                state.update(status='failed',passed=False,error='Historical fault receipt changed during recovery check')
            if not state['passed']:
                latch_failure(helper,out,state.get('error','Health container/client exit unconfirmed'))
            write(out/'state.json',state)
        if not state['passed']:raise RuntimeError(state.get('error','Health check did not pass'))
        write(out/'DONE.json',{'passed':True,'image_id':IMAGE,'state_sha256':sha(out/'state.json'),
                             'scope':'Standard copy/compute/XCCL health only; not model or custom communicator qualification'})
        print(json.dumps({'passed':True,'out':str(out),'scope':'bounded standard-XCCL recovery health'}))


if __name__=='__main__':main()
