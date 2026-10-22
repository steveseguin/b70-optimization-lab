"""Allocation admission for the packet188 lineages from the measured production-shape census.

`v3` (packet187's record selection, 0-25 storage) keeps packet186's V3 dual ledger byte for byte, and its census equals
packet186's. `v3k`, `k3trims`, `k3`, `k3kio`, `k3prep` share one storage (the k3 storage, rank0_layers 0-26): that
ledger plus the census delta measured by p188_v5_full_shape.py with the real allocation calls. The delta is attributed
allocation by allocation from the retained census archives: rank 0 = exactly the allocations of GDN layer 26 (weights and
buffers), nothing removed; rank 1 = 0. The pinned kernel-io staging (one per rank) is host memory, not device bytes.
Host admission: the V3 row needs packet186's 107,667,817,956 B MemAvailable at START; the k3 rows add the host shadow of
the layer-26 device bytes and the pinned staging; both exclude the queue's extra 1 GiB.
"""
import json,resource,tarfile
from p188_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
from bracket_config import HOST_BASE,HOST_V3_EXTRA,HOST_K3_EXTRA,CENSUS_DELTA_K3,KIO_PINNED,host_required
K3=('v3k','k3trims','k3','k3kio','k3prep')
P186=LOCAL/'lineage-inputs/packet186-own/v5/evidence/admission.json'


def census_rows(shape,load,rank):
    art=next(r['artifact'] for r in shape['runs'] if r['load']==load and r['rank']==rank)
    assert sha(ROOT/art['path'])==art['sha256'],'retained census archive changed'
    with tarfile.open(ROOT/art['path']) as t:c=json.load(t.extractfile('census.json'))
    return {x['label']:x['bytes'] for x in c['allocations'] if x['memory']=='device' and x['live']},{x['label']:x['bytes'] for x in c['allocations'] if x['memory']!='device' and x['live']}


def main():
    limits();rows=[]
    from common import P56,module
    gate=module('p188_memory_admission',P56/'memory_gate.py')
    plans={mode:P/'lineage'/mode/'memory-plan.json' for mode in ('v3',*K3)}
    shape=json.loads((P/'evidence/full-shape.json').read_text());assert shape['passed'] and shape['v3_capture_identity_with_packet186']
    assert all(sha(plans[m])==shape['k3_memory_plan_sha256'] for m in K3),'k3 plan is not the full-shape derivation'
    parent=json.loads(P186.read_text())
    assert sha(plans['v3'])==sha(LOCAL.parent/'packet186-twocard-v3/v5/lineage/v3/memory-plan.json'),'v3 ledger must be packet186\'s V3 dual ledger'
    census={(r['layout'],r['rank']):r['device_allocation_bytes'] for r in shape['memory']}
    for mode,path in plans.items():
        layout='v3' if mode=='v3' else 'v3k-first'
        ledger=json.loads(path.read_text());config=gate.configuration(ledger,4096,1,0)
        for rank in config['ranks']:
            r=rank['rank'];live=census[(layout,r)]
            assert rank['free_with_mtp_bytes']>=ledger['minimum_free_bytes']
            assert rank['arena_device_bytes']<=ledger['arena_limit_bytes']
            assert live<=rank['total_with_mtp_bytes'],'census exceeds the plan'
            rows.append(dict(mode=mode,rank=r,planned_device_bytes=rank['arena_device_bytes'],planned_arena_headroom_bytes=ledger['arena_limit_bytes']-rank['arena_device_bytes'],
                planned_free_bytes=rank['free_with_mtp_bytes'],census_device_bytes=live,census_arena_headroom_bytes=ledger['arena_limit_bytes']-live,
                census_physical_free_bytes=ledger['capacity_bytes']-live,minimum_free_bytes=ledger['minimum_free_bytes'],host_required_available_bytes=host_required(mode)))
    # packet187's V3 rows: census identical to packet186's V3 dual layout
    v3_parent={(r['mode'],r['rank']):r for r in parent['rows']}
    assert all(census[('v3',r)]==v3_parent[('v3',r)]['census_device_bytes'] for r in (0,1)),'V3 census differs from packet186 admission'
    delta=shape['census_delta_bytes_per_rank']
    assert delta==[census[('v3k-first',0)]-census[('v3',0)],census[('v3k-first',1)]-census[('v3',1)]]==list(CENSUS_DELTA_K3)
    A,Ah=census_rows(shape,'v3k-first',0);B,Bh=census_rows(shape,'v3',0)
    added={k:v for k,v in A.items() if k not in B};removed={k:v for k,v in B.items() if k not in A}
    assert added and all('blk.26.' in k for k in added) and not removed and all(A[k]==B[k] for k in A if k in B),'rank 0 delta must be exactly layer 26'
    assert sum(added.values())==delta[0]
    A1,A1h=census_rows(shape,'v3k-first',1);B1,B1h=census_rows(shape,'v3',1)
    assert A1==B1,'rank 1 device allocations must be identical'
    pinned_added={k:v for k,v in Ah.items() if k not in Bh};pinned_added1={k:v for k,v in A1h.items() if k not in B1h}
    assert list(pinned_added)==['card0:kernel-io'] and list(pinned_added1)==['card0:kernel-io'],'only the kernel-io staging is added on the host side'
    assert pinned_added['card0:kernel-io']+pinned_added1['card0:kernel-io']==KIO_PINNED
    assert HOST_K3_EXTRA==HOST_V3_EXTRA+sum(delta)+KIO_PINNED and host_required('k3trims')==HOST_BASE+HOST_K3_EXTRA and host_required('v3')==107_667_817_956
    sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'admission_gate.py',P/'bracket_config.py',*plans.values(),P/'evidence/full-shape.json',P186)}
    save(P/'evidence/admission.json',dict(passed=True,device_executed=False,full_shape_read=False,driver_residency_unmeasured=True,rows=rows,
        census_delta_bytes_per_rank=delta,rank0_layer26_bytes=sum(added.values()),rank0_layer26_allocations=len(added),
        kernel_io_pinned_bytes=dict(rank0=pinned_added['card0:kernel-io'],rank1=pinned_added1['card0:kernel-io']),
        host_required_available_bytes=dict(v3=host_required('v3'),k3=host_required('k3trims')),host_queue_start_extra_bytes=1024**3,
        host_shadow_delta_over_v3_bytes=sum(delta)+KIO_PINNED,
        memory_summary=dict(v3=dict(rank0=dict(census=census[('v3',0)],arena_headroom=32212254720-census[('v3',0)]),rank1=dict(census=census[('v3',1)],arena_headroom=32212254720-census[('v3',1)])),
                            k3=dict(rank0=dict(census=census[('v3k-first',0)],arena_headroom=32212254720-census[('v3k-first',0)],physical_free=34242297856-census[('v3k-first',0)]),
                                    rank1=dict(census=census[('v3k-first',1)],arena_headroom=32212254720-census[('v3k-first',1)],physical_free=34242297856-census[('v3k-first',1)]))),
        note=('k3 storage: rank 0 census +1,129,070,858 B (layer 26) leaves 838,134,798 B arena headroom (plan 208,970,894 B; free with MTP 2.19 GB >= 1.5 GB); '
              'rank 1 unchanged (630,519,094 B census headroom; plan 1,373,494 B, identical to packet186/187 which ran on device)'),
        sources=sources))
    print('admission PASS: v3 + k3 storage; delta rank0',delta[0],'(layer 26, %d allocations) rank1'%len(added),delta[1],'host k3',host_required('k3trims'))


if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
