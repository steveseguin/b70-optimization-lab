#!/usr/bin/env python3
"""CPU test: ClipOwnership's encode/observation bookkeeping is per thread, so two encode
workers can run the observe -> encode -> consume protocol concurrently without seeing
each other's state (server 77b: 'Previous embedding observations were not consumed')."""
import importlib.util, sys, threading, types
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
# Real torch (venv) and real ComfyUI (a prepared packet's source tree) satisfy the imports on CPU.
import os
PACKET = Path(os.environ.get('LTX_PACKET', '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-graph-capture-77'))
sys.path[:0] = [str(PACKET / 'source'), str(PACKET / 'source/scripts')]
spec = importlib.util.spec_from_file_location('host_embedding_clip_threadsafe', HERE / 'host_embedding_clip_threadsafe.py')
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except Exception as error:  # noqa: BLE001
    print('import needs more stubs:', type(error).__name__, error); raise
group = mod.ClipOwnership.__new__(mod.ClipOwnership)
group._encode_state = threading.local()
group.observation_limit = 4
results = {}
barrier = threading.Barrier(2)
def worker(name):
    try:
        for _ in range(50):
            assert group.encodes == group.last_checked_encode and not group.observation_active and not group.embedding_observations
            group.observation_active = True
            barrier.wait(timeout=5)              # both threads are mid-encode at once
            group.embedding_observations.append({'ordinal': 1, 'thread': name})
            assert all(row['thread'] == name for row in group.embedding_observations)
            group.encodes += 1
            group.observation_active = False
            group.consume_observations()
            barrier.wait(timeout=5)
        results[name] = group.encodes
    except Exception as error:  # noqa: BLE001
        results[name] = repr(error)
threads = [threading.Thread(target=worker, args=(n,), name=f'ltx-encode-{n}') for n in ('a', 'b')]
for t in threads: t.start()
for t in threads: t.join()
ok = results == {'a': 50, 'b': 50} and group.encodes == 0   # main thread never encoded
print('per-thread results:', results, 'main thread encodes:', group.encodes)
print('ALL CASES AS EXPECTED:', ok)
