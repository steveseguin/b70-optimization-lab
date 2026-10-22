"""Report-contract fixture generator (ops/rehearse_entry.py micro contract; CPU only).

Expands a fixture captured from the real CPU rehearsal (report_fixture_data.FIXTURES[kind]: the
worker's lifecycle-inputs.json, its sample stream, every leg's teardown receipt and the checkpoint
manifests the report reads) under OUTPUT/run, then applies one optional mutation the report must
catch. Writes only under OUTPUT.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def generate(output, fixture):
    kind = fixture['kind']
    from report_fixture_data import FIXTURES   # a .py module: the report sandbox reads repository Python sources only
    archive = FIXTURES[kind]
    run = Path(output) / 'run'
    for rel, text in archive['files'].items():
        path = run / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    mutation = fixture.get('mutation')
    if mutation == 'merged-token':
        x = json.loads((run / 'lifecycle-inputs.json').read_text())
        tokens = x['legs'][1]['requests']['resume']['tokens']
        tokens[0] = (tokens[0] + 1) % 16
        (run / 'lifecycle-inputs.json').write_text(json.dumps(x))
    elif mutation == 'sref-blob':
        path = run / 'checkpoints/sref/manifest.json'
        m = json.loads(path.read_text())
        b = m['ranks'][1]['blobs'][0]
        b['sha256'] = ('0' if b['sha256'][0] != '0' else '1') + b['sha256'][1:]
        path.write_text(json.dumps(m))
    elif mutation is not None:
        raise ValueError('unknown fixture mutation')
