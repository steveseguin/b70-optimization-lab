import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('stream_subject', Path.cwd()/'scripts/bench-openai-long-context-suite.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class Response:
    def __init__(self, events): self.events = events
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def __iter__(self):
        yield b': ignored comment\n'
        for event in self.events: yield ('data: '+json.dumps(event)+'\n').encode()
        yield b'data: [DONE]\n'

def check(chunks, count):
    events = [{'choices':[{'token_ids':ids, 'delta':{'content':text}}]} for ids,text in chunks]
    events.append({'choices':[], 'usage':{'prompt_tokens':11, 'completion_tokens':count}})
    with patch.object(m.urllib.request, 'urlopen', return_value=Response(events)) as http:
        row = m.stream_chat('http://invalid.local', 'fixture', 'prompt', 8, 1, 17, {}, True)
    payload = json.loads(http.call_args.args[0].data)
    assert payload['return_token_ids'] is True
    return row

row = check([([13,21], 'hello'), ([34], ' world')], 3)
assert row.get('token_ids') == [13,21,34], 'STREAM_TOKEN_IDENTITY: preserve ordered streamed token IDs in each result'
expected = hashlib.sha256(b'[13,21,34]').hexdigest()
assert row['token_ids_complete'] is True and row['token_ids_sha256'] == expected
assert row['stream_token_id_count'] == 3 and row['text'] == 'hello world'
same = check([([13], 'hello'), ([21,34], ' world')], 3)
assert same['token_ids_sha256'] == expected, 'Chunk grouping must not change identity'
different = check([([13,22,34], 'hello world')], 3)
assert different['token_ids_sha256'] != expected, 'Equal text is not equal token identity'
for chunks,count in [([([13], 'x')], 2), ([([13], 'x')], None), ([(None, 'x')],1), ([([], '')],0)]:
    item = check(chunks,count)
    assert item['token_ids_complete'] is False
    if not item['token_ids']: assert item['token_ids_sha256'] is None
print('PASS: ordered token identity, chunk invariance, distinct IDs and incomplete/absent metadata')
