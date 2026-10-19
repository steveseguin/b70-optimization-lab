"""During a run check complete streams and exact tokens, never timing values."""
import json
from pathlib import Path
from demand_analyze import request,stream,require
def check(folder,expected):
    result=json.loads((folder/'result.json').read_text())
    generated=stream(folder/'timings.jsonl')
    request(result,generated,stream(folder/'prefill-timings.jsonl'),offline=False)
    require(result['tokens']==expected,'unchanged oracle tokens')
    require(all(type(r['token_id']) is int and type(r['generated_index']) is int for r in generated),'generated token field format')
    require([r['token_id'] for r in generated]==expected,'generated stream exact tokens')
    reset=json.loads((folder/'reset.json').read_text())
    require(reset.get('passed') is True and reset.get('cached_tokens')==0 and reset.get('allocation_ids_preserved') is True,'request reset failed')
    return True
def partial(out,manifest,checked=None,cap=128,final=False):
    import suite_driver as D
    if checked is None:checked=set()
    for entry in manifest['prompts']:
        folder=Path(out)/'run'/entry['prompt_id']
        if folder in checked:continue
        if not final and not (folder/'lookup-request-complete.json').exists():continue
        check(folder,D.CHECK.token_record(D.ORACLE/'results'/entry['prompt_id'])[:cap]);checked.add(folder)
    if final:require(len(checked)==len(manifest['prompts']),'missing completed request stream')
    return dict(passed=True,complete_exact_requests=len(checked),checks=['presence','format','exactness'],elapsed_time_verdict=False)
