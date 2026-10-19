"""Measured packet-local peak; no legacy whole-chain reservation."""
import shutil
from pathlib import Path
P=Path(__file__).resolve().parent
FREE_FLOOR=25_000_000_000

def admit(extra=0,**unused):
 free=shutil.disk_usage(P).free
 if free-extra<FREE_FLOOR:raise RuntimeError('device storage floor 25 GB')
 return dict(free_bytes=free,requested_bytes=extra,floor_bytes=FREE_FLOOR)
def state_write_bytes(context):
 if context!=4096:raise ValueError('only registered4096 capacity')
 return 240_000_000 # measured229,176,400 bytes; unchanged context/layout

def request_write_bytes(retained_steps):
 if retained_steps!=0:raise ValueError('performance path retains no layer fixtures')
 return 8_000_000
