#!/usr/bin/env python3
"""One bounded, standard Torch/XCCL recovery check; no model or custom IPC code."""
from __future__ import annotations
import argparse
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path


def save(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    if args.check_only:
        print(json.dumps({'check_only':True,'torch_imported':False,'world_size':2,'collective_shapes':[[1,5120],[512,5120]],'backend':'xccl'}))
        return
    # Every import above is stdlib; check-only cannot initialize a GPU backend.
    import torch
    import torch.distributed as dist
    rank=int(os.environ['RANK']);local_rank=int(os.environ['LOCAL_RANK'])
    if int(os.environ['WORLD_SIZE'])!=2 or rank not in (0,1) or local_rank!=rank:
        raise RuntimeError('Exactly two local ranks are required')
    args.out.mkdir(parents=True,exist_ok=True)
    path=args.out/f'rank{rank}.json'
    result={'rank':rank,'local_rank':local_rank,'passed':False,'backend':'xccl','torch_version':torch.__version__,
            'custom_ipc':False,'model_loaded':False,'checks':[],'group_cleanup_completed':False}
    save(path,result)
    try:
        if torch.xpu.device_count()!=2:
            raise RuntimeError('Exactly two XPU devices must be visible')
        torch.xpu.set_device(local_rank)
        device=torch.device(f'xpu:{local_rank}')
        properties_api=getattr(torch.xpu,'get_device_properties',None)
        if properties_api is not None:
            properties=properties_api(device)
            device_uuid=getattr(properties,'uuid',None)
            result['device_properties']={'name':getattr(properties,'name',None),
                'uuid':None if device_uuid is None else str(device_uuid),
                'total_memory':getattr(properties,'total_memory',None)}
        else:
            result['device_properties']={'available':False,'reason':'Torch properties API unavailable'}
        source=torch.arange(64,dtype=torch.float32).to(torch.float16).div(8).repeat(64)
        copied=source.to(device).clone()
        computed=copied.mul(2).sub(copied)
        torch.xpu.synchronize(device)
        actual=computed.cpu()
        if not torch.equal(actual,source):
            raise RuntimeError('Local exact copy/compute check failed')
        result['checks'].append({'kind':'copy_compute','values':4096,'exact':True,
                                 'output_sha256':hashlib.sha256(actual.numpy().tobytes()).hexdigest()})
        peer=getattr(torch.xpu,'can_device_access_peer',None)
        if peer is None:
            result['peer_capability']={'available':False,'reason':'Torch API unavailable'}
        else:
            try:
                supported=bool(peer(local_rank,1-local_rank))
            except NotImplementedError:
                result['peer_capability']={'available':False,'reason':'Torch API not implemented'}
            else:
                result['peer_capability']={'available':True,'can_access_peer':supported}
                if not supported:raise RuntimeError('Peer access unavailable on qualified two-card topology')
        save(path,result)
        dist.init_process_group(backend='xccl',timeout=timedelta(seconds=45))
        result['group_initialized']=True;save(path,result)
        for shape in ((1,5120),(512,5120)):
            values=torch.full(shape,rank+1,dtype=torch.float16,device=device)
            work=dist.all_reduce(values,op=dist.ReduceOp.SUM,async_op=True)
            work.wait(timeout=timedelta(seconds=30))
            torch.xpu.synchronize(device)
            actual=values.cpu()
            if not torch.equal(actual,torch.full(shape,3,dtype=torch.float16)):
                raise RuntimeError(f'XCCL exact sum failed: {shape}')
            result['checks'].append({'kind':'all_reduce','shape':list(shape),'dtype':'torch.float16',
                                     'rank_input':rank+1,'expected':3,'exact':True,
                                     'output_sha256':hashlib.sha256(actual.numpy().tobytes()).hexdigest()})
            save(path,result)
        # Normal successful cleanup after both explicitly completed collectives.
        # Failure paths record/exit; they never submit cleanup GPU operations.
        dist.destroy_process_group()
        result['group_cleanup_completed']=True
        result['passed']=True;save(path,result)
    except BaseException as exc:
        result['error']=f'{type(exc).__name__}: {exc}'
        save(path,result)
        raise


if __name__=='__main__':main()
