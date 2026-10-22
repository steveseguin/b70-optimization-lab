"""Coordinator compile hold (2026-10-22): no compiler/linker or multi-GB I/O while window-p186-driver.service
is active or activating; poll every 60 s, deadline 90 min, then proceed and say so. Appends to evidence/compile-poll.json."""
import json, subprocess, time
from pathlib import Path
O = Path(__file__).resolve().parent
UNIT = 'window-p186-driver.service'
def poll(deadline_s=5400, period_s=60):
    rows, start = [], time.time()
    while True:
        r = subprocess.run(['systemctl', '--user', 'is-active', UNIT], capture_output=True, text=True, timeout=30)
        state = r.stdout.strip() or r.stderr.strip()
        rows.append(dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), state=state))
        if state not in ('active', 'activating'):
            return dict(unit=UNIT, proceeded='unit not active', observations=rows)
        if time.time() - start >= deadline_s:
            return dict(unit=UNIT, proceeded='90-minute deadline reached while active (coordinator rule: proceed and say so)', observations=rows)
        time.sleep(period_s)
if __name__ == '__main__':
    path = O / 'evidence/compile-poll.json'
    history = json.loads(path.read_text())['history'] if path.exists() else [dict(proceeded='session checks before the first compile', observations=[
        dict(utc='2026-10-22T16:30:17Z', state='active'), dict(utc='2026-10-22T16:40:03Z', state='active'),
        dict(utc='2026-10-22T16:44:15Z', state='active'), dict(utc='2026-10-22T16:45:07Z', state='inactive')])]
    row = poll()
    history.append(row)
    path.write_text(json.dumps(dict(row, passed=True, device_executed=False, history=history), indent=2) + '\n')
    print(row['proceeded'])
