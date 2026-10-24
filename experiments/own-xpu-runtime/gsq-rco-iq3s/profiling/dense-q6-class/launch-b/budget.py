"""Remaining payload forecast from acknowledged capture lifecycle, never files."""
T=221743168;D=9699332;META=128*1024**2;EXTERNAL_FLOOR=2*1024**3;ROOT_FLOOR=27000000000;ROOT_CACHE=128*1024**2
EVENTS=('initial_reset','warmup_target_dump','second_reset','measured_target_dump','finish')
REMAINING=(3*(T+D),2*(T+D),T+2*D,T+D,D,0)
def need(v,m):
 if not v:raise ValueError(m)
class Budget:
 def __init__(self):self.stage=0;self.acknowledged=[]
 def advance(self,event):
  need(self.stage<len(EVENTS) and EVENTS[self.stage]==event,'capture acknowledgement order');self.acknowledged.append(event);self.stage+=1
 def report(self):return dict(stage=self.stage,acknowledged=list(self.acknowledged),remaining_payload_bytes=REMAINING[self.stage],metadata_reserve_bytes=META,external_floor_bytes=EXTERNAL_FLOOR)
def check_free(root_free,external_free,budget):
 need(type(budget.stage)is int and 0<=budget.stage<=5,'capture stage')
 need(root_free>=ROOT_FLOOR+ROOT_CACHE,'root cache forecast/floor')
 need(external_free>=EXTERNAL_FLOOR+META+REMAINING[budget.stage],'remaining external evidence forecast/floor')
 return budget.report()
