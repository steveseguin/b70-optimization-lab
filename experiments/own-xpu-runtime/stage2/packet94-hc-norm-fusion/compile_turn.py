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
   foreign_build=(comm in ('cmake','gmake','make','ninja') or (comm=='python3' and len(cmd)>2 and any(b'/packet58g-onecard/' in x for x in cmd[1:3])))
   if foreign_build or comm in ('icpx','icx','g++','cc1plus','clang++','clang','clang-21','clang-20','ld.lld','llvm-link','sycl-post-link','clang-offload-w'):
    result.append((int(p.name),comm))
  except (FileNotFoundError,PermissionError,ProcessLookupError):pass
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
  f.seek(0);f.truncate();f.write('packet90 pid='+str(os.getpid())+'\n');f.flush()
  yield
