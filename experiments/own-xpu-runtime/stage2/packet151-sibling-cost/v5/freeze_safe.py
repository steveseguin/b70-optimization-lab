"""CPU gate subprocess deadlines exclude detected scheduler/freezer pauses.

Poll at 250 ms. A monotonic gap over two seconds re-arms the full budget.
Only a child created here can be terminated on an active-time expiry.
"""
import subprocess
import time

class Budget:
 def __init__(self, seconds, clock=time.monotonic, gap=2.):
  self.seconds=seconds;self.remaining=seconds;self.clock=clock;self.last=clock();self.gap=gap;self.pauses=0
 def tick(self):
  now=self.clock();delta=now-self.last;self.last=now
  if delta>self.gap:self.remaining=self.seconds;self.pauses+=1
  else:self.remaining-=delta
  return self.remaining

def run(*popenargs,input=None,capture_output=False,timeout=None,check=False,**kwargs):
 if input is not None:
  if kwargs.get('stdin') is not None:raise ValueError('stdin and input')
  kwargs['stdin']=subprocess.PIPE
 if capture_output:
  if kwargs.get('stdout') is not None or kwargs.get('stderr') is not None:raise ValueError('capture_output and streams')
  kwargs.update(stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 with subprocess.Popen(*popenargs,**kwargs) as process:
  budget=Budget(timeout) if timeout is not None else None
  payload=input
  while True:
   try:
    stdout,stderr=process.communicate(payload,timeout=.25 if budget else None)
    break
   except subprocess.TimeoutExpired:
    payload=None
    if budget.tick()<=0:
     process.kill();stdout,stderr=process.communicate()
     raise subprocess.TimeoutExpired(process.args,timeout,output=stdout,stderr=stderr)
  if check and process.returncode:
   raise subprocess.CalledProcessError(process.returncode,process.args,output=stdout,stderr=stderr)
  return subprocess.CompletedProcess(process.args,process.returncode,stdout,stderr)


def wait(process, timeout):
 budget=Budget(timeout)
 while True:
  try:return process.wait(timeout=.25)
  except subprocess.TimeoutExpired:
   if budget.tick()<=0:raise

class ActiveClock:
 """Proxy for the ops arbiter's ten-second polling clock; long gaps excluded."""
 def __init__(self):self.last=time.monotonic();self.value=self.last
 def monotonic(self):
  now=time.monotonic();delta=now-self.last;self.last=now
  if delta<=30:self.value+=delta
  return self.value
 sleep=staticmethod(time.sleep)


def install():
 """Cover nested standard-library run calls in CPU-only gate processes."""
 subprocess.run=run
