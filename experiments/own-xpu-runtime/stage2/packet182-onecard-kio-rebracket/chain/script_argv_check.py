#!/usr/bin/env python3
"""Script-mode chain-flag check (the chain-176-a defect class). CPU only; nothing launches.

For a derived one-card chain packet P, run P/suite_driver.py exactly as window.py does
(as a script: runpy with run_name='__main__', argv --window W --card 0 --output ...
--miss-mode zerocopy --authorized-device-window --view down-tile16) for every model
window, with the native child intercepted: subprocess.Popen raises before anything is
executed, so the driver's first receipt.json (written before the child) holds the exact
native argv it would have launched. Every chain flag of P/derived-chain.json must occur
exactly once with its value. onecard_chain_derive.py --predevice-check imports
suite_driver as a module and therefore cannot see this (it passed on packet176c).

Simulated (as in the generator's pre-device rehearsal): the coordinator's process
priority/affinity and chain_devices.verify_onecard_environment. Writes go only to a
temporary directory under P/evidence that is removed afterwards.

  python3 -B script_argv_check.py <packet-dir> [--json out.json]
Exit 0 = every window carries every flag; 3 = a window lacks a flag (prints which).
"""
import argparse, json, os, runpy, shutil, subprocess, sys, uuid
from pathlib import Path

WINDOWS = ('KD', 'W2m', 'WS', 'WS128x', 'WS128')

PROBE = r'''
import json,os,runpy,subprocess,sys
from pathlib import Path
P=Path(sys.argv[1]);window=sys.argv[2];out=Path(sys.argv[3])
sys.path.insert(0,str(P))
import chain_devices
chain_devices.verify_onecard_environment=lambda env:None
os.getpriority=lambda *a:0 if window.startswith('W') else 19
os.sched_getaffinity=lambda *a:set(range(4))|set(range(16,20)) if window.startswith('W') else set(range(8,16))|set(range(24,32))
class Intercepted(Exception):pass
def popen(cmd,*a,**k):raise Intercepted('native child intercepted')
subprocess.Popen=popen
sys.argv=[str(P/'suite_driver.py'),'--window',window,'--card','0','--output',str(out),'--miss-mode','zerocopy',
          '--authorized-device-window','--view','down-tile16']
code=None
try:runpy.run_path(str(P/'suite_driver.py'),run_name='__main__')
except SystemExit as e:code=e.code
row=json.loads((out/'receipt.json').read_text())
print('ARGV='+json.dumps(dict(exit=code,command=row['command'],device_executed=row.get('device_executed'),error=row.get('error'))))
'''


def check(P, flags):
    P = Path(P).resolve()
    scratch = P / 'evidence' / ('.script-argv-' + uuid.uuid4().hex)
    rows, bad = [], []
    try:
        for window in WINDOWS:
            out = scratch / window
            cp = subprocess.run([sys.executable, '-B', '-c', PROBE, str(P), window, str(out)], cwd=P.parents[3],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600,
                                env=dict(PATH='/usr/bin:/bin', OMP_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1',
                                         LD_LIBRARY_PATH=os.environ.get('LD_LIBRARY_PATH', '')))
            line = next((s for s in cp.stdout.splitlines() if s.startswith('ARGV=')), None)
            if line is None:
                bad.append(f'{window}: driver did not reach the native child: ' + (cp.stderr or cp.stdout)[-600:])
                continue
            got = json.loads(line[5:])
            command = got['command']
            missing = [f for f, v in flags.items() if command.count(f) != 1 or command[command.index(f) + 1] != v]
            if got['device_executed'] is not False:
                bad.append(f'{window}: receipt says device_executed={got["device_executed"]}')
            if missing:
                bad.append(f'{window}: native argv lacks ' + ', '.join(f'{f} {flags[f]}' for f in missing))
            rows.append(dict(window=window, native_argv=command, flags_present=not missing,
                             native_child_executed=False, driver_exit=got['exit'], driver_error=got['error']))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return dict(passed=not bad and len(rows) == len(WINDOWS), device_executed=False, packet=str(P), flags=flags,
                mode='suite_driver.py run as a script (runpy __main__), native Popen intercepted', windows=rows, failures=bad)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('packet', type=Path)
    ap.add_argument('--json', type=Path)
    ap.add_argument('--flags', help='JSON object; default: derived-chain.json flags')
    a = ap.parse_args()
    flags = json.loads(a.flags) if a.flags else json.loads((a.packet / 'derived-chain.json').read_text())['flags']
    row = check(a.packet, flags)
    if a.json:
        a.json.write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(dict(passed=row['passed'], failures=row['failures'])))
    return 0 if row['passed'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
