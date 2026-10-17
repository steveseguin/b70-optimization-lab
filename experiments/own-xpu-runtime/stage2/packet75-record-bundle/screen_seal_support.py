"""Seal CPU mock results without running any model, compiling, or touching devices."""
from pathlib import Path
import json
from storage import digest
P=Path(__file__).resolve().parent
ROOT=P.parents[3]

def wrapper_seal():
    target=P/'screen/wrapper-seal.json'
    if target.exists():raise ValueError('wrapper already sealed')
    proof=json.loads((P/'evidence/lease-tests.json').read_text())
    assert proof['passed'] and proof['device_executed'] is False
    files=[*sorted((P/'screen').glob('*.py')),P/'screen/placements.json',P/'evidence/lease-tests.log',P/'evidence/lease-tests.json']
    target.write_text(json.dumps(dict(passed=True,device_executed=False,cpu_model_executed=False,
        schema='packet70.screen-wrapper.v1',sources={str(f.relative_to(ROOT)):digest(f) for f in files}),indent=2)+'\n')
