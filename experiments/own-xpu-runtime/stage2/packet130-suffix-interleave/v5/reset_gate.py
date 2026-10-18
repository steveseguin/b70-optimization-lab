"""Compile and execute only the real miniature CPU backend, never a device."""
import json,subprocess,shutil,time
from build_engine import P,ROOT,B,BASE,sha,save,limits,compiler_turn

def main():
    limits();out=B/'reset-bytes';out.mkdir(exist_ok=True)
    prior=json.loads((P/'evidence/build.json').read_text())['commands']
    args=next(r['command'] for r in prior if r['name']=='gnu-host-entry-main');args=args[:args.index('-o')]
    args=[x for x in args if not x.startswith('-O')]+['-O1','-I'+str(P/'native-src')]
    cmd=[*args,'-c',str(P/'native/reset_bytes.cpp'),'-o',str(out/'entry.o')]
    link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'))
    link=[str(out/'entry.o') if a.endswith('/entry-main.o') else a for a in link if not a.endswith('own-rt-iq3-entry.cpp.o')]
    link[link.index('-o')+1]=str(out/'fixture')
    with compiler_turn():
        for name,command in (('compile',cmd),('link',link)):
            with (out/(name+'.log')).open('w') as f:subprocess.run(command,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
    from mini_selection import prepare
    control,candidate=prepare();runs=[]
    for rank in (0,1):
        for repeat in (0,1):
            dest=out/f'rank{rank}-{repeat}';dest.mkdir(exist_ok=False);started=time.monotonic()
            command=[str(out/'fixture'),str(control),sha(control),str(rank),str(dest),str(candidate),sha(candidate)]
            with (out/f'rank{rank}-{repeat}.log').open('w') as f:subprocess.run(command,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
            row=json.loads((dest/'result.json').read_text());runs.append(dict(rank=rank,repeat=repeat,seconds=time.monotonic()-started,**row))
            # Only generated miniature bytes are scratch; retain compact hashes/results.
            save(P/'evidence'/f'reset-rank{rank}-{repeat}.json',row);shutil.rmtree(dest)
            print('real CPU reset bytes',rank,repeat,'PASS',flush=True)
    save(P/'evidence/reset-bytes.json',dict(passed=True,device_executed=False,runs=runs,binary_sha256=sha(out/'fixture'),commands=[cmd,link],
         fixture_projection='experts=wide64, head=production, selected suffix_schedule retained; reset evidence only, actual split-head arithmetic and arrival ordering covered by head/controller gates',
         sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'reset_gate.py',P/'native/reset_bytes.cpp',P/'mini_selection.py',control,candidate]}))
    limits()
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 main()
