#!/usr/bin/env python3
"""Serial GPU window queue for this session: one launcher at a time, a 5-minute gap after every stop,
global stop at the first new xe kernel line, and a failed item skips the rest of its group. No retries.
v4 (2026-10-15): any failure (main item or companion) marks both groups failed, writes queue/STOP with the
reason and exits, so nothing else reaches a card until the coordinator has read the failure and reset the
queue. The coordinator clears the fault latch only after this runner has exited."""
import os,subprocess,sys,time,glob,json
S=os.path.dirname(os.path.abspath(__file__)); Q=os.path.join(S,'queue'); LOG=os.path.join(S,'queue.log')
GAP_W=305   # after any model window (two cards, resident weights)
GAP_K=90    # after short kernel/fixture/benchmark windows (the owner asked for shorter waits after short bounded processes)
gap=GAP_W
def log(m):
    with open(LOG,'a') as f: f.write(time.strftime('%Y-%m-%dT%H:%M:%SZ ',time.gmtime())+m+'\n')
def xe_lines(since):
    out=subprocess.run(['journalctl','-k','--since','@%d'%since,'--no-pager'],capture_output=True,text=True).stdout
    return [l for l in out.splitlines() if 'xe ' in l]
t0=int(time.time()); last=float(sys.argv[1]) if len(sys.argv)>1 else 0.0
idle_deadline=time.time()+6*3600
log('runner start pid %d last=%d'%(os.getpid(),last))
while True:
    if os.path.exists(os.path.join(Q,'STOP')): log('STOP file; exiting'); break
    items=sorted(p for p in glob.glob(os.path.join(Q,'*.sh')) if not os.path.exists(p+'.done') and not os.path.exists(p+'.fail') and not os.path.exists(p+'.skip'))
    if not items:
        if time.time()>idle_deadline: log('idle deadline; exiting'); break
        time.sleep(5); continue
    item=items[0]; name=os.path.basename(item)[:-3]; group=name.split('-')[1] if '-' in name else name
    if os.path.exists(os.path.join(Q,'GROUPFAIL-'+group)):
        open(item+'.skip','w').write('group failed\n'); log('skip %s (group %s failed)'%(name,group)); continue
    wait=last+gap-time.time()
    if wait>0: time.sleep(min(wait,5)); continue
    bad=xe_lines(t0)
    if bad: log('GLOBAL STOP before %s: new xe kernel line: %s'%(name,bad[0][:200])); open(os.path.join(Q,'STOP'),'w').write(bad[0]); break
    subprocess.run([os.path.join(S,'affinity-codex.sh')],capture_output=True)
    log('launch %s load %s'%(name,open('/proc/loadavg').read().split()[0]))
    companion=None; cname=''
    if os.path.exists(item+'.companion'):
        cpath=open(item+'.companion').read().strip(); cname=os.path.basename(cpath)[:-3]
        if not os.path.exists(os.path.join(Q,'companion-'+cname+'.done')) and not os.path.exists(os.path.join(Q,'companion-'+cname+'.fail')):
            log('launch companion %s (disjoint card) with %s'%(cname,name)); companion=subprocess.Popen(['bash',cpath])
    rc=subprocess.run(['bash',item]).returncode
    if companion is not None:
        companion.wait(); ctail=''
        try: ctail=open(os.path.join(S,cname+'.log')).read().strip().splitlines()[-1]
        except Exception: pass
        cok=ctail.startswith('rc=0 ')
        log('%s companion %s: %s'%('done' if cok else 'FAIL',cname,ctail[:160]))
        open(os.path.join(Q,'companion-'+cname+('.done' if cok else '.fail')),'w').write(ctail+'\n')
        if not cok: open(os.path.join(Q,'GROUPFAIL-'+(cname.split('-')[1] if '-' in cname else cname)),'w').write(cname+'\n')
    last=time.time(); idle_deadline=time.time()+6*3600
    gap=GAP_W if any(t in n for n in (name,cname) for t in ('-W','-chain')) else GAP_K  # chains end in model windows
    tail=''
    # p45 scripts log to S/<number>-<name>.log; p44 scripts used S/<name>.log. Read whichever exists.
    for lp in [os.path.join(S,name+'.log')]+([os.path.join(S,name.split('-',1)[1]+'.log')] if '-' in name else []):
        try: tail=open(lp).read().strip().splitlines()[-1]; break
        except Exception: pass
    ok=tail.startswith('rc=0 ')
    log('%s %s: %s'%('done' if ok else 'FAIL',name,tail[:160]))
    open(item+('.done' if ok else '.fail'),'w').write(tail+'\n')
    if not ok: open(os.path.join(Q,'GROUPFAIL-'+group),'w').write(name+'\n')
    if not ok or (companion is not None and not cok):
        why='%s %s; companion %s %s'%(name,'ok' if ok else 'FAILED',cname or '-','-' if companion is None else ('ok' if cok else 'FAILED'))
        open(os.path.join(Q,'STOP'),'w').write('halt after failure: '+why+'\n'); log('HALT after failure (%s); exiting'%why); break
