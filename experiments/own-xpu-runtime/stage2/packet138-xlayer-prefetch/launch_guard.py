"""Use actual inherited rlimits at each native boundary; imports never set caps."""
from types import SimpleNamespace
from exec_limits import check

def install_native_guard(pipeline):
 original=pipeline.subprocess.Popen
 def guarded(argv,*args,**kwargs):
  check()
  assert kwargs.get('env') is not None,'closed native environment required'
  return original(argv,*args,**kwargs)
 pipeline.subprocess=SimpleNamespace(**{**vars(pipeline.subprocess),'Popen':guarded})
