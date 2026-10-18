#!/usr/bin/env python3
"""Choose previously sealed bytes before a chain starts; never rebuild."""
import argparse
import json
import os
import time
from pathlib import Path
from build_engine import save, sha
from bundle_selection import PLACEMENTS, EXPERTS, DENSE, HC, HOST, ROUTE, NORM, RECURRENCE, DRAFT_HEAD, KEYS, name as view_name
P = Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--placement',choices=PLACEMENTS,default='1')
    ap.add_argument('--draft',choices=('draft-hc',),default='draft-hc')
    ap.add_argument('--miss',choices=('batch',),default='batch')
    ap.add_argument('--experts',choices=EXPERTS,default='wide64')
    ap.add_argument('--dense',choices=DENSE,default='production')
    ap.add_argument('--hc',choices=HC,default='production')
    ap.add_argument('--host',choices=HOST,default='production')
    ap.add_argument('--route',choices=ROUTE,default='production')
    ap.add_argument('--norm',choices=NORM,default='production')
    ap.add_argument('--recurrence',choices=RECURRENCE,default='production')
    ap.add_argument('--draft_head',choices=DRAFT_HEAD,default='production')
    a=ap.parse_args();start=time.monotonic()
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16))|set(range(24,32))
    from storage import B,REGISTERED_CHAIN
    from stopped_archive import require_fresh_chain
    require_fresh_chain(B)
    name=view_name(*(getattr(a,k) for k in KEYS));view=P/'selections'/(name+'--placement-'+a.placement)
    from prepare_packet import seal_view
    seal_view(tuple(getattr(a,k) for k in KEYS),a.placement)
    seal=json.loads((view/'screen-seal.json').read_text())
    from chain_seal import check_map
    check_map(P.parents[3],seal['sources']);check_map(view,seal['artifacts']);check_map(view,seal['gates']);check_map(view,seal['fixture_files'])
    if (P/'build-receipt.json').exists():
        archive=P/'evidence'/('prior-chain-seal-'+sha(P/'build-receipt.json')+'.json')
        if not archive.exists(): archive.write_bytes((P/'build-receipt.json').read_bytes())
    for leaf in ('selection.json','memory-plan.json','dispatch-speed6.json','screen-seal.json'):
        (P/leaf).write_bytes((view/leaf).read_bytes())
    rank,split,boundary=PLACEMENTS[a.placement]
    save(P/'bundle-selection.json',dict(name=name,placement=a.placement,draft=a.draft,miss=a.miss,
        draft_rank=rank,target_split=split,layer_boundary=boundary,experts=a.experts,dense=a.dense,hc=a.hc,host=a.host,route=a.route,norm=a.norm,recurrence=a.recurrence,draft_head=a.draft_head,
        selection_sha256=sha(P/'selection.json'),screen_seal_sha256=sha(view/'screen-seal.json')))
    from chain_seal import checked, verify
    save(P/'build-receipt.json',checked())
    from packet56_submission import pin_resealed_packet56
    pin_resealed_packet56();verify()
    elapsed=time.monotonic()-start
    assert elapsed<120, 'reseal exceeded two minutes'
    print(json.dumps(dict(passed=True,device_executed=False,selection=name,seconds=elapsed)))

if __name__=='__main__':main()
