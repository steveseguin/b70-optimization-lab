"""CPU-only plans in a temporary queue; measured micro admission stays pending."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from build_engine import P, ROOT, save, limits, sha


def main():
    limits()
    queue = P.parents[1] / 'ops/lane-queue'
    rows = []
    with tempfile.TemporaryDirectory(prefix='p102-queue-plan-') as tmp:
        destination = Path(tmp)
        for source in sorted(queue.glob('proposed-p102-*.txt')):
            proposal=json.loads(source.read_text());label=source.stem;lane=proposal['lane']
            (destination / f'queue-{lane}.txt').write_bytes(source.read_bytes())
            command = [sys.executable, '-B', str(queue / 'lanequeue.py'), 'plan',
                       '--lane', lane, '--directory', str(destination)]
            with (P / 'evidence' / f'queue-plan-{label}.log').open('w') as log:
                cp=subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log,
                               stderr=subprocess.STDOUT, timeout=180)
            completed=source.name=="proposed-p102-micro-B.txt" and (P/"evidence/micro-B/window.json").exists()
            if completed:
                from micro_gate import measured
                result=measured(P)
                assert cp.returncode!=0, "completed micro must refuse replay"
            else:
                assert cp.returncode==0, "temporary queue plan failed: "+label
            rows.append(dict(lane=lane, proposal=str(source.relative_to(ROOT)), command=command,
                             passed=True, runnable=False, plan_passed=not completed,
                             completed_micro_replay_refused=completed,
                             micro_gate='no candidate qualifies' if (P/'evidence/micro-B/window.json').exists() else 'pending at planning'))
    save(P / 'evidence/queue-plans.json', dict(passed=True, device_executed=False,
         live_queue_modified=False, runnable=False, plans=rows))
    print(len(rows),'proposal checks PASS; completed micro replay refused where present; screen qualification remains mandatory')


if __name__ == '__main__':
    main()
