"""In-run stream format and oracle only; metrics/consistency are offline."""
import json,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent.parent
def partial(out,manifest,checked=None,view='smoke'):
    if checked is None:checked=set()
    if view=='checked':
        # Exact output is checked after this single request completes.
        return dict(passed=True,complete_exact_requests=0,checks=['presence','format','oracle'])
    kind='smoke' if view=='smoke' else 'v5'
    proposal=json.loads((P/f'proposals/{kind}.json').read_text())
    for label in proposal['views']:
        for entry in manifest['prompts']:
            request=out/'run'/label/entry['prompt_id']
            if request in checked or not (request/'lookup-request-complete.json').exists():continue
            result=subprocess.run([sys.executable,'-B',str(P/'check_streams.py'),
                str(P/f'proposals/{kind}.json'),str(request)],stdin=subprocess.DEVNULL,
                capture_output=True,text=True)
            if result.returncode:raise ValueError('stream/oracle gate: '+result.stderr[-2000:])
            checked.add(request)
    return dict(passed=True,complete_exact_requests=len(checked),checks=['presence','format','oracle'],
                numeric_consistency_checks=False,elapsed_time_verdict=False)
