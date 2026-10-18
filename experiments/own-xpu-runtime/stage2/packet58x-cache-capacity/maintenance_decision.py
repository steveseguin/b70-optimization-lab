"""Recheck frozen 58v evidence under 58wb's amended rule; no device or writes there."""
import hashlib,json,resource,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent
AMENDMENT=P.parent/'packet58w-onecard-record'
ROOT=P.parents[3]


def main():
    assert not (P/'evidence/card0-capacity-a').exists(), 'never amend after launch'
    # Isolated interpreters preserve frozen imports. Only replay evidence;
    # do not invoke verify()'s fresh-chain gate while 58w is running.
    code=("import json,subprocess,sys,verify_ready as R; "
          "s=json.loads(subprocess.check_output([sys.executable,'-B',str(R.P/'screen_gate.py')],"
          "stdin=subprocess.DEVNULL,text=True,timeout=180)); "
          "print(json.dumps(dict(decision=R.evaluate(s['rows']),sources=s['sources'],"
          "smoke_passed=s['smoke_passed'])))")
    result=subprocess.run([sys.executable,'-B','-c',code],cwd=AMENDMENT,
                          stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=240)
    replay=json.loads(result.stdout)
    assert replay['decision']['passed'] and replay['smoke_passed']
    sources=replay['sources']
    for source in (AMENDMENT/'screen_gate.py',AMENDMENT/'verify_ready.py',
                   AMENDMENT/'readiness-policy.json',ROOT/'notes/2026-10-18-own-runtime-packet58w.md'):
        sources[str(source.relative_to(ROOT))]=hashlib.sha256(source.read_bytes()).hexdigest()
    row=dict(passed=True,device_executed=False,default='overlap',parent_bracket_complete=True,
             amendment='packet58xb follows packet58wb; before any packet58x device window',
             reason='58v smoke and all five views rechecked exact against packet49; A0 reported warm-up, '
                    'excluded from comparison; both overlap views beat each warm serial control by >=0.5%, drift <=3%.',
             decision=replay['decision'],smoke_passed=True,sources=sources)
    (P/'maintenance-decision.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps({k:v for k,v in row.items() if k!='sources'}))


if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
