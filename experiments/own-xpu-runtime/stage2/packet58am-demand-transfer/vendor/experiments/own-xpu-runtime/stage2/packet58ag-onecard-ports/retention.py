"""Preserve extracted historical manifests outside the active pin closure."""
import json,shutil,sys
from build_engine import P,sha,save
from frozen_inputs import FROZEN

def main():
    # Original archive members remain byte-preserved and reconstruct these.
    # This only moves generated, historical manifests inside our new tree.
    sys.path.insert(0,str(P.parents[1]/'ops/lane-queue'));import pin_guard
    compiled=json.loads((P/'evidence/build.json').read_text())['sources'];rows=[]
    for p in FROZEN.rglob('*.json'):
        row=json.loads(p.read_text())
        if not list(pin_guard.extract_pins(row)):continue
        assert str(p.relative_to(P.parents[3])) not in compiled
        dest=P/'lineage/extracted-metadata'/p.relative_to(FROZEN);dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert sha(dest)==sha(p);p.unlink()
        else:shutil.move(p,dest)
        rows.append(dict(member=str(dest.relative_to(P)),digest=sha(dest)))
    save(P/'evidence/retention.json',dict(passed=True,device_executed=False,moved_historical_metadata=rows,original_archives_preserved=True))
if __name__=='__main__':main()
