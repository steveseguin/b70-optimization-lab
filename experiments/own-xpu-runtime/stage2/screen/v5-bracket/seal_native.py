"""Bind the native build, real startup/reset/IPC gates and fixed selections."""
import argparse
from build_engine import P,ROOT,B,sha,save,limits
import json

def closure():
    sources={}
    for name in ('build','full-shape','reset-bytes','protocol'):
        path=P/'evidence'/(name+'.json');row=json.loads(path.read_text())
        assert row.get('passed') is True and row.get('device_executed') is False,name
        for leaf,digest in row.get('sources',{}).items():assert sha(ROOT/leaf)==digest,leaf
        sources.update(row.get('sources',{}));sources[str(path.relative_to(ROOT))]=sha(path)
        for leaf,digest in row.get('artifacts',{}).items():
            assert sha(P/leaf)==digest,leaf
            sources[str((P/leaf).relative_to(ROOT))]=digest
        for leaf,digest in row.get('binaries',{}).items():
            assert sha(ROOT/leaf)==digest,leaf
            sources[leaf]=digest
        if 'binary_sha256' in row:
            fixture=B/('full-shape' if name=='full-shape' else 'reset-bytes')/'fixture'
            assert sha(fixture)==row['binary_sha256'],str(fixture)
            sources[str(fixture.relative_to(ROOT))]=sha(fixture)
    for path in [*P.glob('native/*'),*P.glob('configs/*.json'),*P.glob('lineage/*.json'),
                 P/'bracket_config.py',P/'seal_native.py',P/'selection-provenance.json']:
        if path.name!='screen-seal.json':sources[str(path.relative_to(ROOT))]=sha(path)
    return sources

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    limits();path=P/'lineage/screen-seal.json'
    binary=B/'device/own-rt-iq3'
    row=dict(schema='own-runtime.bracket.cpu-seal.v1',passed=True,device_executed=False,
             arithmetic='iq3-p49-split32-v1',sources=closure(),binary_sha256=sha(binary),
             device_quality='pending first-use A/A smoke and full packet49 oracle per view',
             device_wall_savings='unmeasured')
    if args.verify:assert json.loads(path.read_text())==row,'native gate/selection closure changed'
    else:save(path,row)
    print('packet98 native CPU seal verified; no device execution')
if __name__=='__main__':main()
