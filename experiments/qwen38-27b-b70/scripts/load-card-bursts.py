#!/usr/bin/env python3
"""Bursty compute on one card, to stand in for the desktop's work on card 03:00.0 (notes/2026-10-17-hang-repro.md).

The desktop (gnome-shell) renders on card 03 only, so only card 03 shares its engines and execution units with
another client while a two-card exchange runs. This loads one card the same way, in bursts: a burst of fp16 matmuls
lasting 1-20 ms (one to eight 2048 x 2048 x 2048 products per kernel, synchronized), then an idle of 2-50 ms, drawn
at random, until --minutes pass. Synthetic tensors only; about 50 MB of device memory.
"""
import argparse
import random
import time

import torch

ap = argparse.ArgumentParser()
ap.add_argument('--device', type=int, default=0)
ap.add_argument('--minutes', type=float, default=20)
ap.add_argument('--seed', type=int, default=7)
a = ap.parse_args()
rng = random.Random(a.seed)
dev = torch.device('xpu', a.device)
x = torch.randn(2048, 2048, device=dev, dtype=torch.float16) * 0.01
print('LOAD on xpu:%d %s' % (a.device, torch.xpu.get_device_properties(dev)), flush=True)
end = time.time() + a.minutes * 60
bursts = 0
while time.time() < end:
    stop = time.perf_counter() + rng.uniform(0.001, 0.020)
    while time.perf_counter() < stop:
        for _ in range(rng.randint(1, 8)):
            y = x @ x
        torch.xpu.synchronize()
    bursts += 1
    time.sleep(rng.uniform(0.002, 0.050))
print('LOAD DONE %d bursts on xpu:%d' % (bursts, a.device), flush=True)
