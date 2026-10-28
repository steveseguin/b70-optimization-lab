#!/usr/bin/env python3
"""Create new manifest copies with hash-bound actual prefill trace provenance.

Never changes native evidence, original manifests, counters or pair identities.
Run only after requests/dumps and native trace writers have completed.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path


def attach(original):
    original = original.resolve()
    spec = json.loads(original.read_text())
    if 'prefill_provenance' in spec:
        raise ValueError('original already declares prefill provenance')
    def ref(path):
        if path.is_symlink() or not path.is_file():
            raise ValueError('regular completed evidence file required')
        path = path.resolve()
        return dict(path=str(path), sha256=sha256(path.read_bytes()).hexdigest())
    provider = next(s for s in spec['stages'] if s['id']==0)
    native = (original.parent/provider['dump']).parent
    spec['prefill_provenance'] = dict(schema='ownrt.prefill-trace-provenance.v1',
        selected_plan=ref(original.parent/'selected-request-plan.json'),
        canonical_pairs=ref(original.parent/'canonical-pairs.json'),
        native_draft_rows=ref(native/'draft-rows.jsonl'),
        native_provider_batches=ref(native/'ring-draft-batches.jsonl'),
        provider_attestation=ref(original.parent/provider['quiescence']))
    for stage in spec['stages']:
        for key in ('dump','plan','metadata','quiescence','draft_state_set','provider_survival'):
            if key in stage:
                stage[key] = str((original.parent/stage[key]).resolve())
        stage['prefill_trace'] = ref(Path(stage['dump']).parent/'ring.jsonl')
    destination = original.with_name(original.stem+'.prefill-provenance.json')
    with destination.open('x') as stream:
        json.dump(spec,stream,indent=2,ensure_ascii=False)
        stream.write('\n')
    print(json.dumps(dict(original=str(original),original_sha256=sha256(original.read_bytes()).hexdigest(),
                         manifest=str(destination),manifest_sha256=sha256(destination.read_bytes()).hexdigest())))
    return destination


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifests',type=Path,nargs='+')
    for manifest in parser.parse_args().manifests:
        attach(manifest)
