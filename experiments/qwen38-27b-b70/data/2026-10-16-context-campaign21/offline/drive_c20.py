import re, json, subprocess, datetime as dt, os, sys
R='/mnt/fast-ai/bench-results/context-longrun-20261012'
SP=os.path.dirname(os.path.abspath(__file__))
valid0={'c20b':['mini-swe-agent','open-interpreter','freeagent','goose','pi','qwen-code'],
       'c20d':['cline','openhands','hermes-agent','kimi-code','forgecode'],'c20e':['mistral-vibe'],'c20f':['opencode']}
valid=valid0; valid0['c20f']=['opencode']
day={'c20b':'2026-10-15','c20d':'2026-10-15','c20e':'2026-10-15','c20f':'2026-10-15'}
for camp, agents in valid.items():
    log=open(f'{R}/{camp}/campaign.log' if camp!='c20f' else f'{R}/c20f.log').read()
    for a in agents:
        st=re.findall(r'### (\d\d:\d\d:\d\d) \['+re.escape(a)+r'\] start', log)
        dn=re.findall(r'### (\d\d:\d\d:\d\d) \['+re.escape(a)+r'\] done', log)
        if not st or not dn: print('missing', camp, a, file=sys.stderr); continue
        t0=dt.datetime.strptime(day[camp]+' '+st[-1],'%Y-%m-%d %H:%M:%S').timestamp()
        t1=dt.datetime.strptime(day[camp]+' '+dn[-1],'%Y-%m-%d %H:%M:%S').timestamp()
        job=f'AB-{a}__repair-n40-s2x'
        ab=json.load(open(f'{R}/{camp}/runs/jobs/{job}/trial/agent/agentbench.json'))
        args={'label':f'{camp}/{a}','state':f'{R}/{camp}/proxy-state/{job}','requests':f'{R}/{camp}/runs/jobs/{job}/trial/agent/requests.jsonl',
              'agent_s':ab['agent_exit']['seconds'],'t0':t0,'t1':t1,'srvlog':f'{R}/server/tp2-w262144-{camp}/server.log',
              'dump_last':(f'{SP}/last-{a}.json' if not os.path.exists(f'{SP}/last-{a}.json') else None)}
        r=subprocess.run(['python3','-I',f'{SP}/run.py',json.dumps(args)],capture_output=True,text=True)
        if r.returncode: print(r.stderr, file=sys.stderr)
        d=json.loads(r.stdout); d['wall_s']=ab['wall_s']; d['verifier']={k:ab['verifier'].get(k) for k in ('fixed','clean')}; d['audit']=ab['verifier'].get('audit',{}).get('right')
        print(json.dumps(d)); sys.stdout.flush()
