"""Validate the smoke's own evolving output, then replay the complete reader."""
import json,math
from pathlib import Path
def partial(out,manifest):
    import suite_driver as D
    receipt=D.read(out/'receipt.json')
    D.require(receipt['window']=='WSCREEN' and receipt['gpu_count']==1,'driver output schema differs')
    counts=0;complete=0
    root=out/'run/S0'
    for entry in manifest['prompts']:
        request=root/entry['prompt_id'];timing=request/'timings.jsonl'
        if timing.exists():
            raw=timing.read_text();lines=raw.splitlines()
            if raw and not raw.endswith('\n'):lines=lines[:-1]
            for line in lines:
                row=json.loads(line)
                for name in ('prepare_major_faults','prepare_minor_faults','process_major_faults','prepare_ms'):
                    D.require(type(row[name]) in (int,float) and math.isfinite(row[name]) and row[name]>=0,'invalid lookup timing '+name)
                D.require(row['resident_lookups'] is True,'smoke did not use resident copies')
                counts+=1
        if (request/'lookup-request-complete.json').exists():
            # Marker is opened only after result and request receipt have closed.
            D.compare_request(request,D.ORACLE/'results'/entry['prompt_id'],entry,64,'none');complete+=1
    return dict(passed=True,device_result_pending=counts==0,driver_schema_checked=True,timing_rows_checked=counts,complete_exact_requests=complete,
                source='current smoke output, never a saved fixture',first_minute_startup_check=True)
