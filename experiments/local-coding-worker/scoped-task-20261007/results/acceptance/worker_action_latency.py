import copy
import importlib.util
from pathlib import Path
s = importlib.util.spec_from_file_location('target_collector', Path.cwd() / 'worker/collect_overnight.py')
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
base = {'token_ids':[201,202,203], 'token_offsets_s':[0.2,0.45,0.7], 'http_ttft_s':0.2,
        'decode_stream_proxy_tokens_s':4.0, 'elapsed_s':0.8, 'action_format_valid':True, 'action_ready_s':1.0}
for ready in (0.8, 1.0, 19.0):
 r=copy.deepcopy(base);r['action_ready_s']=ready;m.check_timing(r, b'', False)
r=copy.deepcopy(base);r['action_format_valid']=False;del r['action_ready_s'];m.check_timing(r,b'',False)
invalid=[]
for ready in (0.79, -1, float('nan'), float('inf'), None, '1.0', True):
 r=copy.deepcopy(base);r['action_ready_s']=ready;invalid.append(r)
r=copy.deepcopy(base);del r['action_ready_s'];invalid.append(r)
for valid in (None, 1, 'true'):
 r=copy.deepcopy(base);r['action_format_valid']=valid;invalid.append(r)
r=copy.deepcopy(base);del r['action_format_valid'];invalid.append(r)
r=copy.deepcopy(base);r['action_format_valid']=False;invalid.append(r)
for index,r in enumerate(invalid):
 try:m.check_timing(r,b'',False)
 except m.IntegrityError:pass
 else:raise AssertionError(f'ACTION_LATENCY_FAILURE: invalid completed-action timing accepted, case {index}')
# Existing token-arrival validation must still reject unrelated bad evidence.
r=copy.deepcopy(base);r['token_offsets_s']=[0.2,0.7,0.45]
try:m.check_timing(r,b'',False)
except m.IntegrityError:pass
else:raise AssertionError('Unordered token arrivals accepted')
print('PASS: valid and invalid action-ready timings; arrival-time regression')
