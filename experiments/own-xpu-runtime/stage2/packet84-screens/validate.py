"""CPU-only full-shape startup and queue rehearsal; no live queue writes."""
import json
import shutil
import subprocess
import tempfile
from config import HERE, PACKET, ROOT, VIEWS, ORDER, view, output, verify, sha
from build_engine import limits, save

def main():
    limits(); verify()
    evidence = HERE / 'evidence'
    # Same real-worker import used by packet84 screen_plans.py's selected_check,
    # without rewriting the frozen packet's selected-* evidence files.
    from bootstrap import install, WRAPPER
    install()
    import runpy
    runpy.run_path(str(WRAPPER / 'tp2_worker.py'), run_name='cpu_import')
    fixture = PACKET / 'build/full-shape/fixture'
    runs = []
    for label in VIEWS:
        for rank in (0, 1):
            dest = evidence / f'startup-{label}-rank{rank}'
            dest.mkdir(exist_ok=True)
            sel = view(label) / 'selection.json'
            command = [str(fixture), str(sel), sha(sel), str(rank), str(dest), 'positive', '1', '0']
            with (dest / 'run.log').open('w') as log:
                subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
            result = json.loads((dest / 'result.json').read_text())
            assert result['passed'] and result['device_executed'] is False
            # The fixture checks the selected recurrence, route, HC, experts,
            # norm, host cleanup and draft head after the real post-load setup.
            runs.append(dict(choice=label, rank=rank, command=command, result=result,
                files={str(p.relative_to(ROOT)): sha(p) for p in dest.iterdir() if p.is_file()}))
    queue = ROOT / 'experiments/own-xpu-runtime/ops/lane-queue'
    proposed = queue / 'proposed-p84s-B.txt'
    with tempfile.TemporaryDirectory(prefix='packet84s-queue-') as tmp:
        target = __import__('pathlib').Path(tmp) / 'queue'
        shutil.copytree(queue, target)
        shutil.copyfile(proposed, target / 'queue-B.txt')
        command = ['/usr/bin/python3', '-B', str(queue / 'lanequeue.py'), 'plan', '--lane', 'B', '--directory', str(target)]
        with (evidence / 'queue-plan.jsonl').open('w') as out, (evidence / 'queue-plan.stderr').open('w') as err:
            subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=err, check=True, timeout=180)
    plans = [json.loads(line) for line in (evidence / 'queue-plan.jsonl').read_text().splitlines()]
    assert len(plans) == 4 and all(p['plan'] == 'passed' for p in plans)
    for index in range(4):
        command = ['/usr/bin/python3', '-B', str(HERE / 'screen_job.py'), '--lane', 'B',
                   '--index', str(index), '--output', str(output(index)), '--plan']
        dest = evidence / f'screen-plan-{index}.json'
        with dest.open('w') as log:
            subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, check=True, timeout=120)
        plan = json.loads(dest.read_text())
        assert plan['supported'] and not plan['device_executed']
        assert plan['reservation_scope'] == 'lane-B' and plan['physical_cards'] == [2, 3]
        assert plan['command'][2] == str(PACKET / 'worker.py')
    save(evidence / 'validation.json', dict(passed=True, device_executed=False, model_payload_read=False,
         full_shape_binary_sha256=sha(fixture), startup=runs, queue_plans=plans,
         proposed_sha256=sha(proposed), composition_pin_sha256=sha(HERE / 'composition-pin.json')))
    print('Six full-shape startups and all four temporary lane-B queue plans PASS')

if __name__ == '__main__':
    main()
