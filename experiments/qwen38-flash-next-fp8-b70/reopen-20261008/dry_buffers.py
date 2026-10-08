#!/usr/bin/env python3
"""Construct real-shape host buffers one rank at a time, CPU/stdlib only.

Anonymous mmap + Linux mlock measures OS-locked allocation/RSS, NOT the XPU
pinned allocator, its retention, graph pools or a whole-server peak. No model
payloads, torch, devices, endpoints, subprocesses or privileges. 20 GB maximum
process address space; one 256 MiB-or-smaller fill at a time; release each rank.
"""
import argparse
import ctypes
import datetime
import json
import mmap
from pathlib import Path
import resource
import time

from memory_plan import DEFAULT_MODEL, read_metadata, pressure_sample, sha256, should_stop
from placement_plan import HERE, storage_plan
LIMIT = 20_000_000_000
PAGE = mmap.PAGESIZE


def status():
    fields={}
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.split(':')[0] in ('VmRSS','VmLck','VmHWM','VmSize'):
            fields[line.split(':')[0]]=int(line.split()[1])*1024
    return fields


def mapped_bytes(buffers):
    return sum(((b['bytes']+PAGE-1)//PAGE)*PAGE for b in buffers)


def check_capacity(buffers, before, memlock):
    size=mapped_bytes(buffers)
    if size+before['VmSize']+256*2**20 > LIMIT:
        raise RuntimeError('20 GB process allocation bound would be exceeded')
    if memlock != resource.RLIM_INFINITY and size+before['VmLck'] > memlock:
        raise RuntimeError('existing unprivileged memlock limit cannot cover rank; not changed')
    return size


def measure_rank(plan):
    before=status()
    total=check_capacity(plan['buffers'],before,resource.getrlimit(resource.RLIMIT_MEMLOCK)[0])
    sample=pressure_sample(Path('/proc/meminfo').read_text())
    if should_stop(sample,total):
        raise RuntimeError('existing watchdog margin cannot cover dry buffers; no allocation')
    libc=ctypes.CDLL(None,use_errno=True)
    libc.mlock.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    libc.mlock.restype=ctypes.c_int
    maps=[]
    started=time.monotonic()
    try:
        for buf in plan['buffers']:
            size=((buf['bytes']+PAGE-1)//PAGE)*PAGE
            if should_stop(pressure_sample(Path('/proc/meminfo').read_text()),size):
                raise RuntimeError('watchdog margin crossed during dry construction')
            memory=mmap.mmap(-1,size,flags=mmap.MAP_PRIVATE|mmap.MAP_ANONYMOUS)
            maps.append(memory)
            addr=ctypes.addressof(ctypes.c_char.from_buffer(memory))
            # Touch bounded chunks before mlock to avoid a single 12.8 GB fault-in.
            for offset in range(0,size,64*2**20):
                if should_stop(pressure_sample(Path('/proc/meminfo').read_text())):
                    raise RuntimeError('watchdog cancelled CPU dry construction')
                ctypes.memset(addr+offset,0,min(64*2**20,size-offset))
            if libc.mlock(addr,size):
                raise OSError(ctypes.get_errno(),'mlock failed; no privileged fallback')
        loaded=status()
        result=dict(rank=plan['rank'],logical_buffer_bytes=plan['pinned_bytes'],mapped_bytes=total,
                    before=before,loaded=loaded,rss_delta_bytes=loaded['VmRSS']-before['VmRSS'],
                    locked_delta_bytes=loaded['VmLck']-before['VmLck'],seconds=time.monotonic()-started)
        result['os_locked_size_matches']=result['locked_delta_bytes']==total
    finally:
        for memory in reversed(maps):
            memory.close()  # munmap also unlocks; no driver-owned allocations
    result['after_release']=status()
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    soft,hard=resource.getrlimit(resource.RLIMIT_AS)
    cap=min([x for x in (LIMIT,soft,hard) if x != resource.RLIM_INFINITY])
    resource.setrlimit(resource.RLIMIT_AS,(cap,cap)) # child process only, no host setting
    config,tensors,metadata=read_metadata(DEFAULT_MODEL)
    mask=HERE/'placement-certified-v5.json'
    plans=storage_plan(config,tensors,json.loads(mask.read_text()))
    result=dict(schema='screen1b.cpu-os-locked-buffers.v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                method='stdlib anonymous mmap + Linux mlock, sequential ranks, real buffer shapes, zero-filled',
                xpu_pinned_allocator_measured=False,server_peak_measured=False,
                process_address_space_cap_bytes=cap,model_metadata=metadata,
                placement_sha256=sha256(mask),script_sha256=sha256(__file__),ranks=[])
    for plan in plans:
        try:
            row=measure_rank(plan); result['ranks'].append(row)
            print(json.dumps(row),flush=True)
        except (OSError,RuntimeError,MemoryError) as error:
            result['error']=str(error);break
        finally:
            args.output.write_text(json.dumps(result,indent=2)+'\n')
    if 'error' in result:
        raise SystemExit(result['error'])


if __name__=='__main__': main()
