"""Exercise startup refusal through the full-shape executable, not a JSON planner."""
import json,shutil,subprocess
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import aliases,selection
def main():
    limits();s=B/'full-shape';rows=[]
    shape=json.loads((P/'evidence/full-shape.json').read_text())
    assert shape['passed'] and sha(s/'fixture')==shape['binary_sha256']
    for label in ('control','draft_attention'):
        path=s/'negative-selection.json';save(path,selection(aliases()[label]))
        for mode in ('short','misaligned'):
            scratch=s/'negative-scratch';scratch.mkdir()
            try:
                cmd=[str(s/'fixture'),str(path),sha(path),'1',str(scratch),mode,'1','0']
                r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
                assert r.returncode!=0 and r.stderr.strip() and 'negative mode' not in r.stderr and not (scratch/'result.json').exists(),(label,mode,r.stderr)
                rows.append(dict(view=label,mode=mode,command=cmd,returncode=r.returncode,error=r.stderr.strip()))
            finally:shutil.rmtree(scratch)
    path.unlink()
    save(P/'evidence/startup-refusals.json',dict(passed=True,device_executed=False,runs=rows,
         sources={str((P/'negative_gate.py').relative_to(ROOT)):sha(P/'negative_gate.py'),
                  str((P/'evidence/full-shape.json').relative_to(ROOT)):sha(P/'evidence/full-shape.json')}))
    print(len(rows),'startup refusals PASS')
if __name__=='__main__':main()
