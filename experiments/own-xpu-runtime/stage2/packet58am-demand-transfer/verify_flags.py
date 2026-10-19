"""Verify proposed and inherited real launch flags against executable help."""
import json,subprocess,re
from pathlib import Path
from packet_io import P,ROOT,sha,save

def main():
    records=[]
    for kind in ('smoke','v5'):
        proposal=json.loads((P/f'proposals/{kind}.json').read_text())
        env={'PATH':'/usr/bin:/bin',**proposal['environment']}
        lane=ROOT/f'experiments/own-xpu-runtime/ops/lane-queue/proposed-p58am-{kind}-A.txt'
        row=json.loads(next(l for l in lane.read_text().splitlines() if l.startswith('{')))
        commands=[('model',proposal['native_argv']),*[(x['stage'],x['argv']) for x in proposal['pre_stage_commands']],('queue',row['argv'])]
        for name,cmd in commands:
            if name=='queue':help_cmd=cmd[:3]+['--help']
            else:help_cmd=cmd[:1]+['--help']
            cp=subprocess.run(help_cmd,env=env,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True)
            assert cp.returncode==0,(kind,name,cp.stderr[-1000:])
            flags={v for v in cmd if v.startswith('--')};advertised=set(re.findall(r'--[a-zA-Z0-9-]+',cp.stdout))
            assert flags<=advertised,(kind,name,flags-advertised)
            log=P/f'evidence/p58an-help-{kind}-{name}.log';log.write_text(cp.stdout+cp.stderr)
            records.append(dict(kind=kind,stage=name,flags=sorted(flags),help_sha256=sha(log),passed=True))
        assert proposal['native_argv'][proposal['native_argv'].index('--lookups')+1]=='resident'
        assert int(proposal['native_argv'][proposal['native_argv'].index('--wait-seconds')+1])>=300
    save(P/'evidence/p58an-flags.json',dict(passed=True,device_executed=False,records=records))
if __name__=='__main__':main()
