#!/usr/bin/env python3
"""Read-only bounded status of packet38 CPU qualification."""
import argparse,datetime,json,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--wait',type=float,default=0);a=ap.parse_args();assert 0<=a.wait<=50;time.sleep(a.wait)
    active=[]
    for root in sorted((P/'build').iterdir()):
        if not root.is_dir() or not root.name.startswith(('real-native-','real-icpx-host-','suite-real-')):continue
        positions=[]
        for rank in (0,1):
            for f in (root/f'rank{rank}/timings.jsonl',root/f'ranks/rank{rank}/timings.jsonl'):
                try:
                    with f.open('rb') as source:
                        source.seek(max(0,f.stat().st_size-10000));lines=source.read().splitlines()
                    for line in reversed(lines):
                        try:row=json.loads(line)
                        except (ValueError,UnicodeDecodeError):continue
                        positions.append(dict(rank=rank,position=row.get('position'),fixture=row.get('fixture')));break
                except OSError:pass
        active.append(dict(root=root.name,positions=positions))
    completed={}
    for prefix in ('','icpx-host-','native-'):
        modes=[]
        for mode in ('none','ngram','hit','miss','mtp'):
            try:
                if json.loads((P/f'real-{prefix}{mode}.json').read_text()).get('passed') is True:modes.append(mode)
            except (OSError,ValueError):pass
        completed[prefix or 'gnu-host']=modes
    free=int(subprocess.check_output(['df','-B1','/'],text=True).splitlines()[-1].split()[3])
    print(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),completed=completed,active=active,root_free_bytes=free)))
if __name__=='__main__':main()
