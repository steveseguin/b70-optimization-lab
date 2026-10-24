"""Exact remaining dump payload from acknowledged full-suite capture events."""
T=221743168;D=9699332;PER=T+D;CAP=26;META=128*1024**2;EXTERNAL_FLOOR=2*1024**3;ROOT_FLOOR=27000000000;ROOT_CACHE=128*1024**2

def need(v,m):
 if not v:raise ValueError(m)
class Budget:
 def __init__(self):self.remaining=27*PER;self.resets=0;self.target_dumped=False;self.dumps=0;self.repeats=0;self.finished=False;self.events=[]
 def credit(self,event,n):
  need(type(n)is int and 0<=n<=self.remaining,'bounded capture credit');self.remaining-=n;self.events.append(dict(event=event,credited_bytes=n,remaining_payload_bytes=self.remaining))
 def reset(self):
  need(not self.finished and self.resets<CAP,'reset lifecycle')
  if self.resets>=3:need(self.target_dumped and self.repeats==0,'previous measured target must be acknowledged')
  n=PER if self.resets<3 else D
  self.credit('reset-'+str(self.resets+1),n);self.resets+=1;self.target_dumped=False
 def dump(self):
  need(not self.finished and 3<=self.resets<=CAP,'measured target dump only')
  if self.target_dumped:
   need(self.resets==CAP and self.dumps==24 and self.repeats==0,'only one final explicit repeat');self.credit('final-repeat',0);self.repeats+=1
  else:self.credit('target-'+str(self.resets),T);self.target_dumped=True;self.dumps+=1
 def finish(self):
  need(not self.finished and self.resets==CAP and self.dumps==24 and self.repeats==1 and self.target_dumped and self.remaining==D,'final acknowledged target before FINISH')
  self.credit('finish',D);self.finished=True
 def report(self):return dict(resets=self.resets,target_dumps=self.dumps,final_repeats=self.repeats,finished=self.finished,remaining_payload_bytes=self.remaining,metadata_reserve_bytes=META,external_floor_bytes=EXTERNAL_FLOOR,events=list(self.events))
def check_free(root_free,external_free,budget):
 need(root_free>=ROOT_FLOOR+ROOT_CACHE,'root cache forecast/floor')
 need(external_free>=EXTERNAL_FLOOR+META+budget.remaining,'remaining acknowledged capture forecast/floor')
 return budget.report()
