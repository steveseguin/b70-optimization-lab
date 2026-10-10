#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Bind the client to completed138 seal and INNER plan, never envelope bytes."""
import hashlib
import json
import os
from pathlib import Path
import pprint
import sys
assert sys.executable == '/home/steve/.venvs/ltx25-baseline/bin/python'
assert os.getpriority(os.PRIO_PROCESS, 0) == 19 and os.environ.get('OMP_NUM_THREADS') == '2'
LANE = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_name('continuation138-tests')
seal = json.loads((OUT/'seal.json').read_bytes())
packet = Path(seal['packet'])
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(packet/'manifest.json') == seal['manifest_sha256']
manifest = json.loads((packet/'manifest.json').read_bytes())
plan = json.loads((packet/'resolution/stream-plan.json').read_bytes())
names = ('text_prefetch138', 'f32_scan137', 'allocator_release130', 'cone_memory131',
         'evidence_publication', 'run_storage', 'residency123', 'audio_residency132',
         'stream_contract', 'stream_receipts', 'qualification_gate', 'text_residency133')
modules = {}
for name in names:
    rel = 'resolution/components/'+name+'.py'
    modules[name] = sha(packet/rel)
    assert modules[name] == manifest['files'][rel]
ref = 'resolution/reference-frame-hashes.json'
assert sha(packet/ref) == manifest['files'][ref]
pins = dict(manifest_sha256=seal['manifest_sha256'], plan_sha256=plan['plan_sha256'],
            modules=modules, reference_sha256=sha(packet/ref))
assert pins['plan_sha256'] != sha(packet/'resolution/stream-plan.json')
client = LANE/'stream/ltx_continuation_client.py'
text = client.read_text()
marker = '\n# Packet138 pins are filled only from its completed seal.\n'
block = marker+'PACKETS[138] = dict('+pprint.pformat(pins, sort_dicts=False)+", dir=R / 'prepared-continuation-stream-138')\n"
if marker in text:
    start = text.index(marker)
    end = text.index('\n\ndef utc(', start)
    text = text[:start]+block+text[end:]
else:
    text = text.replace('\n\ndef utc(', block+'\n\ndef utc(', 1)
compile(text, str(client), 'exec')
client.write_text(text)
(OUT/'client-pins.json').write_text(json.dumps(pins, indent=2)+'\n')
print(json.dumps({k:v for k,v in pins.items() if k != 'modules'}, indent=2))
