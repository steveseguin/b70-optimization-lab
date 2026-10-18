#!/usr/bin/env python3
"""The two-card exchange alone, at the server's sizes, as fast as it goes (notes/2026-10-17-hang-repro.md).

The 06:23 hang was in a prompt step (443 rows after a cache hit). Every TP2 step issues 134 all-gathers of
[rows, 5120] fp16 (b70-allgather-allreduce) and one of [rows sampled, 124160] (the vocabulary gather), and the server's
oneCCL environment (CCL_SYCL_*_SIMPLE_THRESHOLD=4 GiB) sends prompt-size gathers (> 1 MiB per rank) down the "simple"
path that oneCCL by default uses only up to 1 MiB. This client issues server-like steps: 134 gathers of the step's
rows, each after a [rows, 5120] x [5120, 5120] matmul (a linear layer's work), then the vocabulary gather and a host
wait for the step, as the server waits for its sampled tokens. Steps are prompt-size (30-832 rows) or decode-size
(1-6 rows) by --prompt-share; both ranks draw the same rows from the same seed. Each rank adds its own random extra
matmuls before some gathers (--skew), so the two cards reach a gather at different times and the waiting side waits,
as when one card has more work in a step; --gap-share of steps are followed by an idle of 0.05-0.3 s (agent traffic).

Run under torch.distributed.run with two processes (one per card) and the server's oneCCL environment. Rank 0 writes a
JSON line every --report-s seconds. A watchdog thread on each rank: if no step finishes for --stall-s seconds, it
prints STALL with the step, rows and gather index it is in, dumps every Python thread's stack (faulthandler), and
exits the process after another 60 s. Every 64th step checks the gathered bytes (each rank's half equals its input).
Synthetic tensors only.
"""
import argparse
import faulthandler
import json
import os
import random
import sys
import threading
import time

import torch
import torch.distributed as dist

ap = argparse.ArgumentParser()
ap.add_argument('--minutes', type=float, default=60)
ap.add_argument('--seed', type=int, default=20261017)
ap.add_argument('--prompt-share', type=float, default=0.5, help='share of steps with 30-832 rows (rest 1-6 rows)')
ap.add_argument('--gathers', type=int, default=134, help='hidden-size gathers per step')
ap.add_argument('--skew', type=float, default=0.25, help='share of gathers preceded by 1-4 extra matmuls on one rank')
ap.add_argument('--gap-share', type=float, default=0.1, help='share of steps followed by a 0.05-0.3 s idle')
ap.add_argument('--stall-s', type=float, default=10)
ap.add_argument('--report-s', type=float, default=60)
ap.add_argument('--out', required=True)
ap.add_argument('--marks', action='store_true', help='after every gather, copy its running number to pinned host memory')
ap.add_argument('--mismatch-test', action='store_true',
                help='rank 1 runs one extra step at the end (a known hang, to check what the marks show)')
a = ap.parse_args()
rank, world = int(os.environ['RANK']), int(os.environ['WORLD_SIZE'])
torch.xpu.set_device(rank)
dev = torch.device('xpu', rank)
dist.init_process_group('xccl', rank=rank, world_size=world, device_id=dev)
shared = random.Random(a.seed)            # the same draws on both ranks: rows per step, gaps
own = random.Random(a.seed * 31 + rank)  # this rank's skew only
torch.manual_seed(1234 + rank)
HID, VOCAB = 5120, 124160
w = torch.randn(HID, HID, device=dev, dtype=torch.float16) * 0.01
xs = torch.randn(832, HID, device=dev, dtype=torch.float16)
gs = torch.empty((world * 832, HID), device=dev, dtype=torch.float16)
lv = torch.randn(832, VOCAB, device=dev, dtype=torch.float16)
gv = torch.empty((world * 832, VOCAB), device=dev, dtype=torch.float16)
where = {'step': -1, 'rows': 0, 'gather': -1, 'done_at': time.time()}
# Device progress marks (--marks): around each gather k this rank's queue copies a number from a device table into
# pinned host memory: 2k-1 before the gather (it lands once the kernel before the gather has finished) and 2k after it
# (it lands once the gather has finished on this card). On a stall the host reads, without touching the stuck queue,
# whether this card is inside gather k (odd value) or still in a kernel before it (even value, k-1 finished).
R = 1 << 16
issued = [0]
if a.marks:
    mark_table = torch.arange(R, dtype=torch.int32, device=dev)
    mark_host = torch.full((1,), -1, dtype=torch.int32).pin_memory()


def mark(v):
    mark_host.copy_(mark_table[v % R:v % R + 1], non_blocking=True)


def card_state():
    v = int(mark_host[0])
    if v < 0:
        return 'no mark landed yet'
    top = 2 * issued[0] + 1   # the largest value already queued (the next gather's before-mark)
    full = top - ((top - v) % R)
    k = (full + 1) // 2
    if full % 2:
        return 'inside gather %d (started on the card, not finished)' % k
    if k == issued[0]:
        return 'every issued gather finished'
    return 'gather %d finished; gather %d not started on the card (a kernel before it still running)' % (k, k + 1)


def gather(out, inp):
    k = issued[0] + 1
    if a.marks:
        mark(2 * k - 1)
    dist.all_gather_into_tensor(out, inp)
    issued[0] = k
    if a.marks:
        mark(2 * k)


def watchdog():
    reported = False
    while True:
        time.sleep(1)
        late = time.time() - where['done_at']
        if late > a.stall_s and not reported:
            print('STALL rank %d: no step finished for %.1f s; in step %d (%d rows), gather %d%s' % (
                rank, late, where['step'] + 1, where['rows'], where['gather'],
                '; marks: %d gathers issued, this card: %s' % (issued[0], card_state()) if a.marks else ''),
                flush=True)
            faulthandler.dump_traceback(file=sys.stdout, all_threads=True)
            sys.stdout.flush()
            reported = True
        if reported and late > a.stall_s + 60:
            os._exit(3)


threading.Thread(target=watchdog, daemon=True).start()
log = open(a.out, 'a') if rank == 0 else None
end = time.time() + a.minutes * 60
steps = prompt_steps = gathers = checked = bad = 0
t_report = time.time()
extra = True
go, gos = torch.ones(1, device=dev, dtype=torch.int32), torch.empty(world, device=dev, dtype=torch.int32)
dist.barrier()
while True:
    if steps % 64 == 0:  # stop together: each rank reads its own clock, so a per-rank stop can mismatch collectives
        go.fill_(1 if time.time() < end else 0)
        dist.all_gather_into_tensor(gos, go)
        if int(gos.min()) == 0:
            if a.mismatch_test and rank == 1 and extra:
                extra = False   # one more step that rank 0 never joins
            else:
                break
    prompt = shared.random() < a.prompt_share
    rows = shared.randint(30, 832) if prompt else shared.randint(1, 6)
    sampled = shared.randint(1, 6)
    gap = shared.uniform(0.05, 0.3) if shared.random() < a.gap_share else 0.0
    where.update(step=steps, rows=rows, gather=-1)
    x, h = xs[:rows], xs[:rows]
    g = gs[:world * rows]
    for i in range(a.gathers):
        h = h @ w
        if own.random() < a.skew:
            for _ in range(own.randint(1, 4)):
                h = h @ w
        where['gather'] = i
        gather(g, x)
        h = (h + g[:rows]) * 0.5
    where['gather'] = a.gathers
    gather(gv[:world * sampled], lv[:sampled])
    if steps % 64 == 0:
        ok = torch.equal(g[rank * rows:(rank + 1) * rows], x)
        checked += 1
        bad += 0 if ok else 1
    torch.xpu.synchronize()
    steps += 1
    prompt_steps += prompt
    gathers += a.gathers + 1
    where['done_at'] = time.time()
    if gap:
        time.sleep(gap)
    if log and time.time() - t_report >= a.report_s:
        t_report = time.time()
        log.write(json.dumps({'t': round(t_report, 1), 'steps': steps, 'prompt_steps': prompt_steps, 'gathers': gathers,
                              'checked': checked, 'bad': bad}) + '\n')
        log.flush()
        print('XCCL-STRESS %d steps (%d prompt-size), %d gathers, bytes checks %d bad %d' % (
            steps, prompt_steps, gathers, checked, bad), flush=True)
dist.barrier()
if log:
    log.write(json.dumps({'t': round(time.time(), 1), 'steps': steps, 'prompt_steps': prompt_steps, 'gathers': gathers,
                          'checked': checked, 'bad': bad, 'done': True}) + '\n')
    print('XCCL-STRESS DONE %d steps (%d prompt-size), %d gathers, bytes checks %d bad %d' % (
        steps, prompt_steps, gathers, checked, bad), flush=True)
dist.destroy_process_group()
raise SystemExit(1 if bad else 0)
