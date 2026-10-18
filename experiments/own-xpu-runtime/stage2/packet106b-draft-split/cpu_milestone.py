"""Sequential, bounded CPU preparation; completed stages survive disconnects."""
import json, os, subprocess, sys, time
from build_engine import P, ROOT, B, limits, sha, save

def main():
    limits()
    from bundle_selection import aliases, selection
    for label, v in aliases().items():
        target=P/'selections'/label
        target.mkdir(parents=True,exist_ok=True)
        save(target/'selection.json',selection(v))
    for script in sys.argv[1:]:
        log=P/'evidence'/(script+'.log')
        started=time.time()
        with log.open('w') as stream:
            result=subprocess.run([sys.executable,'-B',str(P/script)],cwd=P,
                stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT)
        save(P/'evidence'/(script+'.completed.json'),dict(passed=result.returncode==0,
            device_executed=False,script_sha256=sha(P/script),log_sha256=sha(log),
            seconds=time.time()-started,returncode=result.returncode))
        print(script,result.returncode,flush=True)
        if result.returncode:raise SystemExit(result.returncode)

if __name__=='__main__':main()
