#!/usr/bin/env python3
"""CPU check: replays share, captures exclude, and a capture waits for in-flight replays."""
import sys, threading, time, types
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
SRC = Path('/home/steve/src/ComfyUI-ltx25-baseline/comfy/ldm/lightricks/av_model.py')
for name in ('comfy', 'comfy.ldm', 'comfy.ldm.lightricks', 'comfy.ldm.lightricks.av_model', 'comfy.patcher_extension', 'ltx_layer_shard'):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules['comfy.ldm.lightricks.av_model'].__file__ = str(SRC)
for n_ in ('CallbacksMP', 'WrappersMP'): setattr(sys.modules['comfy.patcher_extension'], n_, object)
for n_ in ('CACHE_KEY', 'KEY', 'LTXLayerShardedPatcher', '_BlockRoute', '_forward_transfers', '_verify_placement', '_move'):
    setattr(sys.modules['ltx_layer_shard'], n_, object)
import ltx_graph_capture as c
lock = c.CaptureReplayLock()
log = []
def reader(i):
    lock.acquire_shared(); log.append(('r-in', i)); time.sleep(0.05); log.append(('r-out', i)); lock.release_shared()
def writer():
    time.sleep(0.01); lock.acquire_exclusive(); log.append(('w-in',)); time.sleep(0.02); log.append(('w-out',)); lock.release_exclusive()
ts = [threading.Thread(target=reader, args=(i,)) for i in range(2)] + [threading.Thread(target=writer)]
for t in ts: t.start()
for t in ts: t.join()
# both readers overlapped; the writer entered only after both readers left; nothing entered during the writer
i_w_in = log.index(('w-in',)); i_w_out = log.index(('w-out',))
assert all(('r-out', i) in log[:i_w_in] for i in range(2)), log
assert log[i_w_in + 1] == ('w-out',), log
assert log.index(('r-in', 1)) < log.index(('r-out', 0)) or log.index(('r-in', 0)) < log.index(('r-out', 1)), log
assert lock.captures == 1
# thread-local pipelined flag
assert not c.pipelined_enabled(); c.set_pipelined(True); assert c.pipelined_enabled()
seen = []
threading.Thread(target=lambda: seen.append(c.pipelined_enabled())).start(); time.sleep(0.05)
assert seen == [False]; c.set_pipelined(False)
print('capture/replay lock and thread-local pipelined flag: ok')
