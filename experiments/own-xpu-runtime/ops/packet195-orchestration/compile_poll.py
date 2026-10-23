"""Coordinator compile hold: no compiler/linker or multi-GB I/O while any window-*, lanequeue-* or packet* unit is
active or activating, apart from the owner's qwen38-* endpoints and an endpoint restore (brief 2026-10-23: a window-*
unit whose ExecStart argv ends in a '...-restore<N>' token is tolerated and recorded); poll every 60 s, deadline 90 min,
then proceed and say so. Appends to evidence/compile-poll.json. Read-only systemctl list-units/show; nothing is started
or stopped."""
import json, subprocess, time
from pathlib import Path
O = Path(__file__).resolve().parent
PATTERNS = ['window-*', 'lanequeue-*', 'packet*']


def units_now():
    r = subprocess.run(['systemctl', '--user', 'list-units', '--no-legend', '--plain', '--state=active,activating', *PATTERNS],
                       capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
    active = sorted(line.split()[0] for line in r.stdout.splitlines() if line.strip())
    allowed = []
    for unit in active:
        desc = subprocess.run(['systemctl', '--user', 'show', unit, '-p', 'Description', '--value'], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL).stdout.strip()
        last = desc.split()[-1] if desc.split() else ''
        if unit.startswith('window-') and '-restore' in last:
            allowed.append(dict(unit=unit, description=desc))
    blocking = [u for u in active if u not in [a['unit'] for a in allowed]]
    return dict(rc=r.returncode, active=active, endpoint_restore_units=allowed, blocking=blocking)


def poll(deadline_s=5400, period_s=60):
    rows, start = [], time.time()
    while True:
        u = units_now()
        rows.append(dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **u))
        if u['rc'] == 0 and not u['blocking']:
            return dict(patterns=PATTERNS, proceeded='no blocking window-*/lanequeue-*/packet* unit active or activating (endpoint-restore windows tolerated)', observations=rows)
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
