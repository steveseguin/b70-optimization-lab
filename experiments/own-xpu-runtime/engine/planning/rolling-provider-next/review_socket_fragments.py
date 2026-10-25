import sys,socket,struct,json
from pathlib import Path
_here=Path(__file__).resolve().parent
sys.path[:0]=[str(_here),str(_here.parent)]
import test_socket_bridge as test
bridge=test.bridge
original_pair=socket.socketpair
original_drive=bridge.drive
state={}
class Fragment:
 def __init__(self,sock):self.sock=sock
 def __getattr__(self,name):return getattr(self.sock,name)
 def fileno(self):return self.sock.fileno()
 def send(self,data,*args,**kwargs):
  if len(data)==test.base.REQUEST.size and struct.unpack('<i',data[:4])[0]==state.get('cancel_op'):
   state['cancel']=True
   if state.get('block_before_send') and not state.get('blocked'):
    state['blocked']=True
    raise BlockingIOError()
  state['writes']=state.get('writes',0)+1
  return self.sock.send(data[:3],*args,**kwargs)
 def recv(self,n,*args,**kwargs):return self.sock.recv(min(n,3),*args,**kwargs)
def pair(*args,**kwargs):
 client,peer=original_pair(*args,**kwargs);return Fragment(client),peer
def drive(*args,**kwargs):
 kwargs['stop_requested']=lambda:state.get('cancel',False)
 return original_drive(*args,**kwargs)
socket.socketpair=pair;bridge.drive=drive
cases=[]
try:
 for count in (2,4,6):
  for cancel_op,block in [(None,False)]+[(op,b) for op in (24,25,27) for b in (False,True)]:
   state.clear();state['cancel_op']=cancel_op;state['block_before_send']=block
   result,owners=test.exercise(count,first_options=dict(miss_first=(4,9),miss_second=(6,11),provider_delay=.0004))
   assert result['cancelled']==(cancel_op is not None)
   assert all(not owner['worker'].ring.pending for owner in owners)
   assert all(owner['worker'].ring.committed==result['input_position'] for owner in owners)
   if cancel_op is None:
    inputs,outputs=test.reference([3,5,8,11],16,(96,));assert result['output_ids']==outputs
   cases.append(dict(stages=count,cancel_on_opcode=cancel_op,cancel_before_any_command_byte=block,writes=state['writes'],provider_pairs=result['provider_pairs'],input_position=result['input_position'],cancelled=result['cancelled']))
finally:socket.socketpair=original_pair;bridge.drive=original_drive
print(json.dumps(dict(schema='ownrt.rolling-socket-partial-review.v1',passed=len(cases),cases=cases),indent=2))
