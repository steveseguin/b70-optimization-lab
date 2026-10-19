"""First-completed-request data proof: no elapsed-time verdict or launcher."""
import argparse,json
from pathlib import Path
from prepare import P
from analyze import request,stream,demand_stream,require
def check(proposal,folder):
    result=json.loads((folder/'result.json').read_text())
    generated=stream(folder/'timings.jsonl');prefill=stream(folder/'prefill-timings.jsonl')
    request(result,generated,prefill,offline=False)
    cap=proposal['tokens_per_prompt'];require(result['requested_max_new']==cap,'response cap')
    expected=list(map(int,(P/f'inputs/{folder.name}/oracle-{cap}.txt').read_text().split()))
    require(result['tokens']==expected,'unchanged oracle tokens')
    if proposal['detailed_events']:
        demand_stream(stream(folder/'demand-events.jsonl'),proposal['job_name'],len(prefill)+cap,offline=False)
    return dict(passed=True,checks=['presence','format','exactness'],elapsed_time_verdict=False)
def main():
    p=argparse.ArgumentParser();p.add_argument('proposal',type=Path);p.add_argument('request',type=Path);a=p.parse_args()
    print(json.dumps(check(json.loads(a.proposal.read_text()),a.request)))
if __name__=='__main__':main()
