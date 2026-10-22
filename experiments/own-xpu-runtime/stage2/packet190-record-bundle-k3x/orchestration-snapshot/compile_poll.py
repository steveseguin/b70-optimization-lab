"""Coordinator compile hold: no compiler/linker or multi-GB I/O while any window-*, lanequeue-*, packet18*/packet19*
unit is active or activating (the owner's qwen38-* endpoints are not a hold); poll every 60 s, deadline 90 min, then
proceed and say so. Appends to evidence/compile-poll.json. Read-only systemctl list-units; nothing is started or stopped."""
import json, subprocess, time
from pathlib import Path
O = Path(__file__).resolve().parent
PATTERNS = ['window-*', 'lanequeue-*', 'packet18*', 'packet19*']
def busy():
    r = subprocess.run(['systemctl', '--user', 'list-units', '--no-legend', '--plain', '--state=active,activating', *PATTERNS], capture_output=True, text=True, timeout=30)
    return sorted(line.split()[0] for line in r.stdout.splitlines() if line.strip())
def poll(deadline_s=5400, period_s=60):
    rows, start = [], time.time()
    while True:
        units = busy()
        rows.append(dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), active_units=units))
        if not units:
            return dict(patterns=PATTERNS, proceeded='no window/lane/packet unit active', observations=rows)
        if time.time() - start >= deadline_s:
            return dict(patterns=PATTERNS, proceeded='90-minute deadline reached while active (coordinator rule: proceed and say so)', observations=rows)
        time.sleep(period_s)
if __name__ == '__main__':
    path = O / 'evidence/compile-poll.json'
    history = json.loads(path.read_text())['history'] if path.exists() else []
    row = poll()
    history.append(row)
    path.write_text(json.dumps(dict(row, passed=True, device_executed=False, history=history), indent=2) + '\n')
    print(row['proceeded'], row['observations'][-1])
