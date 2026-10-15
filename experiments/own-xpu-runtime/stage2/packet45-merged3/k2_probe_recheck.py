"""Recheck the current analyzer against retained mini receipts without rerunning arithmetic."""
import base64,gzip,json
from pathlib import Path
from storage import verify_archive,digest
from k2_probe_analyze import samples,summarize,forecast
P=Path(__file__).resolve().parent;E=P/'evidence/k2-probe'
def members(path):
    verify_archive(path);files={};current=None;raw=bytearray()
    for line in gzip.open(path,'rt'):
        row=json.loads(line)
        if row.get('kind')=='file':current=row;raw=bytearray()
        elif row.get('kind')=='chunk':raw.extend(base64.b64decode(row['base64']))
        elif row.get('kind')=='end' and current['retained']:files[current['path']]=bytes(raw)
    return files

def main():
    mini=json.loads((E/'mini-gates.json').read_text());suite=json.loads((E/'mini-suite-gates.json').read_text())
    refs=[r['archive'] for r in mini['rows'] if r['probe']]+[suite['archive']];rows=[]
    for ref in refs:
        path=P/ref['path'];assert digest(path)==ref['sha256'];files=members(path)
        for name,raw in files.items():
            if not name.endswith('/receipt.json'):continue
            receipt=json.loads(raw)
            if not receipt.get('mtp_k2_probe') or 'tokens' not in receipt:continue
            if '/warmup/' in name:continue
            log=str(Path(name).parent/'rank1/mtp-k2-probe.jsonl')
            if log not in files:continue
            probes=[json.loads(line) for line in files[log].splitlines()]
            actual,censored=samples(receipt,probes);stats=summarize(actual)
            rows.append(dict(request=name,samples=len(actual),censored=censored,stats=stats,forecast=forecast(stats)))
    assert len(rows)==6 and sum(r['samples'] for r in rows)==30
    result=dict(passed=True,mini_only=True,device_executed=False,requests=6,samples=30,rows=rows,
        sources={n:digest(P/n) for n in ('k2_probe_analyze.py','k2_probe_recheck.py')},archives=refs)
    (E/'analyzer-recheck.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,requests=6,samples=30)))
if __name__=='__main__':main()
