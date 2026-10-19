"""Recheck exact fresh smoke and real device streams before census launch."""
import argparse
import json
from pathlib import Path
import analyze
import coordinator_gate as C
P = Path(__file__).resolve().parent

def verify():
    import window as W
    import queue_runner as Q
    import suite_driver as D
    W.build_gate()
    job, = C.proposal_jobs()
    root = Path(C.identity(job)[2])
    queue = analyze.read(root/'queue.json')
    W.require(queue.get('passed') is True and queue.get('completed') == list(Q.ORDER)
              and queue.get('arm') == 'smoke', 'fresh complete smoke required')
    for stage in Q.ORDER:
        receipt = Q.verify_success(stage, root, 0, 0)
        W.require(receipt['build_receipt_sha256'] == W.sha(P/'build-receipt.json'), 'smoke build differs')
        W.verify_files(root/stage, receipt['native_files'])
        for leaf in ('kernel-before.jsonl', 'kernel-window.jsonl'):
            W.require(not W.S.FAULT.search((root/stage/leaf).read_text()), 'smoke kernel fault')
    analyze.native_closure(root/'WSCREEN', receipt)
    summary = D.summarize_bracket(root/'WSCREEN/run', 'smoke', D.oracle_inputs(), 'overlap')
    W.require(summary.get('smoke_passed') is True, 'exact 12-prompt smoke required')
    cold_seconds = max(r['ttft_ms'] for r in summary['views'][0]['requests']) / 1000
    W.require(600 >= 4*cold_seconds, 'census per-operation wait below four times measured smoke cold phase')
    streams = [analyze.first_request(root/'WSCREEN/run/run/S0'/r['prompt_id'])
               for r in summary['views'][0]['requests']]
    return dict(passed=True, ready=True, smoke=str(root), smoke_job=job['name'],
                smoke_queue_sha256=W.sha(root/'queue.json'),
                build_receipt_sha256=W.sha(P/'build-receipt.json'),
                exact_oracle=True, analyzer_real_device_evidence=True, streams=streams,
                measured_smoke_cold_seconds=cold_seconds, per_operation_wait_seconds=600)

def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try: row = verify()
    except (ValueError, OSError, KeyError, TypeError, AssertionError) as error:
        row = dict(passed=False, ready=False, conditional=True, reason=str(error))
    print(json.dumps(row, indent=2))
    return 0 if row['ready'] else 1
if __name__ == '__main__': raise SystemExit(main())
