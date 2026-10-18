"""Serial compiler turn; wait for foreign compiler processes without signalling."""
import contextlib,fcntl,os,time
from pathlib import Path
LOCK=Path('/tmp/own-xpu-runtime-cpu-compile.lock')
def active():
 result=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   comm=(p/'comm').read_text().strip()
   cmd=(p/'cmdline').read_bytes().split(b'\0')
   foreign_build=(comm in ('cmake','gmake','make','ninja'))
   if foreign_build or comm in ('icpx','icx','g++','cc1plus','clang++','clang','clang-21','clang-20','ld.lld','llvm-link','sycl-post-link','clang-offload-w'):
    result.append((int(p.name),comm))
  except (FileNotFoundError,PermissionError,ProcessLookupError):pass
 # Coordinator 2026-10-18: device runs are not compilers. Wait instead while a whole-host
 # window holds the host (hold-lane-B or a whole-host lane marker), so timing and host-RAM
 # admission are never disturbed by a compile.
 C=Path('/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1')
 try:
  if (C/'hold-lane-B').exists():result.append((-1,'hold-lane-B'))
  for m in C.glob('active-lane-*.json'):
   if b'whole-host' in m.read_bytes():result.append((-1,m.name))
 except OSError:pass
 return result
@contextlib.contextmanager
def turn():
 with LOCK.open('a+') as f:
  fcntl.flock(f,fcntl.LOCK_EX)
  end=time.monotonic()+3600
  while active():
   print('Waiting for compiler turn:',active(),flush=True)
   if time.monotonic()>end:raise TimeoutError('compiler turn deadline')
   time.sleep(10)
  f.seek(0);f.truncate();f.write('packet94 pid='+str(os.getpid())+'\n');f.flush()
  from build_engine import limits
  limits()
  yield
