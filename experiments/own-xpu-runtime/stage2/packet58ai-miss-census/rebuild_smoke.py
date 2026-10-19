"""Rebuild only changed entry-main and relink; obey the shared compiler hold."""
import json
import resource
import subprocess
import time
from build_engine import P,B,sha,save,limits,turn

def main():
    limits()
    receipt=json.loads((P/'evidence/build.json').read_text())
    save(P/'evidence/p58aib-build-before.json',receipt)
    changed=[]
    for mode in ('gnu-host','device'):
        for suffix in ('entry-main','own-rt-iq3'):
            row=next(r for r in receipt['commands'] if r['name']==mode+'-'+suffix)
            with turn(),(B/(row['name']+'-p58aib.log')).open('w') as log:
                start=time.monotonic()
                cp=subprocess.run(row['command'],stdin=subprocess.DEVNULL,stdout=log,
                                  stderr=subprocess.STDOUT,timeout=900)
            assert cp.returncode==0,row['name']
            row.update(returncode=0,seconds=time.monotonic()-start)
            changed.append(row['name'])
            print(row['name'],'PASS',flush=True)
        name='build/'+mode+'/own-rt-iq3'
        receipt['artifacts'][name]=sha(P/name)
    receipt['max_rss_kib']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    assert receipt['max_rss_kib']<2*1024**2
    receipt['p58aib_rebuilt_commands']=changed
    save(P/'evidence/build.json',receipt)

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    main()
