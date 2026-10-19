"""Close active admission inputs; retain unused inherited manifests verbatim.

The compiler closure remains hash checked. Historical vendor metadata is not
an active admission policy; use .snapshot names and record exact relocation.
Active screen admission retains every pin, against an owned byte copy.
"""
import json,sys,shutil
from prepare import P,ROOT,sha,save
sys.path.insert(0,str(P.parents[1]/'ops/lane-queue'))
import pin_guard as G

def main():
    from build_engine import limits
    limits()
    pins,_=G.collect_pins(P)
    oracle={(t,h) for t,h,s in pins if s.name=='oracle-binding.json'}
    bad=[(t,h,s) for t,h,s in pins if not t.is_relative_to(P) and not G.immutable_reason(t,h,P,oracle,G.STAGE)]
    historical=sorted({s for t,h,s in bad if s.is_relative_to(P/'vendor')})
    closure=json.loads((P/'lineage/source-closure.json').read_text())
    history=P/'lineage/historical-metadata.json'
    moves=json.loads(history.read_text())['files'] if history.exists() else []
    for src in historical:
        dst=src.with_suffix('.snapshot')
        digest=sha(src);src.rename(dst)
        moves.append(dict(original=str(src.relative_to(P)),snapshot=str(dst.relative_to(P)),sha256=digest))
        for row in closure['files']:
            if row['destination']==str(src.relative_to(P)):row['destination']=str(dst.relative_to(P))
    save(P/'lineage/source-closure.json',closure)
    save(P/'lineage/historical-metadata.json',dict(files=moves,reason='unused inherited policies; exact bytes retained, not active screen dependencies'))
    # Rewrite only active JSON policies. Original policy bytes stay in lineage.
    owned=P/'lineage/admission-closure.json'
    replacements={};copied=json.loads(owned.read_text())['files'] if owned.exists() else []
    for target,h,source in bad:
        if source in historical:continue
        assert target.suffix not in G.MODEL_SUFFIXES
        assert sha(target)==h, str(target)
        dst=P/'lineage/admission-inputs'/target.relative_to(ROOT)
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,dst)
        replacements[(source,str(target))]=str(dst)
        copied.append(dict(original=str(target.relative_to(ROOT)),owned=str(dst.relative_to(P)),sha256=h))
    for source in sorted({s for s,t in replacements}):
        original=P/'lineage/p58an-metadata-before'/source.relative_to(P)
        original.parent.mkdir(parents=True,exist_ok=True)
        if not original.exists():shutil.copy2(source,original)
        row=json.loads(source.read_text())
        def walk(value):
            if isinstance(value,str):
                for (s,target),dst in replacements.items():
                    if s==source and value in (target,str(Path(target).relative_to(ROOT))):return dst
                return value
            if isinstance(value,list):return [walk(v) for v in value]
            if isinstance(value,dict):return {walk(k):walk(v) for k,v in value.items()}
            return value
        save(source,walk(row))
    seal=P/'screen/host-admission/seal.json';row=json.loads(seal.read_text())
    row['files']={name:sha(seal.parent/name) for name in row['files']};save(seal,row)
    save(P/'lineage/admission-closure.json',dict(files=copied,device_executed=False))
    limits()

from pathlib import Path
if __name__=='__main__':main()
