"""Fail at the native exec boundary if a Python import leaked a resource cap."""
import resource,subprocess,os
KINDS=sorted({getattr(resource,n) for n in dir(resource) if n.startswith('RLIMIT_')})
def snapshot():return {str(k):list(resource.getrlimit(k)) for k in KINDS}
def check(baseline):
 assert resource.getrlimit(resource.RLIMIT_AS)==(resource.RLIM_INFINITY,resource.RLIM_INFINITY),'native launch refuses finite RLIMIT_AS'
 assert snapshot()==baseline,'resource limits changed before native exec'
def install(observer=None):
 baseline=snapshot();original=subprocess.Popen
 def guarded(command,*args,**kwargs):
  argv=list(map(str,command)) if not isinstance(command,str) else [command]
  if any('own-rt-iq3' in x for x in argv) or any('/build/' in x for x in argv[:4]) or '--authorized-device-window' in argv:
   check(baseline)
   if observer is not None:observer(argv,baseline)
  return original(command,*args,**kwargs)
 subprocess.Popen=guarded
 return baseline
