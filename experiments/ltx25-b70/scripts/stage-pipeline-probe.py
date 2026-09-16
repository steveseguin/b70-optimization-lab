"""Does inter-clip pipeline parallelism actually give ~4x on four B70s?

The sampler is 11 diffusion forwards over 48 blocks. Split the blocks into four
card-stages of 12; a clip visits stages 0,1,2,3 for each forward, 44 visits in
all. Diffusion is sequential within a clip but not between clips, so clip N+1
can occupy stage 0 while clip N is in stage 1.

This models a stage-visit with real GEMM work of the measured size (12 blocks of
a 737.5 MB block, 11 forwards -> ~46 ms per visit) and pushes clips through.
"""
import threading, time, torch

CARDS = 4
FORWARDS = 11
CLIPS = 8
TARGET_VISIT_MS = 46.0

# Size a per-stage workload to ~46 ms of real GEMM on each card.
work = {}
for d in range(CARDS):
    torch.xpu.set_device(d)
    a = torch.randn(256, 4096, dtype=torch.bfloat16, device=f'xpu:{d}')
    w = torch.randn(4096, 16384, dtype=torch.bfloat16, device=f'xpu:{d}')
    for _ in range(3):
        a @ w
    torch.xpu.synchronize(d)
    t = time.perf_counter()
    for _ in range(20):
        a @ w
    torch.xpu.synchronize(d)
    one = (time.perf_counter() - t) / 20 * 1e3
    work[d] = (a, w, max(1, int(round(TARGET_VISIT_MS / one))))
print('per-GEMM %.3f ms; %d GEMMs per stage-visit -> ~%.0f ms' %
      (one, work[0][2], one * work[0][2]))

def visit(d):
    a, w, n = work[d]
    with torch.xpu.device(d):
        for _ in range(n):
            a @ w
        torch.xpu.synchronize(d)

# --- serial: one clip at a time through all four stages -------------------
t = time.perf_counter()
for _ in range(2):
    for _f in range(FORWARDS):
        for d in range(CARDS):
            visit(d)
serial_per_clip = (time.perf_counter() - t) / 2
print('serial:    %.3f s per clip' % serial_per_clip)

# --- pipelined: one worker per stage, clips flow through ------------------
locks = [threading.Lock() for _ in range(CARDS)]
done = threading.Semaphore(0)

def clip_thread(idx):
    for _f in range(FORWARDS):
        for d in range(CARDS):
            with locks[d]:          # a stage serves one clip at a time
                visit(d)
    done.release()

t = time.perf_counter()
threads = [threading.Thread(target=clip_thread, args=(i,)) for i in range(CLIPS)]
for th in threads: th.start()
for th in threads: th.join()
pipelined_total = time.perf_counter() - t
print('pipelined: %.3f s for %d clips = %.3f s per clip' %
      (pipelined_total, CLIPS, pipelined_total / CLIPS))
print('speedup %.2fx  (ideal %dx)' % (serial_per_clip / (pipelined_total / CLIPS), CARDS))
