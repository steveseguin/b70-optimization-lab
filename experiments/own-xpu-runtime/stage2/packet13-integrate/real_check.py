"""Retain runtime-authority real-layer fixtures; never call the BLAS oracle a gate."""
import hashlib
import json
from pathlib import Path
import shutil

def retain(run, inputs, output, binary):
    run, inputs, output, binary = map(Path, (run, inputs, output, binary))
    output.mkdir(parents=True, exist_ok=True)
    receipt=json.loads((run/'receipt.json').read_text())
    assert receipt['passed'] and not receipt['device_executed'] and receipt['oracle_exact'] is None
    fixture=run/'step1/layer-00.bf16'
    assert fixture.stat().st_size==20480
    for source,name in [(fixture,'layer-00.bf16'),(run/'step1/layers.jsonl','layers.jsonl'),
                        (run/'receipt.json','run.json'),(run/'memory.json','memory.json')]:
        shutil.copyfile(source,output/name)
    timing=[json.loads(line) for line in (run/'timings.jsonl').read_text().splitlines()]
    tokens=[r for r in timing if r['kind']=='token']
    expected=json.loads((inputs/'input.json').read_text())
    assert [r['input_token'] for r in tokens]==expected['tokens']
    r=dict(schema='own-runtime.iq3.packet13.real-layer.v1',completed=True,
           device_executed=False,oracle_compared=False,real_model_qualified=False,
           comparison_status='pending oracle rebase onto runtime arithmetic',
           arithmetic=receipt['arithmetic'],prompt_tokens=len(tokens),
           shape=[1,4,2560],dtype='BF16 little-endian',
           sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
           binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
           input_sha256=hashlib.sha256((inputs/'tokens.txt').read_bytes()).hexdigest(),
           cpu_wall_ms=sum(t['wall_ms'] for t in tokens),
           device_timings_available=False)
    (output/'receipt.json').write_text(json.dumps(r,indent=2)+'\n')
    (output/'token-timings.json').write_text(json.dumps(tokens,indent=2)+'\n')
    return r
