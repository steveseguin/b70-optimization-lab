"""Retain positive and negative receipts from the unmodified smoke analyzer."""
import json
from pathlib import Path
import tempfile
import analyze
from test_first_request import FirstRequest
from build_engine import P,sha,save,limits

def main():
    limits()
    with tempfile.TemporaryDirectory(prefix='p58aib-first-request-') as tmp:
        folder=Path(tmp)
        FirstRequest().fixture(folder)
        complete=analyze.first_request(folder)
        (folder/'measure.jsonl').write_text('')
        try:
            analyze.first_request(folder)
        except ValueError as error:
            empty=dict(rejected=True,error=str(error))
        else:
            raise AssertionError('empty first-request stream accepted')
    save(P/'evidence/first-request-data-gate.json',dict(passed=True,
        device_executed=False,synthetic_only=True,analyzer_patched=False,
        complete=complete,empty=empty,wall_deadline_seconds=None,
        sources={name:sha(P/name) for name in
                 ('analyze.py','suite_driver.py','first_request_gate.py','test_first_request.py')}))

if __name__=='__main__':main()
