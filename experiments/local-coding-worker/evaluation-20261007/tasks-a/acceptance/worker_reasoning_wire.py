import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
s=importlib.util.spec_from_file_location('target_model',Path.cwd()/'worker/model.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Captured(Exception):pass
class FormatError(Exception):pass
for name in ('minisweagent','minisweagent.models','minisweagent.models.utils','minisweagent.models.utils.actions_text','minisweagent.exceptions'):
 sys.modules[name]=types.ModuleType(name)
sys.modules['minisweagent.models.utils.actions_text'].parse_regex_actions=lambda *a,**kw:[]
sys.modules['minisweagent.exceptions'].FormatError=FormatError
history=[{'role':'system','content':'Work carefully.'},{'role':'assistant','content':'Prior answer', 'reasoning_content':'Retained private working state.'},
         {'role':'user','content':'Continue.'},{'role':'assistant','content':'Another answer'}]
for thinking in (True,False):
 with tempfile.TemporaryDirectory() as tmp:
  model=m.LocalModel.__new__(m.LocalModel)
  model.out=Path(tmp);model.calls=[];model.thinking=thinking;model.model='offline-fixture';model.base='http://127.0.0.1:18124'
  model.template_kwargs={'enable_thinking':thinking};model.max_input=1000;model.max_output=30;model.sampling={'temperature':0}
  captured={}
  def fetch(path,payload=None):
   if path=='/tokenize':captured['tokenize']=payload;return io.BytesIO(b'{"count": 100}')
   assert path=='/metrics';return io.BytesIO(b'')
  def request(base,payload,*args,**kwargs):captured['generation']=payload;raise Captured()
  model.fetch=fetch;model.opener=types.SimpleNamespace(open=lambda *a,**kw:None)
  model.wire=types.SimpleNamespace(write_json=lambda *a:None,request_one=request)
  model.thinking_wire=types.SimpleNamespace(request_one=request)
  try:model.query(history)
  except Captured:pass
  assert captured['tokenize']['messages']==captured['generation']['messages'], 'Routes received different histories'
  messages=captured['tokenize']['messages']
  assert [x['content'] for x in messages]==[x['content'] for x in history], 'Visible history changed'
  if thinking:
   assert messages[1].get('reasoning')=='Retained private working state.', 'REASONING_WIRE_FAILURE: tokenizer must receive canonical assistant reasoning'
   assert messages[3].get('reasoning')=='', 'Absent assistant reasoning must remain explicitly empty'
   assert all('reasoning_content' not in x for x in messages), 'Legacy-only reasoning alias on wire'
  else:assert all('reasoning' not in x and 'reasoning_content' not in x for x in messages), 'Nonthinking behavior changed'
assert history[1]['reasoning_content']=='Retained private working state.', 'Caller history mutated'
print('PASS: tokenizer/generation preserve canonical reasoning and nonthinking history')
