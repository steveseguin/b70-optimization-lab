"""Read-only verification of packet56 head qualification; no launch entry."""
import json
from pathlib import Path
import p56_head_summary as summarize
from p56_head_support import SUPERVISION, require, sha
HERE=Path(__file__).resolve().parent.parent / "packet56-draft-prefix"

def native_files(output):
    names = ('receipt.json', 'comparisons.jsonl', 'events.jsonl')
    return {'run/' + name: sha(output / 'run' / name) for name in names}

def verify_window(path):
    from chain_seal import checked as verify
    verify()
    path = Path(path).resolve()
    row = json.loads(path.read_text())
    require(row.get('schema') == 'own-runtime.packet56.window.v1' and row.get('passed') is True
            and row.get('device_executed') is True and row.get('child_still_running') is False
            and row.get('returncode') == 0 and not row.get('stop_reasons'), 'incomplete prefix window')
    require(row.get('card') == 0 and row.get('boot_id') == Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'prefix window card/boot identity')
    require(row.get('seal_sha256') == sha(HERE/'build-receipt.json')
            and row.get('binary_sha256') == sha(HERE/'build/device/p56-head-fixtures'), 'prefix window seal/binary changed')
    require(isinstance(row.get('pid'), int) and row['pid'] > 0 and row.get('process_start_ticks'), 'missing fresh owner identity')
    require(row.get('native_files') == native_files(path.parent), 'prefix native evidence changed')
    result = summarize.summarize(path.parent/'run')
    require(row.get('exact_output_identity') == result['exact_output_identity'], 'prefix output identity changed')
    require(sha(path.parent/'summary.json') == row.get('summary_sha256')
            and json.loads((path.parent/'summary.json').read_text()) == result, 'prefix summary changed')
    require(row.get('kernel_files') == {name: sha(path.parent/name) for name in ('kernel-before.txt','kernel-window.txt')}, 'kernel evidence changed')
    for name in ('kernel-before.txt','kernel-window.txt'):
        require(not SUPERVISION.FAULT.search((path.parent/name).read_text()), 'prefix window recorded GPU fault')
    require(not (HERE/'build'/('fault-'+row['boot_id']+'.json')).exists(), 'prefix fault latch exists')
    return row
