"""Four capture groups, credit only successful RESET/DUMP/FINISH acknowledgements."""
T=310364224;D=9699332;META=128<<20;EXTERNAL_FLOOR=2<<30;ROOT_FLOOR=27000000000;ROOT_CACHE=128<<20;INITIAL_EXTRA=128<<20
EVENTS=('reset_00','reset_01','reset_02','last_dump','finish')
REMAINING=(4*(T+D),3*(T+D),2*(T+D),T+D,D,0)
def need(v,m):
 if not v:raise ValueError(m)
class Budget:
 def __init__(self):self.stage=0;self.acknowledged=[]
 def advance(self,event):
  need(self.stage<len(EVENTS) and event==EVENTS[self.stage],'capture acknowledgement order');self.acknowledged.append(event);self.stage+=1
 def report(self):return dict(stage=self.stage,acknowledged=list(self.acknowledged),remaining_payload_bytes=REMAINING[self.stage],metadata_reserve_bytes=META,external_floor_bytes=EXTERNAL_FLOOR)
def check_free(root_free,external_free,budget,initial=False):
 need(type(budget.stage)is int and 0<=budget.stage<=5,'capture stage')
 need(root_free>=ROOT_FLOOR+ROOT_CACHE+(INITIAL_EXTRA if initial else 0),'root cache forecast/floor')
 need(external_free>=EXTERNAL_FLOOR+META+REMAINING[budget.stage]+(INITIAL_EXTRA if initial else 0),'remaining external evidence forecast/floor')
 return budget.report()
