"""CPU-only test entry: bound memory and refuse writes outside owned scratch."""
import os,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent

def main():
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 def permitted(path,fd=-1):
  if isinstance(path,int):return True
  path=Path(os.fsdecode(path))
  if not path.is_absolute() and isinstance(fd,int) and fd>=0:path=Path(os.readlink('/proc/self/fd/'+str(fd)))/path
  path=path.absolute()
  return path.is_relative_to(P) or path.is_relative_to('/tmp') or str(path)=='/dev/null'
 def audit(event,args):
  if event=='open':
   path,mode,flags=args
   if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC):
    if not permitted(path):raise PermissionError('packet114 test write outside scratch: '+str(path))
  elif event in ('os.remove','os.rmdir','os.mkdir','os.chmod','os.truncate'):
   if not permitted(args[0],args[-1] if event!='os.truncate' else -1):raise PermissionError('packet114 test mutation outside scratch: '+str(args[0]))
  elif event=='os.symlink':
   if not permitted(args[1],args[2]):raise PermissionError('packet114 symlink destination outside scratch')
  elif event in ('os.rename','os.link'):
   if not all(permitted(x) for x in args[:2]):raise PermissionError('packet114 test path outside scratch')
 sys.addaudithook(audit)
 suite=unittest.defaultTestLoader.discover(str(P),pattern='test_*.py')
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
