"""Incremental stream format and oracle checks; no wall-clock proof timer."""
import json
from views import bracket
from split_analyze import check
_STATES={}
def partial(out,manifest,candidate='resident'):
    import suite_driver as D
    receipt=D.read(out/'receipt.json')
    D.require(receipt['window']=='WSCREEN' and receipt['gpu_count']==1,'driver schema')
    state=_STATES.setdefault(str(out),dict(offsets={},completed=set(),rows=0))
    for label,arm in bracket(candidate):
        for entry in manifest['prompts']:
            root=out/'run'/label/entry['prompt_id'];timing=root/'timings.jsonl'
            if timing.exists():
                offset=state['offsets'].get(str(timing),0)
                D.require(timing.stat().st_size>=offset,'timing stream truncated')
                with timing.open() as stream:
                    stream.seek(offset)
                    while True:
                        start=stream.tell();line=stream.readline()
                        if not line or not line.endswith('\n'):stream.seek(start);break
                        check(json.loads(line),arm);state['rows']+=1
                    state['offsets'][str(timing)]=stream.tell()
            if str(root) not in state['completed'] and (root/'lookup-request-complete.json').exists():
                D.compare_request(root,D.ORACLE/'results'/entry['prompt_id'],entry,64 if candidate=='smoke' else 32,'none')
                state['completed'].add(str(root))
    return dict(passed=True,device_result_pending=state['rows']==0,timing_rows_checked=state['rows'],complete_exact_requests=len(state['completed']),checks='stream presence/format and oracle exactness only')
