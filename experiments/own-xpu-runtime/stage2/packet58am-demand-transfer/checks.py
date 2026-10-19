"""Run bounded CPU Python evidence checks and preserve their result."""
import subprocess,sys
from prepare import P,sha,save
from build_engine import limits,compiler_turn
def main():
    limits()
    with compiler_turn(),(P/'evidence/python-tests.log').open('w') as log:
        result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(P),'-p','test_*.py','-v'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
    assert result.returncode==0
    from analyze import replay,replay_resident
    replay()
    replay_resident()
    save(P/'evidence/python-tests.json',dict(passed=True,device_executed=False,log_sha256=sha(P/'evidence/python-tests.log'),
         test_sources={f.name:sha(f) for f in P.glob('test_*.py')}))
    print('Python failure/reader/admission tests and real-parent replay PASS')
if __name__=='__main__':main()
