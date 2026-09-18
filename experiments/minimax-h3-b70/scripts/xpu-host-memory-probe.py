#!/usr/bin/env python3
"""Bounded diagnostic for driver-held host memory on the two-B70 host (2026-09-18).

Session 9 of the MiniMax-H3 first light: the runner's own RSS stayed under 0.9 GiB while MemAvailable fell from
11 GiB to 1.2 GiB in eight seconds of copying encoder tensors to xpu:0, and the watchdog killed it. The earlier
research-load incident (experiments/qwen38-27b-b70/notes/2026-09-15-research-load-host-oom.md) saw 12.65 GiB of
driver-held pages via xe dma-buf exports with both cards visible and no PYTORCH_ALLOC_CONF=expandable_segments:True.

This probe allocates GIB one-GiB buffers on xpu:0 in one of two ways and prints MemAvailable and the number of
dma-buf file descriptors after each, so the four combinations {both cards visible, one card} x {allocator flag
unset, expandable_segments:True} can be compared in under a minute each. Run it under mem-watchdog.sh with the
FP8 service stopped. Environment: GIB (default 8), MODE=fill (torch.empty + fill_) or copy (host bytearray ->
torch.frombuffer -> .to('xpu:0'), the loader's path), ONEAPI_DEVICE_SELECTOR / PYTORCH_ALLOC_CONF as under test.
"""
import os
import sys
import time


def mem_available_mib() -> int:
    with open('/proc/meminfo') as fh:
        for line in fh:
            if line.startswith('MemAvailable:'):
                return int(line.split()[1]) // 1024
    return -1


def dmabuf_fds() -> int:
    n = 0
    for name in os.listdir('/proc/self/fd'):
        try:
            if 'dmabuf' in os.readlink(f'/proc/self/fd/{name}'):
                n += 1
        except OSError:
            pass
    return n


def main() -> int:
    import torch
    gib = int(os.environ.get('GIB', '8'))
    mode = os.environ.get('MODE', 'fill')
    print(f"devices visible {torch.xpu.device_count()}  selector {os.environ.get('ONEAPI_DEVICE_SELECTOR', '<unset>')}  "
          f"alloc_conf {os.environ.get('PYTORCH_ALLOC_CONF', '<unset>')}  mode {mode}", flush=True)
    torch.xpu.init()
    base = mem_available_mib()
    print(f"start: MemAvailable {base} MiB, dmabuf fds {dmabuf_fds()}", flush=True)
    keep = []
    for i in range(gib):
        if mode == 'copy':
            host = torch.frombuffer(bytearray(2 ** 30), dtype=torch.uint8)
            t = host.to('xpu:0')
            del host
        else:
            t = torch.empty(2 ** 30, dtype=torch.uint8, device='xpu:0')
            t.fill_(1)
        torch.xpu.synchronize()
        keep.append(t)
        avail = mem_available_mib()
        print(f"{i + 1:2d} GiB on xpu:0: MemAvailable {avail} MiB (delta {base - avail:+d}), dmabuf fds {dmabuf_fds()}",
              flush=True)
        if avail < 2500:
            print("stopping early: MemAvailable under 2.5 GiB", flush=True)
            break
    time.sleep(1)
    final = mem_available_mib()
    print(f"end: {len(keep)} GiB held on device, MemAvailable {final} MiB (delta {base - final:+d}), dmabuf fds {dmabuf_fds()}",
          flush=True)
    del keep
    torch.xpu.synchronize()
    torch.xpu.empty_cache()
    time.sleep(1)
    print(f"after free: MemAvailable {mem_available_mib()} MiB", flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
