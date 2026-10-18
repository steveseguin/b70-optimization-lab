"""Copy frozen packet97 sources; retain byte identity, never edit the parent."""
import hashlib,json,shutil
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
BASE=P.parent/'packet97-record-bundle'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert not (P/'copy-lineage.json').exists()
    files=[f for f in BASE.iterdir() if f.suffix in ('.hpp','.cpp','.inc')]
    files+=list((BASE/'p28').glob('*'))
    files += [f for f in (BASE/'prototype').rglob('*') if f.is_file() and f.suffix in ('.hpp','.cpp','.inc')]
    tools=('bootstrap.py','worker.py','placement.py','run_screen.py','compare.py',
           'kernel_gate.py','kernel_overlay.py','submission_overlay.py','math_gate.py',
           'memory_gate.py','memory_plans.py','full_shape.py')
    files += [BASE/n for n in tools]
    files += [BASE/n for n in ('selection-template.json','dispatch-speed6.json',
             'dependency-pins.json','shared-wrapper-pin.json','engine-commands.json',
             'rope.bf16','mtp-manifest.tsv','placement-policy.json')]
    rows={}
    for source in files:
        dest=P/source.relative_to(BASE);dest.parent.mkdir(parents=True,exist_ok=True)
        assert not dest.exists(),dest
        shutil.copyfile(source,dest)
        assert sha(source)==sha(dest)
        rows[str(dest.relative_to(ROOT))]={'source':str(source.relative_to(ROOT)),'sha256':sha(source)}
    (P/'build/tmp').mkdir(parents=True)
    (P/'evidence').mkdir()
    (P/'copy-lineage.json').write_text(json.dumps(rows,indent=2)+'\n')
if __name__=='__main__':main()
